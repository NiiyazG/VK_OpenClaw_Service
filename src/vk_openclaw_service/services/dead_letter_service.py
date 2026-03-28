"""Dead-letter read service."""

from __future__ import annotations

from typing import Protocol, cast

from vk_openclaw_service.infra.repositories.dead_letters import classify_dead_letter_priority


class DeadLetterRepository(Protocol):
    def list_dead_letters(self) -> list[dict[str, object]]: ...
    def ack_dead_letter(self, dead_letter_id: str) -> dict[str, object] | None: ...


class AuditRepository(Protocol):
    def append_event(
        self,
        *,
        event_type: str,
        peer_id: int | None,
        status: str,
        details: dict[str, object],
    ) -> object: ...


class SavedQueryRepository(Protocol):
    def list_queries(self) -> list[dict[str, object]]: ...
    def get_query(self, name: str) -> dict[str, object] | None: ...
    def save_query(self, *, name: str, description: str | None, filters: dict[str, object]) -> dict[str, object]: ...
    def delete_query(self, name: str) -> bool: ...


DEAD_LETTER_QUERY_PRESETS: dict[str, dict[str, object]] = {
    "unresolved": {
        "description": "Unacknowledged dead letters.",
        "filters": {
            "acknowledged": False,
        },
    },
    "retry_exhausted": {
        "description": "Unacknowledged retry budget exhausted dead letters.",
        "filters": {
            "acknowledged": False,
            "reason": "retry_budget_exhausted",
        },
    },
    "delivery_rejected": {
        "description": "Unacknowledged delivery rejection dead letters.",
        "filters": {
            "acknowledged": False,
            "reason": "delivery_rejected",
        },
    },
    "acknowledged": {
        "description": "Already acknowledged dead letters.",
        "filters": {
            "acknowledged": True,
        },
    },
    "critical": {
        "description": "Critical unresolved dead letters.",
        "filters": {
            "acknowledged": False,
            "severity": "critical",
        },
    },
}


def list_dead_letters(repository: DeadLetterRepository, *, limit: int = 50) -> dict[str, object]:
    items = repository.list_dead_letters()
    return {
        "items": items[:limit],
        "count": min(len(items), limit),
    }


def filter_dead_letters(
    items: list[dict[str, object]],
    *,
    acknowledged: bool | None = None,
    reason: str | None = None,
    severity: str | None = None,
    priority: str | None = None,
    peer_id: int | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    acknowledged_after: str | None = None,
    acknowledged_before: str | None = None,
) -> list[dict[str, object]]:
    filtered = items
    if acknowledged is not None:
        filtered = [
            item
            for item in filtered
            if (item.get("acknowledged_at") is not None) is acknowledged
        ]
    if reason is not None:
        filtered = [item for item in filtered if item.get("reason") == reason]
    if severity is not None:
        filtered = [item for item in filtered if item.get("severity") == severity]
    if priority is not None:
        filtered = [item for item in filtered if item.get("priority") == priority]
    if peer_id is not None:
        filtered = [item for item in filtered if item.get("peer_id") == peer_id]
    if created_after is not None:
        filtered = [item for item in filtered if str(item.get("ts")) >= created_after]
    if created_before is not None:
        filtered = [item for item in filtered if str(item.get("ts")) <= created_before]
    if acknowledged_after is not None:
        filtered = [
            item
            for item in filtered
            if item.get("acknowledged_at") is not None and str(item.get("acknowledged_at")) >= acknowledged_after
        ]
    if acknowledged_before is not None:
        filtered = [
            item
            for item in filtered
            if item.get("acknowledged_at") is not None and str(item.get("acknowledged_at")) <= acknowledged_before
        ]
    return filtered


def list_dead_letter_query_presets() -> dict[str, object]:
    return {
        "items": [
            {
                "name": name,
                "description": str(preset["description"]),
                "filters": _record_object_dict(preset, "filters"),
            }
            for name, preset in DEAD_LETTER_QUERY_PRESETS.items()
        ]
    }


def enrich_dead_letter(item: dict[str, object]) -> dict[str, object]:
    enriched = dict(item)
    enriched["priority"] = str(
        item.get("priority")
        or classify_dead_letter_priority(
            reason=str(item.get("reason", "")),
            attempt=_record_attempt(item),
        )
    )
    enriched["severity"] = classify_dead_letter_severity(enriched)
    return enriched


def classify_dead_letter_severity(item: dict[str, object]) -> str:
    return str(item.get("priority") or "normal")


def resolve_dead_letter_filters(
    *,
    preset: str | None = None,
    acknowledged: bool | None = None,
    reason: str | None = None,
    severity: str | None = None,
    priority: str | None = None,
    peer_id: int | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    acknowledged_after: str | None = None,
    acknowledged_before: str | None = None,
) -> dict[str, object]:
    resolved: dict[str, object] = {}
    if preset is not None and preset in DEAD_LETTER_QUERY_PRESETS:
        resolved.update(cast(dict[str, object], DEAD_LETTER_QUERY_PRESETS[preset]["filters"]))
    overrides = {
        "acknowledged": acknowledged,
        "reason": reason,
        "severity": severity,
        "priority": priority,
        "peer_id": peer_id,
        "created_after": created_after,
        "created_before": created_before,
        "acknowledged_after": acknowledged_after,
        "acknowledged_before": acknowledged_before,
    }
    for key, value in overrides.items():
        if value is not None:
            resolved[key] = value
    return resolved


def list_dead_letters_filtered(
    repository: DeadLetterRepository,
    *,
    limit: int = 50,
    preset: str | None = None,
    acknowledged: bool | None = None,
    reason: str | None = None,
    severity: str | None = None,
    priority: str | None = None,
    peer_id: int | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    acknowledged_after: str | None = None,
    acknowledged_before: str | None = None,
) -> dict[str, object]:
    filters = resolve_dead_letter_filters(
        preset=preset,
        acknowledged=acknowledged,
        reason=reason,
        severity=severity,
        priority=priority,
        peer_id=peer_id,
        created_after=created_after,
        created_before=created_before,
        acknowledged_after=acknowledged_after,
        acknowledged_before=acknowledged_before,
    )
    items = filter_dead_letters(
        [enrich_dead_letter(item) for item in repository.list_dead_letters()],
        acknowledged=_filter_bool(filters, "acknowledged"),
        reason=_filter_str(filters, "reason"),
        severity=_filter_str(filters, "severity"),
        priority=_filter_str(filters, "priority"),
        peer_id=_filter_int(filters, "peer_id"),
        created_after=_filter_str(filters, "created_after"),
        created_before=_filter_str(filters, "created_before"),
        acknowledged_after=_filter_str(filters, "acknowledged_after"),
        acknowledged_before=_filter_str(filters, "acknowledged_before"),
    )
    return {
        "items": items[:limit],
        "count": min(len(items), limit),
    }


def acknowledge_dead_letter(
    repository: DeadLetterRepository,
    *,
    dead_letter_id: str,
    audit_repository: AuditRepository | None = None,
    operator_id: str = "admin_api",
) -> dict[str, object] | None:
    record = repository.ack_dead_letter(dead_letter_id)
    if record is None:
        return None
    if audit_repository is not None:
        audit_repository.append_event(
            event_type="dead_letter_acknowledged",
            peer_id=_record_peer_id(record),
            status="ok",
            details={
                "dead_letter_id": record["id"],
                "reason": record["reason"],
                "requested_by": operator_id,
            },
        )
    return record


def acknowledge_dead_letters(
    repository: DeadLetterRepository,
    *,
    dead_letter_ids: list[str],
    audit_repository: AuditRepository | None = None,
    operator_id: str = "admin_api",
) -> dict[str, object]:
    acknowledged: list[dict[str, object]] = []
    not_found: list[str] = []
    for dead_letter_id in dead_letter_ids:
        record = acknowledge_dead_letter(
            repository,
            dead_letter_id=dead_letter_id,
            audit_repository=audit_repository,
            operator_id=operator_id,
        )
        if record is None:
            not_found.append(dead_letter_id)
            continue
        acknowledged.append(record)
    return {
        "acknowledged": acknowledged,
        "not_found": not_found,
        "count": len(acknowledged),
    }


def acknowledge_dead_letters_by_query(
    repository: DeadLetterRepository,
    *,
    preset: str | None = None,
    acknowledged: bool | None = None,
    reason: str | None = None,
    severity: str | None = None,
    priority: str | None = None,
    peer_id: int | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    acknowledged_after: str | None = None,
    acknowledged_before: str | None = None,
    limit: int = 100,
    audit_repository: AuditRepository | None = None,
    operator_id: str = "admin_api",
) -> dict[str, object]:
    filters = resolve_dead_letter_filters(
        preset=preset,
        acknowledged=acknowledged,
        reason=reason,
        severity=severity,
        priority=priority,
        peer_id=peer_id,
        created_after=created_after,
        created_before=created_before,
        acknowledged_after=acknowledged_after,
        acknowledged_before=acknowledged_before,
    )
    items = filter_dead_letters(
        [enrich_dead_letter(item) for item in repository.list_dead_letters()],
        acknowledged=_filter_bool(filters, "acknowledged"),
        reason=_filter_str(filters, "reason"),
        severity=_filter_str(filters, "severity"),
        priority=_filter_str(filters, "priority"),
        peer_id=_filter_int(filters, "peer_id"),
        created_after=_filter_str(filters, "created_after"),
        created_before=_filter_str(filters, "created_before"),
        acknowledged_after=_filter_str(filters, "acknowledged_after"),
        acknowledged_before=_filter_str(filters, "acknowledged_before"),
    )
    target_ids = [str(item["id"]) for item in items[:limit]]
    result = acknowledge_dead_letters(
        repository,
        dead_letter_ids=target_ids,
        audit_repository=audit_repository,
        operator_id=operator_id,
    )
    result["matched"] = len(items)
    return result


def list_saved_queries(repository: SavedQueryRepository) -> dict[str, object]:
    return {"items": repository.list_queries()}


def get_saved_query(repository: SavedQueryRepository, *, name: str) -> dict[str, object] | None:
    return repository.get_query(name)


def save_saved_query(
    repository: SavedQueryRepository,
    *,
    name: str,
    description: str | None,
    filters: dict[str, object],
    audit_repository: AuditRepository | None = None,
    operator_id: str = "admin_api",
) -> dict[str, object]:
    record = repository.save_query(name=name, description=description, filters=filters)
    if audit_repository is not None:
        audit_repository.append_event(
            event_type="dead_letter_saved_query_upserted",
            peer_id=None,
            status="ok",
            details={"name": name, "requested_by": operator_id},
        )
    return record


def delete_saved_query(
    repository: SavedQueryRepository,
    *,
    name: str,
    audit_repository: AuditRepository | None = None,
    operator_id: str = "admin_api",
) -> bool:
    deleted = repository.delete_query(name)
    if deleted and audit_repository is not None:
        audit_repository.append_event(
            event_type="dead_letter_saved_query_deleted",
            peer_id=None,
            status="ok",
            details={"name": name, "requested_by": operator_id},
        )
    return deleted


def _filter_bool(filters: dict[str, object], key: str) -> bool | None:
    value = filters.get(key)
    return value if isinstance(value, bool) else None


def _filter_str(filters: dict[str, object], key: str) -> str | None:
    value = filters.get(key)
    return value if isinstance(value, str) else None


def _filter_int(filters: dict[str, object], key: str) -> int | None:
    value = filters.get(key)
    return value if isinstance(value, int) else None


def _record_peer_id(record: dict[str, object]) -> int | None:
    value = record.get("peer_id")
    return value if isinstance(value, int) else None


def _record_attempt(record: dict[str, object]) -> int:
    value = record.get("attempt")
    return value if isinstance(value, int) else 0


def _record_object_dict(record: dict[str, object], key: str) -> dict[str, object]:
    value = record.get(key)
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, object], value)
