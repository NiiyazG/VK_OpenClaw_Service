"""PostgreSQL-backed repository implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast

from vk_openclaw_service.domain.checkpoints import CheckpointState
from vk_openclaw_service.domain.pairing import PairingCodeRecord
from vk_openclaw_service.infra.repositories.audit import AuditEventRecord
from vk_openclaw_service.infra.repositories.dead_letters import DeadLetterRecord, classify_dead_letter_priority
from vk_openclaw_service.infra.repositories.saved_queries import SavedDeadLetterQueryRecord


class PostgresSession(Protocol):
    def execute(self, query: str, params: tuple[object, ...]) -> None: ...
    def fetchone(self, query: str, params: tuple[object, ...]) -> dict[str, object] | None: ...
    def fetchall(self, query: str, params: tuple[object, ...]) -> list[dict[str, object]]: ...


@dataclass
class PostgresPairingRepository:
    session: PostgresSession

    def save_code(self, peer_id: int, record: PairingCodeRecord) -> None:
        self.session.execute(
            """
            insert into pairing_codes (peer_id, code_hash, expires_at, consumed_at)
            values (%s, %s, %s, %s)
            on conflict (peer_id) do update
            set code_hash = excluded.code_hash,
                expires_at = excluded.expires_at,
                consumed_at = excluded.consumed_at
            """,
            (peer_id, record.code_hash, record.expires_at.isoformat(), _serialize_datetime(record.consumed_at)),
        )

    def get_code(self, peer_id: int) -> PairingCodeRecord | None:
        row = self.session.fetchone(
            """
            select peer_id, code_hash, expires_at, consumed_at
            from pairing_codes
            where peer_id = %s
            """,
            (peer_id,),
        )
        if row is None:
            return None
        return PairingCodeRecord(
            peer_id=_required_int(row, "peer_id"),
            code_hash=_required_str(row, "code_hash"),
            expires_at=datetime.fromisoformat(_required_str(row, "expires_at")),
            consumed_at=_deserialize_datetime(row["consumed_at"]),
        )

    def mark_paired(self, peer_id: int) -> None:
        self.session.execute(
            """
            insert into paired_peers (peer_id)
            values (%s)
            on conflict (peer_id) do nothing
            """,
            (peer_id,),
        )

    def is_paired(self, peer_id: int) -> bool:
        row = self.session.fetchone(
            """
            select peer_id
            from paired_peers
            where peer_id = %s
            """,
            (peer_id,),
        )
        return row is not None

    def list_paired_peers(self) -> list[int]:
        rows = self.session.fetchall(
            """
            select peer_id
            from paired_peers
            order by peer_id
            """,
            (),
        )
        return [_required_int(row, "peer_id") for row in rows]


@dataclass
class PostgresCheckpointRepository:
    session: PostgresSession

    def save(self, state: CheckpointState) -> None:
        self.session.execute(
            """
            insert into checkpoints (
                peer_id,
                last_seen_message_id,
                last_committed_message_id,
                status,
                current_message_id,
                degradation_reason
            )
            values (%s, %s, %s, %s, %s, %s)
            on conflict (peer_id) do update
            set last_seen_message_id = excluded.last_seen_message_id,
                last_committed_message_id = excluded.last_committed_message_id,
                status = excluded.status,
                current_message_id = excluded.current_message_id,
                degradation_reason = excluded.degradation_reason
            """,
            (
                state.peer_id,
                state.last_seen_message_id,
                state.last_committed_message_id,
                state.status,
                state.current_message_id,
                state.degradation_reason,
            ),
        )

    def get(self, peer_id: int) -> CheckpointState | None:
        row = self.session.fetchone(
            """
            select peer_id, last_seen_message_id, last_committed_message_id, status, current_message_id, degradation_reason
            from checkpoints
            where peer_id = %s
            """,
            (peer_id,),
        )
        if row is None:
            return None
        return _checkpoint_from_row(row)

    def get_or_create(self, peer_id: int) -> CheckpointState:
        state = self.get(peer_id)
        if state is None:
            state = CheckpointState.empty(peer_id)
            self.save(state)
        return state

    def list_states(self) -> list[CheckpointState]:
        rows = self.session.fetchall(
            """
            select peer_id, last_seen_message_id, last_committed_message_id, status, current_message_id, degradation_reason
            from checkpoints
            order by peer_id
            """,
            (),
        )
        return [_checkpoint_from_row(row) for row in rows]


@dataclass
class PostgresAuditRepository:
    session: PostgresSession

    def list_events(self, cursor: str | None = None, limit: int = 50) -> dict:
        rows = self.session.fetchall(
            """
            select id, ts, event_type, peer_id, status, details, cursor
            from audit_events
            order by cursor
            """,
            (),
        )
        start_index = 0
        if cursor is not None:
            for index, row in enumerate(rows):
                if row["cursor"] == cursor:
                    start_index = index + 1
                    break
        sliced = rows[start_index:start_index + limit]
        next_cursor = sliced[-1]["cursor"] if sliced else None
        return {
            "items": [
                {
                    "id": str(row["id"]),
                    "ts": str(row["ts"]),
                    "event_type": str(row["event_type"]),
                    "peer_id": _optional_int(row, "peer_id"),
                    "status": str(row["status"]),
                    "details": _required_object_dict(row, "details"),
                }
                for row in sliced
            ],
            "next_cursor": next_cursor,
        }

    def append_event(
        self,
        *,
        event_type: str,
        peer_id: int | None,
        status: str,
        details: dict[str, object],
    ) -> AuditEventRecord:
        row = self.session.fetchone(
            """
            insert into audit_events (event_type, peer_id, status, details)
            values (%s, %s, %s, %s)
            returning id, ts, event_type, peer_id, status, details, cursor
            """,
            (event_type, peer_id, status, details),
        )
        if row is None:
            raise RuntimeError("audit_event_insert_returned_no_row")
        return cast(
            AuditEventRecord,
            {
                "id": str(row["id"]),
                "ts": str(row["ts"]),
                "event_type": str(row["event_type"]),
                "peer_id": _optional_int(row, "peer_id"),
                "status": str(row["status"]),
                "details": _required_object_dict(row, "details"),
                "cursor": str(row["cursor"]),
            },
        )


@dataclass
class PostgresDeadLetterRepository:
    session: PostgresSession

    def append_dead_letter(
        self,
        *,
        peer_id: int,
        message_id: int,
        reason: str,
        attempt: int,
        priority: str | None = None,
        text: str,
        details: dict[str, object],
    ) -> DeadLetterRecord:
        row = self.session.fetchone(
            """
            insert into dead_letters (peer_id, message_id, reason, attempt, priority, text, details)
            values (%s, %s, %s, %s, %s, %s, %s)
            returning id, ts, acknowledged_at, peer_id, message_id, reason, attempt, priority, text, details
            """,
            (
                peer_id,
                message_id,
                reason,
                attempt,
                priority or classify_dead_letter_priority(reason=reason, attempt=attempt),
                text,
                details,
            ),
        )
        if row is None:
            raise RuntimeError("dead_letter_insert_returned_no_row")
        return _dead_letter_from_row(row)

    def list_dead_letters(self) -> list[DeadLetterRecord]:
        rows = self.session.fetchall(
            """
            select id, ts, acknowledged_at, peer_id, message_id, reason, attempt, priority, text, details
            from dead_letters
            order by ts, id
            """,
            (),
        )
        return [_dead_letter_from_row(row) for row in rows]

    def ack_dead_letter(self, dead_letter_id: str) -> DeadLetterRecord | None:
        row = self.session.fetchone(
            """
            update dead_letters
            set acknowledged_at = coalesce(acknowledged_at, now())
            where id = %s
            returning id, ts, acknowledged_at, peer_id, message_id, reason, attempt, priority, text, details
            """,
            (dead_letter_id,),
        )
        if row is None:
            return None
        return _dead_letter_from_row(row)


@dataclass
class PostgresSavedDeadLetterQueryRepository:
    session: PostgresSession

    def list_queries(self) -> list[SavedDeadLetterQueryRecord]:
        rows = self.session.fetchall(
            """
            select name, description, filters, created_at, updated_at
            from saved_dead_letter_queries
            order by name
            """,
            (),
        )
        return [_saved_query_from_row(row) for row in rows]

    def get_query(self, name: str) -> SavedDeadLetterQueryRecord | None:
        row = self.session.fetchone(
            """
            select name, description, filters, created_at, updated_at
            from saved_dead_letter_queries
            where name = %s
            """,
            (name,),
        )
        if row is None:
            return None
        return _saved_query_from_row(row)

    def save_query(
        self,
        *,
        name: str,
        description: str | None,
        filters: dict[str, object],
    ) -> SavedDeadLetterQueryRecord:
        row = self.session.fetchone(
            """
            insert into saved_dead_letter_queries (name, description, filters, created_at, updated_at)
            values (%s, %s, %s, now(), now())
            on conflict (name) do update
            set description = excluded.description,
                filters = excluded.filters,
                updated_at = now()
            returning name, description, filters, created_at, updated_at
            """,
            (name, description, filters),
        )
        if row is None:
            raise RuntimeError("saved_query_upsert_returned_no_row")
        return _saved_query_from_row(row)

    def delete_query(self, name: str) -> bool:
        row = self.session.fetchone(
            """
            delete from saved_dead_letter_queries
            where name = %s
            returning name
            """,
            (name,),
        )
        return row is not None


def _checkpoint_from_row(row: dict[str, object]) -> CheckpointState:
    return CheckpointState(
        peer_id=_required_int(row, "peer_id"),
        last_seen_message_id=_required_int(row, "last_seen_message_id"),
        last_committed_message_id=_required_int(row, "last_committed_message_id"),
        status=_required_str(row, "status"),
        current_message_id=_optional_int(row, "current_message_id"),
        degradation_reason=_optional_str(row, "degradation_reason"),
    )


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _deserialize_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))


def _saved_query_from_row(row: dict[str, object]) -> SavedDeadLetterQueryRecord:
    return cast(
        SavedDeadLetterQueryRecord,
        {
            "name": str(row["name"]),
            "description": _optional_str(row, "description"),
            "filters": _required_object_dict(row, "filters"),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        },
    )


def _dead_letter_from_row(row: dict[str, object]) -> DeadLetterRecord:
    return cast(
        DeadLetterRecord,
        {
            "id": str(row["id"]),
            "ts": str(row["ts"]),
            "acknowledged_at": _optional_str(row, "acknowledged_at"),
            "peer_id": _required_int(row, "peer_id"),
            "message_id": _required_int(row, "message_id"),
            "reason": _required_str(row, "reason"),
            "attempt": _required_int(row, "attempt"),
            "priority": _required_str(row, "priority"),
            "text": _required_str(row, "text"),
            "details": _required_object_dict(row, "details"),
        },
    )


def _required_int(row: dict[str, object], key: str) -> int:
    value = row.get(key)
    if not isinstance(value, int):
        raise ValueError(f"invalid_postgres_row_{key}")
    return value


def _optional_int(row: dict[str, object], key: str) -> int | None:
    value = row.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"invalid_postgres_row_{key}")
    return value


def _required_str(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str):
        raise ValueError(f"invalid_postgres_row_{key}")
    return value


def _optional_str(row: dict[str, object], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"invalid_postgres_row_{key}")
    return value


def _required_object_dict(row: dict[str, object], key: str) -> dict[str, object]:
    value = row.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"invalid_postgres_row_{key}")
    return cast(dict[str, object], value)
