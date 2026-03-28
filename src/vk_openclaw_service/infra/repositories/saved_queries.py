"""Saved dead-letter query repositories."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict, cast


class SavedDeadLetterQueryRecord(TypedDict):
    name: str
    description: str | None
    filters: dict[str, object]
    created_at: str
    updated_at: str


@dataclass
class InMemorySavedDeadLetterQueryRepository:
    items: dict[str, SavedDeadLetterQueryRecord] = field(default_factory=dict)

    def list_queries(self) -> list[SavedDeadLetterQueryRecord]:
        return [self.items[key] for key in sorted(self.items)]

    def get_query(self, name: str) -> SavedDeadLetterQueryRecord | None:
        return self.items.get(name)

    def save_query(
        self,
        *,
        name: str,
        description: str | None,
        filters: dict[str, object],
    ) -> SavedDeadLetterQueryRecord:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        existing = self.items.get(name)
        record = cast(
            SavedDeadLetterQueryRecord,
            {
                "name": name,
                "description": description,
                "filters": dict(filters),
                "created_at": existing["created_at"] if existing is not None else now,
                "updated_at": now,
            },
        )
        self.items[name] = record
        return record

    def delete_query(self, name: str) -> bool:
        return self.items.pop(name, None) is not None


@dataclass
class FileSavedDeadLetterQueryRepository:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def list_queries(self) -> list[SavedDeadLetterQueryRecord]:
        return sorted(self._read(), key=lambda item: str(item["name"]))

    def get_query(self, name: str) -> SavedDeadLetterQueryRecord | None:
        for item in self._read():
            if item["name"] == name:
                return item
        return None

    def save_query(
        self,
        *,
        name: str,
        description: str | None,
        filters: dict[str, object],
    ) -> SavedDeadLetterQueryRecord:
        items = self._read()
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        created_at = now
        for item in items:
            if item["name"] == name:
                created_at = str(item["created_at"])
                item.update(
                    {
                        "description": description,
                        "filters": dict(filters),
                        "updated_at": now,
                    }
                )
                self._write(items)
                return item
        record = cast(
            SavedDeadLetterQueryRecord,
            {
                "name": name,
                "description": description,
                "filters": dict(filters),
                "created_at": created_at,
                "updated_at": now,
            },
        )
        items.append(record)
        self._write(items)
        return record

    def delete_query(self, name: str) -> bool:
        items = self._read()
        filtered = [item for item in items if item["name"] != name]
        if len(filtered) == len(items):
            return False
        self._write(filtered)
        return True

    def _read(self) -> list[SavedDeadLetterQueryRecord]:
        return cast(list[SavedDeadLetterQueryRecord], json.loads(self.path.read_text(encoding="utf-8")))

    def _write(self, items: list[SavedDeadLetterQueryRecord]) -> None:
        self.path.write_text(json.dumps(items, indent=2), encoding="utf-8")
