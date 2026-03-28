"""Pairing repository abstractions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TypedDict, cast

from vk_openclaw_service.domain.pairing import PairingCodeRecord


class PairingPayload(TypedDict):
    codes: dict[str, dict[str, object]]
    paired_peers: list[int]


@dataclass
class InMemoryPairingRepository:
    codes: dict[int, PairingCodeRecord] = field(default_factory=dict)
    paired_peers: set[int] = field(default_factory=set)

    def save_code(self, peer_id: int, record: PairingCodeRecord) -> None:
        self.codes[peer_id] = record

    def get_code(self, peer_id: int) -> PairingCodeRecord | None:
        return self.codes.get(peer_id)

    def mark_paired(self, peer_id: int) -> None:
        self.paired_peers.add(peer_id)

    def is_paired(self, peer_id: int) -> bool:
        return peer_id in self.paired_peers

    def list_paired_peers(self) -> list[int]:
        return sorted(self.paired_peers)


@dataclass
class FilePairingRepository:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"codes": {}, "paired_peers": []}, indent=2), encoding="utf-8")

    def save_code(self, peer_id: int, record: PairingCodeRecord) -> None:
        payload = self._read()
        payload["codes"][str(peer_id)] = {
            "peer_id": record.peer_id,
            "code_hash": record.code_hash,
            "expires_at": record.expires_at.isoformat(),
            "consumed_at": record.consumed_at.isoformat() if record.consumed_at else None,
        }
        self._write(payload)

    def get_code(self, peer_id: int) -> PairingCodeRecord | None:
        payload = self._read()["codes"].get(str(peer_id))
        if payload is None:
            return None
        return PairingCodeRecord(
            peer_id=_required_int(payload, "peer_id"),
            code_hash=_required_str(payload, "code_hash"),
            expires_at=datetime.fromisoformat(_required_str(payload, "expires_at")),
            consumed_at=_optional_datetime(payload, "consumed_at"),
        )

    def mark_paired(self, peer_id: int) -> None:
        payload = self._read()
        peers = set(payload["paired_peers"])
        peers.add(peer_id)
        payload["paired_peers"] = sorted(peers)
        self._write(payload)

    def is_paired(self, peer_id: int) -> bool:
        payload = self._read()
        return peer_id in set(payload["paired_peers"])

    def list_paired_peers(self) -> list[int]:
        payload = self._read()
        return sorted(payload["paired_peers"])

    def _read(self) -> PairingPayload:
        return cast(PairingPayload, json.loads(self.path.read_text(encoding="utf-8")))

    def _write(self, payload: PairingPayload) -> None:
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _required_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"invalid_pairing_payload_{key}")
    return value


def _required_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"invalid_pairing_payload_{key}")
    return value


def _optional_datetime(payload: dict[str, object], key: str) -> datetime | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"invalid_pairing_payload_{key}")
    return datetime.fromisoformat(value)
