from pathlib import Path

from vk_openclaw_service.domain.checkpoints import CheckpointState
from vk_openclaw_service.domain.pairing import PairingCodeRecord, hash_pairing_code
from vk_openclaw_service.infra.repositories.checkpoints import FileCheckpointRepository
from vk_openclaw_service.infra.repositories.dead_letters import FileDeadLetterRepository
from vk_openclaw_service.infra.repositories.pairing import FilePairingRepository


def test_file_checkpoint_repository_persists_state(tmp_path: Path) -> None:
    repository = FileCheckpointRepository(tmp_path / "checkpoints.json")
    state = CheckpointState(
        peer_id=42,
        last_seen_message_id=9,
        last_committed_message_id=7,
        status="idle",
        current_message_id=None,
        degradation_reason=None,
    )

    repository.save(state)
    reloaded = FileCheckpointRepository(tmp_path / "checkpoints.json")

    assert reloaded.get(42) == state


def test_file_pairing_repository_persists_codes_and_paired_peers(tmp_path: Path) -> None:
    repository = FilePairingRepository(tmp_path / "pairing.json")
    record = PairingCodeRecord(
        peer_id=42,
        code_hash=hash_pairing_code("ABC12345"),
        expires_at=__import__("datetime").datetime.fromisoformat("2026-03-16T20:00:00+00:00"),
        consumed_at=None,
    )

    repository.save_code(42, record)
    repository.mark_paired(42)
    reloaded = FilePairingRepository(tmp_path / "pairing.json")

    assert reloaded.get_code(42) == record
    assert reloaded.is_paired(42) is True
    assert reloaded.list_paired_peers() == [42]


def test_file_dead_letter_repository_persists_records(tmp_path: Path) -> None:
    repository = FileDeadLetterRepository(tmp_path / "dead_letters.json")

    record = repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    reloaded = FileDeadLetterRepository(tmp_path / "dead_letters.json")

    assert reloaded.list_dead_letters() == [record]
