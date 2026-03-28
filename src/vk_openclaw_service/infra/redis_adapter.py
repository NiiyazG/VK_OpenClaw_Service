"""Redis adapter probes and factories."""

from __future__ import annotations

import importlib
import importlib.util
import json
import time
from dataclasses import dataclass
from importlib.machinery import ModuleSpec
from typing import Any, Callable, Protocol, cast

from vk_openclaw_service.services.worker_lease import WorkerLeaseRecord


@dataclass(frozen=True)
class RedisDriverState:
    available: bool
    reason: str | None = None


class RedisModule(Protocol):
    def from_url(self, dsn: str) -> Any: ...


@dataclass(frozen=True)
class RedisAdapter:
    dsn: str

    def open_session(
        self,
        *,
        module_loader: Callable[[], RedisModule] | None = None,
    ) -> "RedisSession":
        module = (module_loader or import_redis_module)()
        client = module.from_url(self.dsn)
        return RedisSession(client=client)


@dataclass
class RedisSession:
    client: Any

    def increment(self, key: str, ttl_seconds: int) -> int:
        value = int(self.client.incr(key))
        if value == 1:
            self.client.expire(key, ttl_seconds)
        return value

    def claim_once(self, key: str, ttl_seconds: int) -> bool:
        result = self.client.set(key, "1", nx=True, ex=ttl_seconds)
        return bool(result)

    def acquire(self, key: str, token: str, owner_id: str, ttl_seconds: int) -> bool:
        current = self.get(key)
        ts = time.time()
        if current is not None:
            last_seen = current.refreshed_at if current.refreshed_at is not None else current.acquired_at
            if last_seen is None or ts - last_seen < ttl_seconds:
                return False
        payload = json.dumps(
            {
                "acquired_at": ts,
                "owner_id": owner_id,
                "previous_owner_id": current.owner_id if current is not None else None,
                "refreshed_at": ts,
                "takeover_at": ts if current is not None else None,
                "takeover_count": current.takeover_count + 1 if current is not None else 0,
                "token": token,
            },
            sort_keys=True,
        )
        result = self.client.set(key, payload, nx=current is None, ex=ttl_seconds)
        return bool(result)

    def refresh(self, key: str, token: str, ttl_seconds: int) -> bool:
        current = self.get(key)
        if current is None or current.token != token:
            return False
        refreshed_at = time.time()
        payload = json.dumps(
            {
                "acquired_at": current.acquired_at,
                "owner_id": current.owner_id,
                "previous_owner_id": current.previous_owner_id,
                "refreshed_at": refreshed_at,
                "takeover_at": current.takeover_at,
                "takeover_count": current.takeover_count,
                "token": current.token,
            },
            sort_keys=True,
        )
        self.client.set(key, payload, nx=False, ex=ttl_seconds)
        self.client.expire(key, ttl_seconds)
        return True

    def release(self, key: str, token: str) -> None:
        current = self.get(key)
        if current is not None and current.token == token:
            self.client.delete(key)

    def get(self, key: str) -> WorkerLeaseRecord | None:
        current = self.client.get(key)
        if current is None:
            return None
        if isinstance(current, bytes):
            current = current.decode("utf-8")
        if current.startswith("{"):
            decoded = json.loads(current)
            return WorkerLeaseRecord(
                token=str(decoded["token"]),
                owner_id=str(decoded["owner_id"]),
                acquired_at=float(decoded["acquired_at"]) if decoded.get("acquired_at") is not None else None,
                refreshed_at=float(decoded["refreshed_at"]) if decoded.get("refreshed_at") is not None else None,
                previous_owner_id=(
                    str(decoded["previous_owner_id"]) if decoded.get("previous_owner_id") is not None else None
                ),
                takeover_at=float(decoded["takeover_at"]) if decoded.get("takeover_at") is not None else None,
                takeover_count=int(decoded.get("takeover_count", 0)),
            )
        return WorkerLeaseRecord(token=str(current), owner_id="unknown")

    def enqueue(self, key: str, payload: dict[str, object]) -> None:
        self.client.rpush(key, json.dumps(payload, sort_keys=True))

    def dequeue_ready(self, key: str, now_ts: float) -> dict[str, object] | None:
        length = int(self.client.llen(key))
        for _ in range(length):
            payload = self.client.lpop(key)
            if payload is None:
                return None
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            decoded = json.loads(payload)
            if float(decoded["available_at"]) <= now_ts:
                return decoded
            self.client.rpush(key, payload)
        return None


def probe_redis_driver(
    module_finder: Callable[[str], ModuleSpec | None] = importlib.util.find_spec,
) -> RedisDriverState:
    if module_finder("redis") is not None:
        return RedisDriverState(available=True, reason=None)
    return RedisDriverState(available=False, reason="missing_redis_driver")


def build_redis_adapter(dsn: str) -> RedisAdapter:
    return RedisAdapter(dsn=dsn)


def import_redis_module() -> RedisModule:
    return cast(RedisModule, importlib.import_module("redis"))
