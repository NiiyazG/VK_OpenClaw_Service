"""PostgreSQL adapter probes and factories."""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from importlib.machinery import ModuleSpec
from typing import Any, Callable, Protocol, cast


SCHEMA_STATEMENTS = (
    """
    create table if not exists pairing_codes (
        peer_id bigint primary key,
        code_hash text not null,
        expires_at timestamptz not null,
        consumed_at timestamptz null
    )
    """,
    """
    create table if not exists paired_peers (
        peer_id bigint primary key
    )
    """,
    """
    create table if not exists checkpoints (
        peer_id bigint primary key,
        last_seen_message_id bigint not null,
        last_committed_message_id bigint not null,
        status text not null,
        current_message_id bigint null,
        degradation_reason text null
    )
    """,
    """
    create table if not exists audit_events (
        id text primary key,
        ts timestamptz not null,
        event_type text not null,
        peer_id bigint null,
        status text not null,
        details jsonb not null,
        cursor text unique not null
    )
    """,
    """
    create table if not exists dead_letters (
        id text primary key,
        ts timestamptz not null,
        acknowledged_at timestamptz null,
        peer_id bigint not null,
        message_id bigint not null,
        reason text not null,
        attempt integer not null,
        priority text not null,
        text text not null,
        details jsonb not null
    )
    """,
    """
    create table if not exists saved_dead_letter_queries (
        name text primary key,
        description text null,
        filters jsonb not null,
        created_at timestamptz not null,
        updated_at timestamptz not null
    )
    """,
)


@dataclass(frozen=True)
class PostgresDriverState:
    available: bool
    reason: str | None = None


class PostgresModule(Protocol):
    def connect(self, dsn: str) -> Any: ...


@dataclass(frozen=True)
class PostgresAdapter:
    dsn: str

    def open_session(
        self,
        *,
        module_loader: Callable[[], PostgresModule] | None = None,
    ) -> "PsycopgSession":
        module = (module_loader or import_postgres_module)()
        connection = module.connect(self.dsn)
        return PsycopgSession(connection=connection)


@dataclass
class PsycopgSession:
    connection: Any

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params)
            self.connection.commit()
        finally:
            _close_cursor(cursor)

    def fetchone(self, query: str, params: tuple[object, ...]) -> dict[str, object] | None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params)
            row = cursor.fetchone()
            if row is None:
                self.connection.commit()
                return None
            result = _row_to_dict(cursor, row)
            self.connection.commit()
            return result
        finally:
            _close_cursor(cursor)

    def fetchall(self, query: str, params: tuple[object, ...]) -> list[dict[str, object]]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            result = [_row_to_dict(cursor, row) for row in rows]
            self.connection.commit()
            return result
        finally:
            _close_cursor(cursor)

    def ping(self) -> bool:
        row = self.fetchone("select 1 as ok", ())
        return row == {"ok": 1}


def probe_postgres_driver(
    module_finder: Callable[[str], ModuleSpec | None] = importlib.util.find_spec,
) -> PostgresDriverState:
    if module_finder("psycopg") is not None or module_finder("psycopg2") is not None:
        return PostgresDriverState(available=True, reason=None)
    return PostgresDriverState(available=False, reason="missing_postgres_driver")


def build_postgres_adapter(dsn: str) -> PostgresAdapter:
    return PostgresAdapter(dsn=dsn)


def ensure_postgres_schema(session: PsycopgSession) -> None:
    for statement in SCHEMA_STATEMENTS:
        session.execute(statement, ())


def import_postgres_module() -> PostgresModule:
    try:
        return cast(PostgresModule, importlib.import_module("psycopg"))
    except ModuleNotFoundError:
        return cast(PostgresModule, importlib.import_module("psycopg2"))


def _row_to_dict(cursor: Any, row: object) -> dict[str, object]:
    if isinstance(row, dict):
        return dict(row)
    columns = [description[0] for description in cursor.description]
    if isinstance(row, tuple):
        values = row
    elif isinstance(row, list):
        values = tuple(row)
    else:
        raise TypeError("postgres_row_must_be_tuple_or_dict")
    return dict(zip(columns, values, strict=True))


def _close_cursor(cursor: Any) -> None:
    close = getattr(cursor, "close", None)
    if callable(close):
        close()
