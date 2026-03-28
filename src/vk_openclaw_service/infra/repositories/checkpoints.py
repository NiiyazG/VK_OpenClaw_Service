"""Checkpoint repository abstractions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from vk_openclaw_service.domain.checkpoints import CheckpointState


@dataclass
class InMemoryCheckpointRepository:
    states: dict[int, CheckpointState] = field(default_factory=dict)

    def save(self, state: CheckpointState) -> None:
        self.states[state.peer_id] = state

    def get(self, peer_id: int) -> CheckpointState | None:
        return self.states.get(peer_id)

    def get_or_create(self, peer_id: int) -> CheckpointState:
        state = self.get(peer_id)
        if state is None:
            state = CheckpointState.empty(peer_id)
            self.save(state)
        return state

    def list_states(self) -> list[CheckpointState]:
        return list(self.states.values())


@dataclass
class FileCheckpointRepository:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def save(self, state: CheckpointState) -> None:
        payload = self._read()
        payload[str(state.peer_id)] = {
            "peer_id": state.peer_id,
            "last_seen_message_id": state.last_seen_message_id,
            "last_committed_message_id": state.last_committed_message_id,
            "status": state.status,
            "current_message_id": state.current_message_id,
            "degradation_reason": state.degradation_reason,
        }
        self._write(payload)

    def get(self, peer_id: int) -> CheckpointState | None:
        payload = self._read().get(str(peer_id))
        if payload is None:
            return None
        return _checkpoint_state_from_payload(payload)

    def get_or_create(self, peer_id: int) -> CheckpointState:
        state = self.get(peer_id)
        if state is None:
            state = CheckpointState.empty(peer_id)
            self.save(state)
        return state

    def list_states(self) -> list[CheckpointState]:
        return [_checkpoint_state_from_payload(payload) for payload in self._read().values()]

    def _read(self) -> dict[str, dict[str, object]]:
        return cast(dict[str, dict[str, object]], json.loads(self.path.read_text(encoding="utf-8")))

    def _write(self, payload: dict[str, dict[str, object]]) -> None:
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _checkpoint_state_from_payload(payload: dict[str, object]) -> CheckpointState:
    return CheckpointState(
        peer_id=_required_int(payload, "peer_id"),
        last_seen_message_id=_required_int(payload, "last_seen_message_id"),
        last_committed_message_id=_required_int(payload, "last_committed_message_id"),
        status=_required_str(payload, "status"),
        current_message_id=_optional_int(payload, "current_message_id"),
        degradation_reason=_optional_str(payload, "degradation_reason"),
    )


def _required_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"invalid_checkpoint_payload_{key}")
    return value


def _required_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"invalid_checkpoint_payload_{key}")
    return value


def _optional_int(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"invalid_checkpoint_payload_{key}")
    return value


def _optional_str(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"invalid_checkpoint_payload_{key}")
    return value
