from vk_openclaw_service.infra.repositories.checkpoints import InMemoryCheckpointRepository
from vk_openclaw_service.infra.vk.transport import VkDeliveryOutcome
from vk_openclaw_service.services.worker_service import WorkerService


def test_worker_cycle_commits_successful_message() -> None:
    repository = InMemoryCheckpointRepository()
    sent: list[tuple[int, str]] = []
    service = WorkerService(
        checkpoint_repository=repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        reply_sender=lambda peer_id, text: sent.append((peer_id, text)),
    )

    result = service.process_message(
        peer_id=42,
        message_id=5,
        text="/ask hello",
        paired=True,
        status_payload={"mode": "plain"},
    )

    state = repository.get_or_create(42)
    assert result == {"action": "reply", "reply": "ran:hello"}
    assert sent == [(42, "ran:hello")]
    assert state.last_committed_message_id == 5


def test_worker_cycle_marks_retryable_failure_as_degraded() -> None:
    repository = InMemoryCheckpointRepository()

    def failing_runner(prompt: str) -> str:
        raise TimeoutError("timed out")

    service = WorkerService(
        checkpoint_repository=repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.RETRY,
        openclaw_runner=failing_runner,
        reply_sender=lambda peer_id, text: None,
    )

    result = service.process_message(
        peer_id=42,
        message_id=5,
        text="/ask hello",
        paired=True,
        status_payload={"mode": "plain"},
    )

    state = repository.get_or_create(42)
    assert result == {"action": "retry", "reason": "delivery_retry_required"}
    assert state.last_committed_message_id == 0
    assert state.status == "degraded"
