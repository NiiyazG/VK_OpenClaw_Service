"""VK runtime service built on polling and worker services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from vk_openclaw_service.infra.vk.client import VkClient
from vk_openclaw_service.services.worker_service import WorkerService
from vk_openclaw_service.workers.polling_service import PollingService


class CheckpointRepository(Protocol):
    def get_or_create(self, peer_id: int): ...


class PairingRepository(Protocol):
    def is_paired(self, peer_id: int) -> bool: ...


class LeaseLostError(RuntimeError):
    """Raised when worker lease ownership is lost during a polling cycle."""


class VkRuntimeService:
    def __init__(
        self,
        *,
        vk_client: VkClient,
        checkpoint_repository: CheckpointRepository,
        pairing_repository: PairingRepository,
        worker_service: WorkerService,
        status_payload_factory: Callable[[], dict],
        allowed_peers: set[int],
    ) -> None:
        self.vk_client = vk_client
        self.allowed_peers = allowed_peers
        self.polling_service = PollingService(
            checkpoint_repository=checkpoint_repository,
            pairing_repository=pairing_repository,
            worker_service=worker_service,
            status_payload_factory=status_payload_factory,
        )

    def poll_once(self, heartbeat: Callable[[], bool] | None = None) -> int:
        processed = 0
        for peer_id in sorted(self.allowed_peers):
            if heartbeat is not None and not heartbeat():
                raise LeaseLostError("worker lease lost during polling")
            history = self.vk_client.get_history(peer_id)
            processed += self.polling_service.process_history(history)
        return processed
