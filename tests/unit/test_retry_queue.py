from vk_openclaw_service.infra.repositories.checkpoints import InMemoryCheckpointRepository
from vk_openclaw_service.infra.vk.transport import VkDeliveryOutcome
from vk_openclaw_service.services.retry_drainer import RetryDrainer
from vk_openclaw_service.services.retry_queue import InMemoryRetryQueueStore, RetryQueue
from vk_openclaw_service.services.worker_service import WorkerService


def test_retry_queue_enqueues_message_payload() -> None:
    store = InMemoryRetryQueueStore()
    queue = RetryQueue(store=store, key="vk-openclaw:retry", base_backoff_seconds=5.0, max_backoff_seconds=60.0)

    queue.enqueue_message(
        peer_id=42,
        message_id=8,
        text="/ask hello",
        paired=True,
        reason="delivery_retry_required",
        attempt=1,
        now_ts=100.0,
    )

    assert store.items == [
        (
            "vk-openclaw:retry",
            {
                "peer_id": 42,
                "message_id": 8,
                "text": "/ask hello",
                "paired": True,
                "reason": "delivery_retry_required",
                "attempt": 1,
                "available_at": 105.0,
            },
        )
    ]


def test_retry_queue_dequeues_message_payload() -> None:
    store = InMemoryRetryQueueStore()
    queue = RetryQueue(store=store, key="vk-openclaw:retry")
    queue.enqueue_message(
        peer_id=42,
        message_id=8,
        text="/ask hello",
        paired=True,
        reason="delivery_retry_required",
        now_ts=100.0,
    )

    assert queue.dequeue_message(now_ts=104.0) is None
    payload = queue.dequeue_message(now_ts=105.0)

    assert payload == {
        "peer_id": 42,
        "message_id": 8,
        "text": "/ask hello",
        "paired": True,
        "reason": "delivery_retry_required",
        "attempt": 1,
        "available_at": 105.0,
    }
    assert queue.dequeue_message(now_ts=106.0) is None


def test_retry_drainer_replays_queued_message() -> None:
    checkpoint_repository = InMemoryCheckpointRepository()
    sent: list[tuple[int, str]] = []
    queue = RetryQueue(store=InMemoryRetryQueueStore(), key="vk-openclaw:retry")
    queue.enqueue_message(
        peer_id=42,
        message_id=8,
        text="/ask hello",
        paired=True,
        reason="delivery_retry_required",
        now_ts=100.0,
    )
    worker_service = WorkerService(
        checkpoint_repository=checkpoint_repository,
        delivery_classifier=lambda exc: VkDeliveryOutcome.REJECT,
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        reply_sender=lambda peer_id, text: sent.append((peer_id, text)),
    )
    drainer = RetryDrainer(
        retry_queue=queue,
        checkpoint_repository=checkpoint_repository,
        worker_service=worker_service,
        status_payload_factory=lambda: {"mode": "plain"},
        time_provider=lambda: 105.0,
    )

    processed = drainer.drain_once()

    assert processed == 1
    assert sent == [(42, "ran:hello")]


def test_retry_queue_uses_exponential_backoff_up_to_cap() -> None:
    store = InMemoryRetryQueueStore()
    queue = RetryQueue(store=store, key="vk-openclaw:retry", base_backoff_seconds=5.0, max_backoff_seconds=12.0)

    queue.enqueue_message(
        peer_id=42,
        message_id=8,
        text="/ask hello",
        paired=True,
        reason="delivery_retry_required",
        attempt=3,
        now_ts=100.0,
    )

    payload = queue.dequeue_message(now_ts=112.0)

    assert payload is not None
    assert payload["available_at"] == 112.0
