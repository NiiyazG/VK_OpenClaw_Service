from pathlib import Path

from vk_openclaw_service.infra.repositories.saved_queries import (
    FileSavedDeadLetterQueryRepository,
    InMemorySavedDeadLetterQueryRepository,
)


def test_in_memory_saved_query_repository_round_trip() -> None:
    repository = InMemorySavedDeadLetterQueryRepository()

    saved = repository.save_query(
        name="unresolved-critical",
        description="Critical unresolved dead letters",
        filters={"preset": "critical"},
    )

    assert saved["name"] == "unresolved-critical"
    assert saved["filters"] == {"preset": "critical"}
    assert repository.get_query("unresolved-critical") == saved
    assert repository.list_queries() == [saved]
    assert repository.delete_query("unresolved-critical") is True
    assert repository.get_query("unresolved-critical") is None


def test_file_saved_query_repository_persists_queries(tmp_path: Path) -> None:
    repository = FileSavedDeadLetterQueryRepository(tmp_path / "saved_queries.json")

    saved = repository.save_query(
        name="retry-exhausted",
        description=None,
        filters={"preset": "retry_exhausted"},
    )
    reloaded = FileSavedDeadLetterQueryRepository(tmp_path / "saved_queries.json")

    assert reloaded.get_query("retry-exhausted") == saved
    assert reloaded.list_queries() == [saved]
