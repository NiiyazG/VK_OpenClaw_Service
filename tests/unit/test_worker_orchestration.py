from vk_openclaw_service.domain.checkpoints import CheckpointState
from vk_openclaw_service.infra.vk.transport import VkDeliveryOutcome
from vk_openclaw_service.workers.orchestration import finalize_message_processing


def test_processed_message_commits_checkpoint() -> None:
    state = CheckpointState(
        peer_id=42,
        last_seen_message_id=10,
        last_committed_message_id=7,
        status="processing",
        current_message_id=8,
    )

    updated = finalize_message_processing(
        state,
        handler_failed=False,
        delivery_outcome=None,
        dead_letter_persisted=False,
    )

    assert updated.last_committed_message_id == 8
    assert updated.status == "idle"


def test_retryable_delivery_failure_keeps_checkpoint_uncommitted() -> None:
    state = CheckpointState(
        peer_id=42,
        last_seen_message_id=10,
        last_committed_message_id=7,
        status="processing",
        current_message_id=8,
    )

    updated = finalize_message_processing(
        state,
        handler_failed=True,
        delivery_outcome=VkDeliveryOutcome.RETRY,
        dead_letter_persisted=False,
    )

    assert updated.last_committed_message_id == 7
    assert updated.status == "degraded"
    assert updated.degradation_reason == "delivery_retry_required"


def test_rejected_delivery_commits_failed_message() -> None:
    state = CheckpointState(
        peer_id=42,
        last_seen_message_id=10,
        last_committed_message_id=7,
        status="processing",
        current_message_id=8,
    )

    updated = finalize_message_processing(
        state,
        handler_failed=True,
        delivery_outcome=VkDeliveryOutcome.REJECT,
        dead_letter_persisted=False,
    )

    assert updated.last_committed_message_id == 8
    assert updated.status == "idle"


def test_dead_letter_commits_after_persistence() -> None:
    state = CheckpointState(
        peer_id=42,
        last_seen_message_id=10,
        last_committed_message_id=7,
        status="processing",
        current_message_id=8,
    )

    updated = finalize_message_processing(
        state,
        handler_failed=True,
        delivery_outcome=None,
        dead_letter_persisted=True,
    )

    assert updated.last_committed_message_id == 8
    assert updated.status == "idle"
