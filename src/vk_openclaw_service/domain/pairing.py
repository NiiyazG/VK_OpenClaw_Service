"""One-time pairing code generation and verification."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import choice
from string import ascii_uppercase, digits


PAIRING_ALPHABET = ascii_uppercase + digits
PAIRING_CODE_LENGTH = 8


@dataclass(frozen=True)
class PairingCodeRecord:
    peer_id: int
    code_hash: str
    expires_at: datetime
    consumed_at: datetime | None


def generate_pairing_code(
    peer_id: int,
    ttl_seconds: int,
    *,
    now: datetime | None = None,
) -> tuple[str, PairingCodeRecord]:
    issued_at = now or datetime.now(UTC)
    code = "".join(choice(PAIRING_ALPHABET) for _ in range(PAIRING_CODE_LENGTH))
    return code, PairingCodeRecord(
        peer_id=peer_id,
        code_hash=hash_pairing_code(code),
        expires_at=issued_at + timedelta(seconds=ttl_seconds),
        consumed_at=None,
    )


def hash_pairing_code(code: str) -> str:
    return sha256(code.encode("utf-8")).hexdigest()


def verify_pairing_code(record: PairingCodeRecord, candidate: str, *, now: datetime | None = None) -> bool:
    checked_at = now or datetime.now(UTC)
    return (
        record.consumed_at is None
        and checked_at <= record.expires_at
        and hash_pairing_code(candidate) == record.code_hash
    )


def consume_pairing_code(
    record: PairingCodeRecord,
    candidate: str,
    *,
    now: datetime | None = None,
) -> PairingCodeRecord:
    consumed_at = now or datetime.now(UTC)
    if not verify_pairing_code(record, candidate, now=consumed_at):
        raise ValueError("invalid pairing code")
    return replace(record, consumed_at=consumed_at)
