"""Retry queue draining for transient worker failures."""

from __future__ import annotations

from collections.abc import Callable
from time import time
from typing import Protocol

from vk_openclaw_service.domain.checkpoints import CheckpointState
from vk_openclaw_service.services.worker_service import WorkerService


class CheckpointRepository(Protocol):
    def get_or_create(self, peer_id: int) -> CheckpointState: ...


class RetryQueue(Protocol):
    def dequeue_message(self, *, now_ts: float | None = None) -> dict[str, object] | None: ...


class RetryDrainer:
    def __init__(
        self,
        *,
        retry_queue: RetryQueue,
        checkpoint_repository: CheckpointRepository,
        worker_service: WorkerService,
        status_payload_factory: Callable[[], dict],
        time_provider: Callable[[], float] = time,
    ) -> None:
        self.retry_queue = retry_queue
        self.checkpoint_repository = checkpoint_repository
        self.worker_service = worker_service
        self.status_payload_factory = status_payload_factory
        self.time_provider = time_provider

    def drain_once(self, *, limit: int = 50) -> int:
        processed = 0
        for _ in range(limit):
            payload = self.retry_queue.dequeue_message(now_ts=self.time_provider())
            if payload is None:
                break
            peer_id = _payload_int(payload, "peer_id")
            message_id = _payload_int(payload, "message_id")
            state = self.checkpoint_repository.get_or_create(peer_id)
            if message_id <= state.last_committed_message_id:
                continue
            self.worker_service.process_message(
                peer_id=peer_id,
                message_id=message_id,
                text=_payload_str(payload, "text"),
                paired=_payload_bool(payload, "paired"),
                status_payload=self.status_payload_factory(),
                skip_replay_guard=True,
                retry_attempt=_payload_optional_int(payload, "attempt") or 1,
            )
            processed += 1
        return processed


def _payload_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"invalid_retry_payload_{key}")
    return value


def _payload_optional_int(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"invalid_retry_payload_{key}")
    return value


def _payload_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"invalid_retry_payload_{key}")
    return value


def _payload_bool(payload: dict[str, object], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"invalid_retry_payload_{key}")
    return value
