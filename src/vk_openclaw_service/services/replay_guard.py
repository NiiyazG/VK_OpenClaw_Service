"""Replay protection for incoming message processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ReplayStore(Protocol):
    def claim_once(self, key: str, ttl_seconds: int) -> bool: ...


@dataclass
class InMemoryReplayStore:
    claims: set[str] = field(default_factory=set)

    def claim_once(self, key: str, ttl_seconds: int) -> bool:
        del ttl_seconds
        if key in self.claims:
            return False
        self.claims.add(key)
        return True


@dataclass(frozen=True)
class ReplayGuard:
    store: ReplayStore
    ttl_seconds: int = 300

    def claim(self, *, peer_id: int, message_id: int) -> bool:
        return self.store.claim_once(f"replay:{peer_id}:{message_id}", self.ttl_seconds)
