"""Audit repository abstractions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict, cast


class AuditEventRecord(TypedDict):
    id: str
    ts: str
    event_type: str
    peer_id: int | None
    status: str
    details: dict[str, object]
    cursor: str


DEFAULT_AUDIT_EVENTS: list[AuditEventRecord] = [
    {
        "id": "evt-1",
        "ts": "2026-03-16T20:00:00Z",
        "event_type": "system_started",
        "peer_id": None,
        "status": "ok",
        "details": {"source": "bootstrap"},
        "cursor": "cursor-1",
    },
    {
        "id": "evt-2",
        "ts": "2026-03-16T20:10:00Z",
        "event_type": "pairing_code_created",
        "peer_id": 42,
        "status": "ok",
        "details": {"peer_id": 42},
        "cursor": "cursor-2",
    },
]


@dataclass
class InMemoryAuditRepository:
    events: list[AuditEventRecord] = field(
        default_factory=lambda: [item.copy() for item in DEFAULT_AUDIT_EVENTS]
    )

    def list_events(self, cursor: str | None = None, limit: int = 50) -> dict:
        start_index = 0
        if cursor is not None:
            for index, item in enumerate(self.events):
                if item["cursor"] == cursor:
                    start_index = index + 1
                    break
        sliced = self.events[start_index:start_index + limit]
        next_cursor = sliced[-1]["cursor"] if sliced else None
        items = [
            {
                "id": item["id"],
                "ts": item["ts"],
                "event_type": item["event_type"],
                "peer_id": item["peer_id"],
                "status": item["status"],
                "details": item["details"],
            }
            for item in sliced
        ]
        return {
            "items": items,
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
        event = cast(
            AuditEventRecord,
            {
                "id": f"evt-{len(self.events) + 1}",
                "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "event_type": event_type,
                "peer_id": peer_id,
                "status": status,
                "details": details,
                "cursor": f"cursor-{len(self.events) + 1}",
            },
        )
        self.events.append(event)
        return event


@dataclass
class FileAuditRepository:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps(DEFAULT_AUDIT_EVENTS, indent=2), encoding="utf-8")

    def list_events(self, cursor: str | None = None, limit: int = 50) -> dict:
        events = self._read()
        start_index = 0
        if cursor is not None:
            for index, item in enumerate(events):
                if item["cursor"] == cursor:
                    start_index = index + 1
                    break
        sliced = events[start_index:start_index + limit]
        next_cursor = sliced[-1]["cursor"] if sliced else None
        items = [
            {
                "id": item["id"],
                "ts": item["ts"],
                "event_type": item["event_type"],
                "peer_id": item["peer_id"],
                "status": item["status"],
                "details": item["details"],
            }
            for item in sliced
        ]
        return {
            "items": items,
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
        events = self._read()
        event = cast(
            AuditEventRecord,
            {
                "id": f"evt-{len(events) + 1}",
                "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "event_type": event_type,
                "peer_id": peer_id,
                "status": status,
                "details": details,
                "cursor": f"cursor-{len(events) + 1}",
            },
        )
        events.append(event)
        self._write(events)
        return event

    def _read(self) -> list[AuditEventRecord]:
        return cast(list[AuditEventRecord], json.loads(self.path.read_text(encoding="utf-8")))

    def _write(self, events: list[AuditEventRecord]) -> None:
        self.path.write_text(json.dumps(events, indent=2), encoding="utf-8")
