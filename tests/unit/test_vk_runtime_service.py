from vk_openclaw_service.infra.repositories.checkpoints import InMemoryCheckpointRepository
from vk_openclaw_service.infra.repositories.pairing import InMemoryPairingRepository
from vk_openclaw_service.infra.vk.transport import VkDeliveryOutcome
from vk_openclaw_service.services.worker_service import WorkerService
from vk_openclaw_service.services.vk_runtime import LeaseLostError, VkRuntimeService
from vk_openclaw_service.workers.polling_service import HistoryMessage


class FakeVkClient:
    def __init__(self, history_by_peer: dict[int, list[HistoryMessage]]) -> None:
        self.history_by_peer = history_by_peer
        self.requested_peers: list[int] = []

    def get_history(self, peer_id: int) -> list[HistoryMessage]:
        self.requested_peers.append(peer_id)
        return self.history_by_peer.get(peer_id, [])


def test_vk_runtime_service_polls_all_allowed_peers() -> None:
    checkpoint_repository = InMemoryCheckpointRepository()
    pairing_repository = InMemoryPairingRepository()
    pairing_repository.mark_paired(42)
    pairing_repository.mark_paired(43)
    worker_service = WorkerService(
        checkpoint_repository=checkpoint_repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        reply_sender=lambda peer_id, text: 0,
    )
    vk_client = FakeVkClient(
        {
            42: [HistoryMessage(message_id=1, peer_id=42, text="/ask one", outgoing=False)],
            43: [HistoryMessage(message_id=2, peer_id=43, text="/ask two", outgoing=False)],
        }
    )

    service = VkRuntimeService(
        vk_client=vk_client,
        checkpoint_repository=checkpoint_repository,
        pairing_repository=pairing_repository,
        worker_service=worker_service,
        status_payload_factory=lambda: {"mode": "plain"},
        allowed_peers={42, 43},
    )

    processed = service.poll_once()

    assert processed == 0
    assert vk_client.requested_peers == [42, 43]
    assert checkpoint_repository.get_or_create(42).last_committed_message_id == 1
    assert checkpoint_repository.get_or_create(43).last_committed_message_id == 2


def test_vk_runtime_service_handles_empty_history() -> None:
    checkpoint_repository = InMemoryCheckpointRepository()
    pairing_repository = InMemoryPairingRepository()
    worker_service = WorkerService(
        checkpoint_repository=checkpoint_repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        reply_sender=lambda peer_id, text: 0,
    )
    vk_client = FakeVkClient({})

    service = VkRuntimeService(
        vk_client=vk_client,
        checkpoint_repository=checkpoint_repository,
        pairing_repository=pairing_repository,
        worker_service=worker_service,
        status_payload_factory=lambda: {"mode": "plain"},
        allowed_peers={42},
    )

    processed = service.poll_once()

    assert processed == 0
    assert vk_client.requested_peers == [42]


def test_vk_runtime_service_stops_when_heartbeat_reports_lost_lease() -> None:
    checkpoint_repository = InMemoryCheckpointRepository()
    pairing_repository = InMemoryPairingRepository()
    pairing_repository.mark_paired(42)
    pairing_repository.mark_paired(43)
    worker_service = WorkerService(
        checkpoint_repository=checkpoint_repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        reply_sender=lambda peer_id, text: 0,
    )
    vk_client = FakeVkClient(
        {
            42: [HistoryMessage(message_id=1, peer_id=42, text="/ask one", outgoing=False)],
            43: [HistoryMessage(message_id=2, peer_id=43, text="/ask two", outgoing=False)],
        }
    )
    heartbeats = iter([True, False])

    service = VkRuntimeService(
        vk_client=vk_client,
        checkpoint_repository=checkpoint_repository,
        pairing_repository=pairing_repository,
        worker_service=worker_service,
        status_payload_factory=lambda: {"mode": "plain"},
        allowed_peers={42, 43},
    )

    try:
        service.poll_once(heartbeat=lambda: next(heartbeats))
    except LeaseLostError as exc:
        assert str(exc) == "worker lease lost during polling"
    else:
        raise AssertionError("expected LeaseLostError")

    assert vk_client.requested_peers == [42]
    assert checkpoint_repository.get_or_create(42).last_committed_message_id == 1
    assert checkpoint_repository.get_or_create(43).last_committed_message_id == 0
