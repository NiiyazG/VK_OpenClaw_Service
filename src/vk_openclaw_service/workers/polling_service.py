"""Backlog-safe history polling service."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from collections.abc import Callable, Iterable
from typing import Protocol

from vk_openclaw_service.core.logging import get_worker_logger, log_event
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
    def save(self, state: CheckpointState) -> None: ...


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
        logger: logging.Logger | None = None,
    ) -> None:
        self.checkpoint_repository = checkpoint_repository
        self.pairing_repository = pairing_repository
        self.worker_service = worker_service
        self.status_payload_factory = status_payload_factory
        self.logger = logger or get_worker_logger()

    def process_history(self, messages: Iterable[HistoryMessage]) -> int:
        sorted_messages = sorted(messages, key=lambda message: message.message_id)
        if not sorted_messages:
            return 0

        peer_last_message_id: dict[int, int] = {}
        peer_message_counts: dict[int, int] = {}
        for message in sorted_messages:
            peer_last_message_id[message.peer_id] = max(peer_last_message_id.get(message.peer_id, 0), message.message_id)
            peer_message_counts[message.peer_id] = peer_message_counts.get(message.peer_id, 0) + 1

        processed = 0
        first_run_skipped_peers: set[int] = set()
        for item in sorted_messages:
            state = self.checkpoint_repository.get_or_create(item.peer_id)
            if (
                item.peer_id not in first_run_skipped_peers
                and state.last_seen_message_id == 0
                and state.last_committed_message_id == 0
            ):
                last_id = peer_last_message_id[item.peer_id]
                self.checkpoint_repository.save(
                    replace(
                        state,
                        last_seen_message_id=last_id,
                        last_committed_message_id=last_id,
                        status="idle",
                        current_message_id=None,
                        degradation_reason=None,
                    )
                )
                first_run_skipped_peers.add(item.peer_id)
                log_event(
                    self.logger,
                    "worker_backlog_skipped_on_first_run",
                    peer_id=item.peer_id,
                    skipped_count=peer_message_counts.get(item.peer_id, 0),
                    last_message_id=last_id,
                )
                continue

            if item.peer_id in first_run_skipped_peers:
                continue
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
