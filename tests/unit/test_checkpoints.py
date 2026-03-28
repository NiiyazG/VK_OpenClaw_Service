from vk_openclaw_service.domain.checkpoints import (
    CheckpointState,
    MessageDisposition,
    ProcessingDecision,
    apply_message_result,
    begin_processing,
    observe_message,
)


def test_observe_message_updates_last_seen_without_committing() -> None:
    state = CheckpointState.empty(peer_id=42)

    updated = observe_message(state, message_id=10)

    assert updated.peer_id == 42
    assert updated.last_seen_message_id == 10
    assert updated.last_committed_message_id == 0
    assert updated.status == "idle"


def test_begin_processing_marks_state_processing() -> None:
    state = CheckpointState(peer_id=42, last_seen_message_id=10, last_committed_message_id=7, status="idle")

    updated = begin_processing(state, message_id=8)

    assert updated.current_message_id == 8
    assert updated.status == "processing"
    assert updated.last_committed_message_id == 7


def test_successful_reply_commits_message() -> None:
    state = CheckpointState(peer_id=42, last_seen_message_id=10, last_committed_message_id=7, status="processing", current_message_id=8)

    updated = apply_message_result(state, ProcessingDecision(disposition=MessageDisposition.PROCESSED))

    assert updated.last_committed_message_id == 8
    assert updated.current_message_id is None
    assert updated.status == "idle"
    assert updated.degradation_reason is None


def test_reply_send_failure_does_not_commit_message() -> None:
    state = CheckpointState(peer_id=42, last_seen_message_id=10, last_committed_message_id=7, status="processing", current_message_id=8)

    updated = apply_message_result(
        state,
        ProcessingDecision(
            disposition=MessageDisposition.RETRY,
            reason="reply_send_failed",
            degrade_worker=True,
        ),
    )

    assert updated.last_committed_message_id == 7
    assert updated.current_message_id is None
    assert updated.status == "degraded"
    assert updated.degradation_reason == "reply_send_failed"


def test_dead_letter_commits_only_after_persisted_dead_letter() -> None:
    state = CheckpointState(peer_id=42, last_seen_message_id=10, last_committed_message_id=7, status="processing", current_message_id=8)

    updated = apply_message_result(
        state,
        ProcessingDecision(
            disposition=MessageDisposition.DEAD_LETTERED,
            reason="retry_budget_exhausted",
            dead_letter_persisted=True,
        ),
    )

    assert updated.last_committed_message_id == 8
    assert updated.current_message_id is None
    assert updated.status == "idle"


def test_dead_letter_without_persistence_is_rejected() -> None:
    state = CheckpointState(peer_id=42, last_seen_message_id=10, last_committed_message_id=7, status="processing", current_message_id=8)

    try:
        apply_message_result(
            state,
            ProcessingDecision(
                disposition=MessageDisposition.DEAD_LETTERED,
                reason="retry_budget_exhausted",
                dead_letter_persisted=False,
            ),
        )
    except ValueError as exc:
        assert "dead-letter" in str(exc)
    else:
        raise AssertionError("expected ValueError")
