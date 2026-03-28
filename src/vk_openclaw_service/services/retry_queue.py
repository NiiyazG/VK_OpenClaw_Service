"""Retry queue for transiently failed message processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Protocol, cast


class RetryQueueStore(Protocol):
    def enqueue(self, key: str, payload: dict[str, object]) -> None: ...
    def dequeue_ready(self, key: str, now_ts: float) -> dict[str, object] | None: ...


@dataclass
class InMemoryRetryQueueStore:
    items: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def enqueue(self, key: str, payload: dict[str, object]) -> None:
        self.items.append((key, payload))

    def dequeue_ready(self, key: str, now_ts: float) -> dict[str, object] | None:
        for index, (item_key, payload) in enumerate(self.items):
            available_at = cast(float, payload["available_at"])
            if item_key == key and available_at <= now_ts:
                self.items.pop(index)
                return payload
        return None


@dataclass(frozen=True)
class RetryQueue:
    store: RetryQueueStore
    key: str = "vk-openclaw:retry"
    base_backoff_seconds: float = 5.0
    max_backoff_seconds: float = 60.0

    def enqueue_message(
        self,
        *,
        peer_id: int,
        message_id: int,
        text: str,
        paired: bool,
        reason: str,
        attempt: int = 1,
        now_ts: float | None = None,
    ) -> None:
        current_time = now_ts if now_ts is not None else time()
        backoff_seconds = min(self.base_backoff_seconds * (2 ** max(attempt - 1, 0)), self.max_backoff_seconds)
        self.store.enqueue(
            self.key,
            {
                "peer_id": peer_id,
                "message_id": message_id,
                "text": text,
                "paired": paired,
                "reason": reason,
                "attempt": attempt,
                "available_at": current_time + backoff_seconds,
            },
        )

    def dequeue_message(self, *, now_ts: float | None = None) -> dict[str, object] | None:
        current_time = now_ts if now_ts is not None else time()
        return self.store.dequeue_ready(self.key, current_time)
