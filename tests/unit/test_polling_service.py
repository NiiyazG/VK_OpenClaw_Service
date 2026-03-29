from vk_openclaw_service.infra.repositories.checkpoints import InMemoryCheckpointRepository
from vk_openclaw_service.infra.repositories.pairing import InMemoryPairingRepository
from vk_openclaw_service.infra.vk.transport import VkDeliveryOutcome
from vk_openclaw_service.services.worker_service import WorkerService
from vk_openclaw_service.workers.polling_service import HistoryMessage, PollingService


def test_polling_service_processes_backlog_larger_than_ten_messages() -> None:
    checkpoint_repository = InMemoryCheckpointRepository()
    pairing_repository = InMemoryPairingRepository()
    pairing_repository.mark_paired(42)

    processed_prompts: list[str] = []
    sent: list[tuple[int, str]] = []
    worker_service = WorkerService(
        checkpoint_repository=checkpoint_repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: processed_prompts.append(prompt) or f"ran:{prompt}",
        reply_sender=lambda peer_id, text: sent.append((peer_id, text)),
    )

    # Simulate a non-first-run peer so the worker processes backlog as usual.
    checkpoint_repository.save(
        checkpoint_repository.get_or_create(42).__class__(
            peer_id=42,
            last_seen_message_id=1,
            last_committed_message_id=0,
            status="idle",
            current_message_id=None,
            degradation_reason=None,
        )
    )
    messages = [HistoryMessage(message_id=idx, peer_id=42, text=f"/ask msg-{idx}", outgoing=False) for idx in range(1, 13)]

    service = PollingService(
        checkpoint_repository=checkpoint_repository,
        pairing_repository=pairing_repository,
        worker_service=worker_service,
        status_payload_factory=lambda: {"mode": "plain"},
    )

    processed = service.process_history(messages)
    state = checkpoint_repository.get_or_create(42)

    assert processed == 12
    assert len(processed_prompts) == 12
    assert state.last_committed_message_id == 12


def test_polling_service_first_run_skips_initial_history_backlog() -> None:
    checkpoint_repository = InMemoryCheckpointRepository()
    pairing_repository = InMemoryPairingRepository()

    processed_prompts: list[str] = []
    sent: list[tuple[int, str]] = []
    worker_service = WorkerService(
        checkpoint_repository=checkpoint_repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: processed_prompts.append(prompt) or f"ran:{prompt}",
        reply_sender=lambda peer_id, text: sent.append((peer_id, text)),
    )

    messages = [HistoryMessage(message_id=idx, peer_id=42, text="/status", outgoing=False) for idx in range(1, 13)]
    service = PollingService(
        checkpoint_repository=checkpoint_repository,
        pairing_repository=pairing_repository,
        worker_service=worker_service,
        status_payload_factory=lambda: {"mode": "plain"},
    )

    processed = service.process_history(messages)
    state = checkpoint_repository.get_or_create(42)

    assert processed == 0
    assert processed_prompts == []
    assert sent == []
    assert state.last_committed_message_id == 12
    assert state.last_seen_message_id == 12


def test_polling_service_processes_new_messages_after_first_run_skip() -> None:
    checkpoint_repository = InMemoryCheckpointRepository()
    pairing_repository = InMemoryPairingRepository()
    pairing_repository.mark_paired(42)

    processed_prompts: list[str] = []
    sent: list[tuple[int, str]] = []
    worker_service = WorkerService(
        checkpoint_repository=checkpoint_repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: processed_prompts.append(prompt) or f"ran:{prompt}",
        reply_sender=lambda peer_id, text: sent.append((peer_id, text)),
    )
    service = PollingService(
        checkpoint_repository=checkpoint_repository,
        pairing_repository=pairing_repository,
        worker_service=worker_service,
        status_payload_factory=lambda: {"mode": "plain"},
    )

    initial = [HistoryMessage(message_id=idx, peer_id=42, text="/status", outgoing=False) for idx in range(1, 4)]
    processed_initial = service.process_history(initial)
    assert processed_initial == 0

    next_cycle = [HistoryMessage(message_id=idx, peer_id=42, text=f"/ask msg-{idx}", outgoing=False) for idx in range(1, 6)]
    processed_next = service.process_history(next_cycle)
    state = checkpoint_repository.get_or_create(42)

    assert processed_next == 2
    assert processed_prompts == ["msg-4", "msg-5"]
    assert state.last_committed_message_id == 5


def test_polling_service_skips_outgoing_and_already_committed_messages() -> None:
    checkpoint_repository = InMemoryCheckpointRepository()
    pairing_repository = InMemoryPairingRepository()
    pairing_repository.mark_paired(42)
    checkpoint_repository.save(
        checkpoint_repository.get_or_create(42).__class__(
            peer_id=42,
            last_seen_message_id=5,
            last_committed_message_id=5,
            status="idle",
            current_message_id=None,
            degradation_reason=None,
        )
    )

    processed_prompts: list[str] = []
    sent: list[tuple[int, str]] = []
    worker_service = WorkerService(
        checkpoint_repository=checkpoint_repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: processed_prompts.append(prompt) or f"ran:{prompt}",
        reply_sender=lambda peer_id, text: sent.append((peer_id, text)),
    )

    messages = [
        HistoryMessage(message_id=4, peer_id=42, text="/ask old", outgoing=False),
        HistoryMessage(message_id=5, peer_id=42, text="/ask committed", outgoing=False),
        HistoryMessage(message_id=6, peer_id=42, text="/ask outgoing", outgoing=True),
        HistoryMessage(message_id=7, peer_id=42, text="/ask fresh", outgoing=False),
    ]

    service = PollingService(
        checkpoint_repository=checkpoint_repository,
        pairing_repository=pairing_repository,
        worker_service=worker_service,
        status_payload_factory=lambda: {"mode": "plain"},
    )

    processed = service.process_history(messages)
    state = checkpoint_repository.get_or_create(42)

    assert processed == 1
    assert processed_prompts == ["fresh"]
    assert state.last_committed_message_id == 7


def test_polling_service_first_run_skips_outgoing_pair_command_from_history() -> None:
    checkpoint_repository = InMemoryCheckpointRepository()
    pairing_repository = InMemoryPairingRepository()

    sent: list[tuple[int, str]] = []
    worker_service = WorkerService(
        checkpoint_repository=checkpoint_repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        reply_sender=lambda peer_id, text: sent.append((peer_id, text)),
        pairing_verifier=lambda peer_id, code: {"status": "paired"},
    )

    messages = [
        HistoryMessage(message_id=1, peer_id=42, text="/pair ABC12345", outgoing=True),
    ]

    service = PollingService(
        checkpoint_repository=checkpoint_repository,
        pairing_repository=pairing_repository,
        worker_service=worker_service,
        status_payload_factory=lambda: {"mode": "plain"},
    )

    processed = service.process_history(messages)
    state = checkpoint_repository.get_or_create(42)

    assert processed == 0
    assert sent == []
    assert state.last_committed_message_id == 1


def test_polling_service_allows_outgoing_pair_command_after_initial_sync() -> None:
    checkpoint_repository = InMemoryCheckpointRepository()
    pairing_repository = InMemoryPairingRepository()
    checkpoint_repository.save(
        checkpoint_repository.get_or_create(42).__class__(
            peer_id=42,
            last_seen_message_id=1,
            last_committed_message_id=0,
            status="idle",
            current_message_id=None,
            degradation_reason=None,
        )
    )

    sent: list[tuple[int, str]] = []
    worker_service = WorkerService(
        checkpoint_repository=checkpoint_repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        reply_sender=lambda peer_id, text: sent.append((peer_id, text)),
        pairing_verifier=lambda peer_id, code: {"status": "paired"},
    )

    messages = [HistoryMessage(message_id=1, peer_id=42, text="/pair ABC12345", outgoing=True)]
    service = PollingService(
        checkpoint_repository=checkpoint_repository,
        pairing_repository=pairing_repository,
        worker_service=worker_service,
        status_payload_factory=lambda: {"mode": "plain"},
    )

    processed = service.process_history(messages)
    state = checkpoint_repository.get_or_create(42)

    assert processed == 1
    assert sent == [(42, "Pairing successful.")]
    assert state.last_committed_message_id == 1
