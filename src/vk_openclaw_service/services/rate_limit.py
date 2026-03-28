"""Rate limiting services for costly command paths."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Protocol


class CounterStore(Protocol):
    def increment(self, key: str, ttl_seconds: int) -> int: ...


@dataclass
class InMemoryCounterStore:
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def increment(self, key: str, ttl_seconds: int) -> int:
        del ttl_seconds
        self.counters[key] += 1
        return self.counters[key]


@dataclass(frozen=True)
class FixedWindowRateLimiter:
    store: CounterStore
    limit: int
    window_seconds: int = 60

    def allow(self, *, peer_id: int, bucket: str) -> bool:
        current = self.store.increment(f"rate:{bucket}:{peer_id}", self.window_seconds)
        return current <= self.limit
