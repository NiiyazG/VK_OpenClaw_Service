"""In-memory pairing service for the initial API implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from fastapi import HTTPException, status

from vk_openclaw_service.domain.pairing import PairingCodeRecord, consume_pairing_code, generate_pairing_code
from vk_openclaw_service.infra.repositories.pairing import InMemoryPairingRepository


class PairingRepository(Protocol):
    def save_code(self, peer_id: int, record: PairingCodeRecord) -> None: ...
    def get_code(self, peer_id: int) -> PairingCodeRecord | None: ...
    def mark_paired(self, peer_id: int) -> None: ...
    def is_paired(self, peer_id: int) -> bool: ...
    def list_paired_peers(self) -> list[int]: ...


class AuditRepository(Protocol):
    def append_event(
        self,
        *,
        event_type: str,
        peer_id: int | None,
        status: str,
        details: dict[str, object],
    ) -> object: ...


class PairingService:
    def __init__(
        self,
        repository: PairingRepository | None = None,
        audit_repository: AuditRepository | None = None,
        *,
        allowed_peers: set[int] | None = None,
        ttl_seconds: int = 600,
    ) -> None:
        self.repository = repository or InMemoryPairingRepository()
        self.audit_repository = audit_repository
        self.allowed_peers = allowed_peers or {42}
        self.ttl_seconds = ttl_seconds

    def create_code(self, peer_id: int) -> dict:
        if peer_id not in self.allowed_peers:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="peer_not_allowed")
        code, record = generate_pairing_code(peer_id=peer_id, ttl_seconds=self.ttl_seconds, now=datetime.now(UTC))
        self.repository.save_code(peer_id, record)
        if self.audit_repository is not None:
            self.audit_repository.append_event(
                event_type="pairing_code_created",
                peer_id=peer_id,
                status="ok",
                details={"peer_id": peer_id, "expires_at": record.expires_at.isoformat()},
            )
        return {
            "peer_id": peer_id,
            "code": code,
            "expires_at": record.expires_at.isoformat(),
        }

    def verify_code(self, peer_id: int, code: str) -> dict:
        record = self.repository.get_code(peer_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid_pairing_code")
        try:
            consumed = consume_pairing_code(record, code, now=datetime.now(UTC))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid_pairing_code") from exc
        self.repository.save_code(peer_id, consumed)
        self.repository.mark_paired(peer_id)
        if self.audit_repository is not None:
            self.audit_repository.append_event(
                event_type="pairing_verified",
                peer_id=peer_id,
                status="ok",
                details={"peer_id": peer_id},
            )
        return {"status": "paired"}


pairing_service = PairingService()
