from vk_openclaw_service.infra.repositories.checkpoints import InMemoryCheckpointRepository
from vk_openclaw_service.infra.repositories.audit import InMemoryAuditRepository
from vk_openclaw_service.infra.vk.transport import VkDeliveryOutcome
from vk_openclaw_service.services.worker_service import WorkerService


def test_worker_service_commits_successful_ask_message() -> None:
    repository = InMemoryCheckpointRepository()
    audit_repository = InMemoryAuditRepository()
    sent: list[tuple[int, str]] = []
    service = WorkerService(
        checkpoint_repository=repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        reply_sender=lambda peer_id, text: sent.append((peer_id, text)),
        audit_repository=audit_repository,
    )

    result = service.process_message(
        peer_id=42,
        message_id=8,
        text="/ask hello",
        paired=True,
        status_payload={"mode": "plain"},
    )

    state = repository.get_or_create(42)
    assert result == {"action": "reply", "reply": "ran:hello"}
    assert sent == [(42, "ran:hello")]
    assert state.last_committed_message_id == 8
    assert state.status == "idle"
    assert audit_repository.events[-1]["event_type"] == "message_processed"


def test_worker_service_keeps_checkpoint_uncommitted_when_delivery_should_retry() -> None:
    repository = InMemoryCheckpointRepository()
    audit_repository = InMemoryAuditRepository()

    def failing_runner(prompt: str) -> str:
        raise TimeoutError("timed out")

    service = WorkerService(
        checkpoint_repository=repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.RETRY,
        openclaw_runner=failing_runner,
        reply_sender=lambda peer_id, text: None,
        audit_repository=audit_repository,
    )

    result = service.process_message(
        peer_id=42,
        message_id=8,
        text="/ask hello",
        paired=True,
        status_payload={"mode": "plain"},
    )

    state = repository.get_or_create(42)
    assert result == {"action": "retry", "reason": "delivery_retry_required"}
    assert state.last_committed_message_id == 0
    assert state.status == "degraded"
    assert audit_repository.events[-1]["event_type"] == "message_processing_failed"


def test_worker_service_retries_when_reply_delivery_fails_retryably() -> None:
    repository = InMemoryCheckpointRepository()
    audit_repository = InMemoryAuditRepository()

    def failing_sender(peer_id: int, text: str) -> None:
        raise TimeoutError("timed out")

    service = WorkerService(
        checkpoint_repository=repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.RETRY,
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        reply_sender=failing_sender,
        audit_repository=audit_repository,
    )

    result = service.process_message(
        peer_id=42,
        message_id=8,
        text="/ask hello",
        paired=True,
        status_payload={"mode": "plain"},
    )

    state = repository.get_or_create(42)
    assert result == {"action": "retry", "reason": "delivery_retry_required"}
    assert state.last_committed_message_id == 0
    assert state.status == "degraded"
    assert audit_repository.events[-1]["event_type"] == "message_delivery_retry"


def test_worker_service_returns_rate_limit_reply_when_limiter_blocks() -> None:
    repository = InMemoryCheckpointRepository()
    audit_repository = InMemoryAuditRepository()
    sent: list[tuple[int, str]] = []
    service = WorkerService(
        checkpoint_repository=repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        reply_sender=lambda peer_id, text: sent.append((peer_id, text)),
        audit_repository=audit_repository,
        rate_limiter=type("Limiter", (), {"allow": lambda self, **kwargs: False})(),
    )

    result = service.process_message(
        peer_id=42,
        message_id=9,
        text="/ask hello",
        paired=True,
        status_payload={"mode": "plain"},
    )

    assert result == {"action": "reply", "reply": "Rate limit exceeded. Try again later."}
    assert sent == [(42, "Rate limit exceeded. Try again later.")]


def test_worker_service_ignores_duplicate_message_when_replay_guard_blocks() -> None:
    repository = InMemoryCheckpointRepository()
    audit_repository = InMemoryAuditRepository()
    sent: list[tuple[int, str]] = []
    service = WorkerService(
        checkpoint_repository=repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        reply_sender=lambda peer_id, text: sent.append((peer_id, text)),
        audit_repository=audit_repository,
        replay_guard=type("Guard", (), {"claim": lambda self, **kwargs: False})(),
    )

    result = service.process_message(
        peer_id=42,
        message_id=10,
        text="/ask hello",
        paired=True,
        status_payload={"mode": "plain"},
    )

    assert result == {"action": "ignored", "reason": "duplicate_message"}
    assert sent == []
    assert audit_repository.events[-1]["event_type"] == "message_duplicate_skipped"


def test_worker_service_enqueues_retry_payload_on_retryable_failure() -> None:
    repository = InMemoryCheckpointRepository()
    audit_repository = InMemoryAuditRepository()
    retry_calls: list[dict[str, object]] = []

    def failing_runner(prompt: str) -> str:
        raise TimeoutError("timed out")

    service = WorkerService(
        checkpoint_repository=repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.RETRY,
        openclaw_runner=failing_runner,
        reply_sender=lambda peer_id, text: None,
        audit_repository=audit_repository,
        dead_letter_repository=type(
            "DeadLetterRepository",
            (),
            {"append_dead_letter": lambda self, **kwargs: kwargs},
        )(),
        retry_queue=type(
            "RetryQueue",
            (),
            {"enqueue_message": lambda self, **kwargs: retry_calls.append(kwargs)},
        )(),
    )

    result = service.process_message(
        peer_id=42,
        message_id=11,
        text="/ask hello",
        paired=True,
        status_payload={"mode": "plain"},
    )

    assert result == {"action": "retry", "reason": "delivery_retry_required"}
    assert retry_calls == [
        {
            "peer_id": 42,
            "message_id": 11,
            "text": "/ask hello",
            "paired": True,
            "reason": "delivery_retry_required",
            "attempt": 1,
        }
    ]


def test_worker_service_dead_letters_when_retry_budget_is_exhausted() -> None:
    repository = InMemoryCheckpointRepository()
    audit_repository = InMemoryAuditRepository()
    retry_calls: list[dict[str, object]] = []

    def failing_runner(prompt: str) -> str:
        raise TimeoutError("timed out")

    service = WorkerService(
        checkpoint_repository=repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.RETRY,
        openclaw_runner=failing_runner,
        reply_sender=lambda peer_id, text: None,
        audit_repository=audit_repository,
        dead_letter_repository=type(
            "DeadLetterRepository",
            (),
            {"append_dead_letter": lambda self, **kwargs: kwargs},
        )(),
        retry_queue=type(
            "RetryQueue",
            (),
            {"enqueue_message": lambda self, **kwargs: retry_calls.append(kwargs)},
        )(),
        retry_queue_max_attempts=2,
    )

    result = service.process_message(
        peer_id=42,
        message_id=12,
        text="/ask hello",
        paired=True,
        status_payload={"mode": "plain"},
        retry_attempt=2,
    )

    state = repository.get_or_create(42)
    assert result == {"action": "dead_letter", "reason": "retry_budget_exhausted"}
    assert retry_calls == []
    assert state.last_committed_message_id == 12
    assert state.status == "idle"
    assert audit_repository.events[-1]["event_type"] == "message_dead_lettered"
