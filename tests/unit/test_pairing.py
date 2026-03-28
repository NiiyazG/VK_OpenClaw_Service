from datetime import UTC, datetime, timedelta

from vk_openclaw_service.domain.pairing import (
    PairingCodeRecord,
    consume_pairing_code,
    generate_pairing_code,
    hash_pairing_code,
    verify_pairing_code,
)


def test_generate_pairing_code_returns_plaintext_and_hashed_record() -> None:
    now = datetime.now(UTC)

    plain_code, record = generate_pairing_code(peer_id=42, ttl_seconds=600, now=now)

    assert len(plain_code) == 8
    assert plain_code.isalnum()
    assert record.peer_id == 42
    assert record.code_hash != plain_code
    assert record.expires_at == now + timedelta(seconds=600)
    assert record.consumed_at is None


def test_hash_pairing_code_is_deterministic() -> None:
    assert hash_pairing_code("ABC12345") == hash_pairing_code("ABC12345")


def test_verify_pairing_code_accepts_matching_unexpired_code() -> None:
    now = datetime.now(UTC)
    record = PairingCodeRecord(
        peer_id=42,
        code_hash=hash_pairing_code("ABC12345"),
        expires_at=now + timedelta(minutes=5),
        consumed_at=None,
    )

    assert verify_pairing_code(record, "ABC12345", now=now) is True


def test_verify_pairing_code_rejects_consumed_or_expired_code() -> None:
    now = datetime.now(UTC)
    consumed = PairingCodeRecord(
        peer_id=42,
        code_hash=hash_pairing_code("ABC12345"),
        expires_at=now + timedelta(minutes=5),
        consumed_at=now,
    )
    expired = PairingCodeRecord(
        peer_id=42,
        code_hash=hash_pairing_code("ABC12345"),
        expires_at=now - timedelta(seconds=1),
        consumed_at=None,
    )

    assert verify_pairing_code(consumed, "ABC12345", now=now) is False
    assert verify_pairing_code(expired, "ABC12345", now=now) is False


def test_consume_pairing_code_marks_record_consumed() -> None:
    now = datetime.now(UTC)
    record = PairingCodeRecord(
        peer_id=42,
        code_hash=hash_pairing_code("ABC12345"),
        expires_at=now + timedelta(minutes=5),
        consumed_at=None,
    )

    consumed = consume_pairing_code(record, "ABC12345", now=now)

    assert consumed.consumed_at == now


def test_consume_pairing_code_rejects_invalid_value() -> None:
    now = datetime.now(UTC)
    record = PairingCodeRecord(
        peer_id=42,
        code_hash=hash_pairing_code("ABC12345"),
        expires_at=now + timedelta(minutes=5),
        consumed_at=None,
    )

    try:
        consume_pairing_code(record, "ZZZ99999", now=now)
    except ValueError as exc:
        assert "invalid" in str(exc)
    else:
        raise AssertionError("expected ValueError")
