"""Backlog-safe history polling service."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Iterable
from typing import Protocol

from vk_openclaw_service.domain.checkpoints import CheckpointState
from vk_openclaw_service.services.worker_service import WorkerService


@dataclass(frozen=True)
class HistoryMessage:
    message_id: int
    peer_id: int
    text: str
    outgoing: bool


class CheckpointRepository(Protocol):
    def get_or_create(self, peer_id: int) -> CheckpointState: ...


class PairingRepository(Protocol):
    def is_paired(self, peer_id: int) -> bool: ...


class PollingService:
    def __init__(
        self,
        *,
        checkpoint_repository: CheckpointRepository,
        pairing_repository: PairingRepository,
        worker_service: WorkerService,
        status_payload_factory: Callable[[], dict],
    ) -> None:
        self.checkpoint_repository = checkpoint_repository
        self.pairing_repository = pairing_repository
        self.worker_service = worker_service
        self.status_payload_factory = status_payload_factory

    def process_history(self, messages: Iterable[HistoryMessage]) -> int:
        processed = 0
        for item in sorted(messages, key=lambda message: message.message_id):
            state = self.checkpoint_repository.get_or_create(item.peer_id)
            if item.message_id <= state.last_committed_message_id:
                continue
            if item.outgoing and not _is_pair_command(item.text):
                continue
            self.worker_service.process_message(
                peer_id=item.peer_id,
                message_id=item.message_id,
                text=item.text,
                paired=self.pairing_repository.is_paired(item.peer_id),
                status_payload=self.status_payload_factory(),
            )
            processed += 1
        return processed


def _is_pair_command(text: str) -> bool:
    stripped = text.strip().lower()
    return stripped == "/pair" or stripped.startswith("/pair ")
