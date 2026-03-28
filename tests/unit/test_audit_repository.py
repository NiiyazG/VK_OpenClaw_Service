from pathlib import Path

from vk_openclaw_service.infra.repositories.audit import FileAuditRepository, InMemoryAuditRepository


def test_audit_repository_lists_events_with_cursor_and_limit() -> None:
    repository = InMemoryAuditRepository()

    result = repository.list_events(cursor="cursor-1", limit=1)

    assert len(result["items"]) == 1
    assert result["items"][0]["event_type"] == "pairing_code_created"
    assert result["next_cursor"] == "cursor-2"


def test_file_audit_repository_persists_default_events(tmp_path: Path) -> None:
    repository = FileAuditRepository(tmp_path / "audit.json")

    result = repository.list_events(limit=2)

    assert len(result["items"]) == 2
    assert result["items"][0]["event_type"] == "system_started"
    assert result["next_cursor"] == "cursor-2"


def test_file_audit_repository_appends_events(tmp_path: Path) -> None:
    repository = FileAuditRepository(tmp_path / "audit.json")

    repository.append_event(
        event_type="message_processed",
        peer_id=42,
        status="ok",
        details={"message_id": 8},
    )
    result = repository.list_events(limit=10)

    assert result["items"][-1]["event_type"] == "message_processed"
    assert result["items"][-1]["peer_id"] == 42
