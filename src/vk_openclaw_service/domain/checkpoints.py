"""Checkpoint state transitions for backlog-safe message processing."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class MessageDisposition(StrEnum):
    PROCESSED = "processed"
    RETRY = "retry"
    DEAD_LETTERED = "dead_lettered"


@dataclass(frozen=True)
class ProcessingDecision:
    disposition: MessageDisposition
    reason: str | None = None
    degrade_worker: bool = False
    dead_letter_persisted: bool = False


@dataclass(frozen=True)
class CheckpointState:
    peer_id: int
    last_seen_message_id: int
    last_committed_message_id: int
    status: str
    current_message_id: int | None = None
    degradation_reason: str | None = None

    @classmethod
    def empty(cls, peer_id: int) -> "CheckpointState":
        return cls(
            peer_id=peer_id,
            last_seen_message_id=0,
            last_committed_message_id=0,
            status="idle",
        )


def observe_message(state: CheckpointState, message_id: int) -> CheckpointState:
    return replace(state, last_seen_message_id=max(state.last_seen_message_id, message_id))


def begin_processing(state: CheckpointState, message_id: int) -> CheckpointState:
    if message_id <= state.last_committed_message_id:
        raise ValueError("message is already committed")
    return replace(
        observe_message(state, message_id),
        current_message_id=message_id,
        status="processing",
        degradation_reason=None,
    )


def apply_message_result(state: CheckpointState, decision: ProcessingDecision) -> CheckpointState:
    if state.current_message_id is None:
        raise ValueError("cannot apply a result without an active message")

    if decision.disposition is MessageDisposition.PROCESSED:
        return replace(
            state,
            last_committed_message_id=state.current_message_id,
            current_message_id=None,
            status="idle",
            degradation_reason=None,
        )

    if decision.disposition is MessageDisposition.RETRY:
        return replace(
            state,
            current_message_id=None,
            status="degraded" if decision.degrade_worker else "idle",
            degradation_reason=decision.reason if decision.degrade_worker else None,
        )

    if not decision.dead_letter_persisted:
        raise ValueError("dead-letter persistence is required before commit")

    return replace(
        state,
        last_committed_message_id=state.current_message_id,
        current_message_id=None,
        status="idle",
        degradation_reason=None,
    )
