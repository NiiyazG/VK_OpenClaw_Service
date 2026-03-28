from vk_openclaw_service.domain.checkpoints import CheckpointState
from vk_openclaw_service.infra.repositories.checkpoints import InMemoryCheckpointRepository


def test_checkpoint_repository_stores_and_reads_state() -> None:
    repository = InMemoryCheckpointRepository()
    state = CheckpointState(
        peer_id=42,
        last_seen_message_id=10,
        last_committed_message_id=8,
        status="idle",
        current_message_id=None,
        degradation_reason=None,
    )

    repository.save(state)

    assert repository.get(42) == state


def test_checkpoint_repository_returns_empty_state_for_unknown_peer() -> None:
    repository = InMemoryCheckpointRepository()

    state = repository.get_or_create(42)

    assert state.peer_id == 42
    assert state.last_seen_message_id == 0
    assert state.last_committed_message_id == 0
