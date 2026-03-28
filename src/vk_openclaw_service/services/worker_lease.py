"""Ephemeral worker coordination lease."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import time
from typing import Protocol, cast
from uuid import uuid4


@dataclass(frozen=True)
class WorkerLeaseRecord:
    token: str
    owner_id: str
    acquired_at: float | None = None
    refreshed_at: float | None = None
    previous_owner_id: str | None = None
    takeover_at: float | None = None
    takeover_count: int = 0


class WorkerLeaseStore(Protocol):
    def acquire(self, key: str, token: str, owner_id: str, ttl_seconds: int) -> bool: ...
    def refresh(self, key: str, token: str, ttl_seconds: int) -> bool: ...
    def release(self, key: str, token: str) -> None: ...
    def get(self, key: str) -> WorkerLeaseRecord | None: ...


class AuditRepository(Protocol):
    def append_event(
        self,
        *,
        event_type: str,
        peer_id: int | None,
        status: str,
        details: dict[str, object],
    ) -> object: ...


@dataclass
class InMemoryWorkerLeaseStore:
    claims: dict[str, WorkerLeaseRecord] = field(default_factory=dict)
    now: Callable[[], float] = time.time

    def acquire(self, key: str, token: str, owner_id: str, ttl_seconds: int) -> bool:
        current = self.claims.get(key)
        if current is not None and not _is_stale(current, self.now(), ttl_seconds):
            return False
        ts = self.now()
        previous_owner_id = current.owner_id if current is not None else None
        takeover_at = ts if current is not None else None
        takeover_count = current.takeover_count + 1 if current is not None else 0
        self.claims[key] = WorkerLeaseRecord(
            token=token,
            owner_id=owner_id,
            acquired_at=ts,
            refreshed_at=ts,
            previous_owner_id=previous_owner_id,
            takeover_at=takeover_at,
            takeover_count=takeover_count,
        )
        return True

    def refresh(self, key: str, token: str, ttl_seconds: int) -> bool:
        del ttl_seconds
        current = self.claims.get(key)
        if current is None or current.token != token:
            return False
        self.claims[key] = WorkerLeaseRecord(
            token=current.token,
            owner_id=current.owner_id,
            acquired_at=current.acquired_at,
            refreshed_at=self.now(),
            previous_owner_id=current.previous_owner_id,
            takeover_at=current.takeover_at,
            takeover_count=current.takeover_count,
        )
        return True

    def release(self, key: str, token: str) -> None:
        current = self.claims.get(key)
        if current is not None and current.token == token:
            self.claims.pop(key, None)

    def get(self, key: str) -> WorkerLeaseRecord | None:
        return self.claims.get(key)


@dataclass(frozen=True)
class WorkerLease:
    store: WorkerLeaseStore
    audit_repository: AuditRepository | None = None
    owner_id: str = "worker-default"
    key: str = "vk-openclaw:worker-lease"
    ttl_seconds: int = 15
    now: Callable[[], float] = time.time

    def acquire(self) -> str | None:
        self._sync_store_now()
        previous = self.store.get(self.key)
        token = uuid4().hex
        if not self.store.acquire(self.key, token, self.owner_id, self.ttl_seconds):
            return None
        self._append_takeover_audit_event(previous)
        return token

    def refresh(self, token: str) -> bool:
        self._sync_store_now()
        return self.store.refresh(self.key, token, self.ttl_seconds)

    def release(self, token: str) -> None:
        self.store.release(self.key, token)

    def snapshot(self) -> dict[str, object]:
        record = self.store.get(self.key)
        active = record is not None
        owner_id = record.owner_id if record is not None else None
        held_by_self = owner_id == self.owner_id if owner_id is not None else False
        stale = _is_stale(record, self.now(), self.ttl_seconds) if record is not None else False
        return {
            "configured_owner_id": self.owner_id,
            "lease_key": self.key,
            "held": active,
            "owner_id": owner_id,
            "held_by_self": held_by_self,
            "stale": stale,
            "acquired_at": record.acquired_at if record is not None else None,
            "refreshed_at": record.refreshed_at if record is not None else None,
            "previous_owner_id": record.previous_owner_id if record is not None else None,
            "takeover_at": record.takeover_at if record is not None else None,
            "takeover_count": record.takeover_count if record is not None else 0,
            "ttl_seconds": self.ttl_seconds,
        }

    def run(self, callback: Callable[[], object]) -> tuple[bool, object | None]:
        token = self.acquire()
        if token is None:
            return False, None
        try:
            return True, callback()
        finally:
            self.release(token)

    def reset_if_stale(self, *, operator_id: str = "admin_api") -> dict[str, object] | None:
        self._sync_store_now()
        current = self.store.get(self.key)
        if current is None or not _is_stale(current, self.now(), self.ttl_seconds):
            return None
        snapshot = cast(
            dict[str, object],
            {
            "lease_key": self.key,
            "owner_id": current.owner_id,
            "acquired_at": current.acquired_at,
            "refreshed_at": current.refreshed_at,
            "previous_owner_id": current.previous_owner_id,
            "takeover_at": current.takeover_at,
            "takeover_count": current.takeover_count,
            "ttl_seconds": self.ttl_seconds,
            },
        )
        self.store.release(self.key, current.token)
        self._append_reset_audit_event(current, operator_id=operator_id)
        return snapshot

    def _append_takeover_audit_event(self, previous: WorkerLeaseRecord | None) -> None:
        if self.audit_repository is None or previous is None:
            return
        if previous.owner_id == self.owner_id:
            return
        if not _is_stale(previous, self.now(), self.ttl_seconds):
            return
        last_seen = previous.refreshed_at if previous.refreshed_at is not None else previous.acquired_at
        stale_for_seconds = None if last_seen is None else max(self.now() - last_seen, 0.0)
        self.audit_repository.append_event(
            event_type="worker_lease_taken_over",
            peer_id=None,
            status="ok",
            details={
                "lease_key": self.key,
                "previous_owner_id": previous.owner_id,
                "owner_id": self.owner_id,
                "requested_by": f"worker:{self.owner_id}",
                "trigger": "automatic_stale_takeover",
                "stale_for_seconds": stale_for_seconds,
                "ttl_seconds": self.ttl_seconds,
            },
        )

    def _append_reset_audit_event(self, current: WorkerLeaseRecord, *, operator_id: str) -> None:
        if self.audit_repository is None:
            return
        last_seen = current.refreshed_at if current.refreshed_at is not None else current.acquired_at
        stale_for_seconds = None if last_seen is None else max(self.now() - last_seen, 0.0)
        self.audit_repository.append_event(
            event_type="worker_lease_reset",
            peer_id=None,
            status="ok",
            details={
                "lease_key": self.key,
                "previous_owner_id": current.owner_id,
                "requested_by": operator_id,
                "stale_for_seconds": stale_for_seconds,
                "ttl_seconds": self.ttl_seconds,
            },
        )

    def _sync_store_now(self) -> None:
        if self.now is not time.time and hasattr(self.store, "now"):
            setattr(self.store, "now", self.now)


def _is_stale(record: WorkerLeaseRecord, now_ts: float, ttl_seconds: int) -> bool:
    last_seen = record.refreshed_at if record.refreshed_at is not None else record.acquired_at
    if last_seen is None:
        return False
    return now_ts - last_seen >= ttl_seconds
