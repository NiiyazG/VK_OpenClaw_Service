"""Dead-letter repository abstractions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict, cast


class DeadLetterRecord(TypedDict):
    id: str
    ts: str
    acknowledged_at: str | None
    peer_id: int
    message_id: int
    reason: str
    attempt: int
    priority: str
    text: str
    details: dict[str, object]


@dataclass
class InMemoryDeadLetterRepository:
    items: list[DeadLetterRecord] = field(default_factory=list)

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
        record = cast(
            DeadLetterRecord,
            {
                "id": f"dlq-{len(self.items) + 1}",
                "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "acknowledged_at": None,
                "peer_id": peer_id,
                "message_id": message_id,
                "reason": reason,
                "attempt": attempt,
                "priority": priority or classify_dead_letter_priority(reason=reason, attempt=attempt),
                "text": text,
                "details": details,
            },
        )
        self.items.append(record)
        return record

    def list_dead_letters(self) -> list[DeadLetterRecord]:
        return list(self.items)

    def ack_dead_letter(self, dead_letter_id: str) -> DeadLetterRecord | None:
        for item in self.items:
            if item["id"] != dead_letter_id:
                continue
            if item["acknowledged_at"] is None:
                item["acknowledged_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            return item
        return None


@dataclass
class FileDeadLetterRepository:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

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
        items = self._read()
        record = cast(
            DeadLetterRecord,
            {
                "id": f"dlq-{len(items) + 1}",
                "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "acknowledged_at": None,
                "peer_id": peer_id,
                "message_id": message_id,
                "reason": reason,
                "attempt": attempt,
                "priority": priority or classify_dead_letter_priority(reason=reason, attempt=attempt),
                "text": text,
                "details": details,
            },
        )
        items.append(record)
        self._write(items)
        return record

    def list_dead_letters(self) -> list[DeadLetterRecord]:
        return self._read()

    def ack_dead_letter(self, dead_letter_id: str) -> DeadLetterRecord | None:
        items = self._read()
        for item in items:
            if item["id"] != dead_letter_id:
                continue
            if item["acknowledged_at"] is None:
                item["acknowledged_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
                self._write(items)
            return item
        return None

    def _read(self) -> list[DeadLetterRecord]:
        return cast(list[DeadLetterRecord], json.loads(self.path.read_text(encoding="utf-8")))

    def _write(self, items: list[DeadLetterRecord]) -> None:
        self.path.write_text(json.dumps(items, indent=2), encoding="utf-8")


def classify_dead_letter_priority(*, reason: str, attempt: int) -> str:
    if reason == "retry_budget_exhausted" and attempt >= 3:
        return "critical"
    if reason in {"retry_budget_exhausted", "delivery_rejected"}:
        return "high"
    return "normal"
