from datetime import UTC, datetime, timedelta

from vk_openclaw_service.domain.pairing import PairingCodeRecord, hash_pairing_code
from vk_openclaw_service.infra.repositories.pairing import InMemoryPairingRepository


def test_repository_stores_and_reads_pairing_record() -> None:
    repository = InMemoryPairingRepository()
    record = PairingCodeRecord(
        peer_id=42,
        code_hash=hash_pairing_code("ABC12345"),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        consumed_at=None,
    )

    repository.save_code(42, record)

    assert repository.get_code(42) == record


def test_repository_tracks_paired_peers() -> None:
    repository = InMemoryPairingRepository()

    assert repository.is_paired(42) is False

    repository.mark_paired(42)

    assert repository.is_paired(42) is True
