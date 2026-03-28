"""Static audit service for the initial API skeleton."""

from __future__ import annotations

from typing import Protocol


class AuditRepository(Protocol):
    def list_events(self, cursor: str | None = None, limit: int = 50) -> dict: ...


def list_audit_events(audit_repository: AuditRepository, cursor: str | None = None, limit: int = 50) -> dict:
    return audit_repository.list_events(cursor=cursor, limit=limit)


class DeadLetterRepository(Protocol):
    def list_dead_letters(self) -> list[dict[str, object]]: ...


class SavedQueryRepository(Protocol):
    def list_queries(self) -> list[dict[str, object]]: ...


class WorkerLeaseView(Protocol):
    def snapshot(self) -> dict[str, object]: ...
    def reset_if_stale(self, *, operator_id: str = "admin_api") -> dict[str, object] | None: ...


def get_worker_lease_snapshot(worker_lease: WorkerLeaseView) -> dict[str, object]:
    return worker_lease.snapshot()


def reset_stale_worker_lease(worker_lease: WorkerLeaseView, *, operator_id: str) -> dict[str, object] | None:
    return worker_lease.reset_if_stale(operator_id=operator_id)


def build_audit_summary(
    audit_repository: AuditRepository,
    dead_letter_repository: DeadLetterRepository,
    saved_query_repository: SavedQueryRepository,
    worker_lease: WorkerLeaseView,
) -> dict[str, object]:
    events = audit_repository.list_events(limit=1000)["items"]
    event_type_counts: dict[str, int] = {}
    for item in events:
        event_type = str(item["event_type"])
        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
    dead_letters = dead_letter_repository.list_dead_letters()
    saved_queries = saved_query_repository.list_queries()
    unresolved_count = sum(1 for item in dead_letters if item.get("acknowledged_at") is None)
    acknowledged_count = len(dead_letters) - unresolved_count
    unresolved_by_priority = {
        "normal": 0,
        "high": 0,
        "critical": 0,
    }
    unresolved_by_reason: dict[str, int] = {}
    for item in dead_letters:
        if item.get("acknowledged_at") is not None:
            continue
        priority = str(item.get("priority") or "normal")
        unresolved_by_priority[priority] = unresolved_by_priority.get(priority, 0) + 1
        reason = str(item.get("reason") or "unknown")
        unresolved_by_reason[reason] = unresolved_by_reason.get(reason, 0) + 1
    return {
        "events": {
            "count": len(events),
            "last_event_at": events[-1]["ts"] if events else None,
            "by_type": event_type_counts,
            "recent_types": [str(item["event_type"]) for item in events[-10:]],
        },
        "dead_letters": {
            "count": len(dead_letters),
            "unresolved_count": unresolved_count,
            "acknowledged_count": acknowledged_count,
            "unresolved_by_priority": unresolved_by_priority,
            "unresolved_by_reason": unresolved_by_reason,
        },
        "saved_queries": {
            "count": len(saved_queries),
            "names": [str(item["name"]) for item in saved_queries],
        },
        "worker_lease": {
            "snapshot": worker_lease.snapshot(),
            "takeover_count": event_type_counts.get("worker_lease_taken_over", 0),
            "reset_count": event_type_counts.get("worker_lease_reset", 0),
        },
    }
