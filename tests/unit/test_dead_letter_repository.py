from pathlib import Path

from vk_openclaw_service.infra.repositories.dead_letters import (
    FileDeadLetterRepository,
    InMemoryDeadLetterRepository,
)


def test_in_memory_dead_letter_repository_appends_and_lists_records() -> None:
    repository = InMemoryDeadLetterRepository()

    record = repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )

    assert record["peer_id"] == 42
    assert record["message_id"] == 8
    assert record["priority"] == "critical"
    assert record["acknowledged_at"] is None
    assert repository.list_dead_letters() == [record]

    acked = repository.ack_dead_letter(record["id"])

    assert acked is not None
    assert acked["acknowledged_at"] is not None


def test_file_dead_letter_repository_persists_records(tmp_path: Path) -> None:
    repository = FileDeadLetterRepository(tmp_path / "dead_letters.json")

    record = repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        priority="high",
        text="/ask hello",
        details={"outcome": "retry"},
    )
    reloaded = FileDeadLetterRepository(tmp_path / "dead_letters.json")

    assert reloaded.list_dead_letters() == [record]
    assert record["priority"] == "high"

    acked = reloaded.ack_dead_letter(record["id"])

    assert acked is not None
    assert acked["acknowledged_at"] is not None


def test_dead_letter_repository_ack_is_idempotent() -> None:
    repository = InMemoryDeadLetterRepository()

    record = repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )

    first = repository.ack_dead_letter(record["id"])
    second = repository.ack_dead_letter(record["id"])

    assert first is not None
    assert second is not None
    assert first["acknowledged_at"] == second["acknowledged_at"]
