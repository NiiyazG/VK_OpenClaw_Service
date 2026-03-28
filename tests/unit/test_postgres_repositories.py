from datetime import datetime

from vk_openclaw_service.domain.checkpoints import CheckpointState
from vk_openclaw_service.domain.pairing import PairingCodeRecord, hash_pairing_code
from vk_openclaw_service.infra.repositories.postgres import (
    PostgresAuditRepository,
    PostgresCheckpointRepository,
    PostgresDeadLetterRepository,
    PostgresPairingRepository,
    PostgresSavedDeadLetterQueryRepository,
)


class FakePostgresSession:
    def __init__(self) -> None:
        self.pairing_codes: dict[int, dict[str, object]] = {}
        self.paired_peers: set[int] = set()
        self.checkpoints: dict[int, dict[str, object]] = {}
        self.audit_events: list[dict[str, object]] = [
            {
                "id": "evt-1",
                "ts": "2026-03-16T20:00:00Z",
                "event_type": "system_started",
                "peer_id": None,
                "status": "ok",
                "details": {"source": "bootstrap"},
                "cursor": "cursor-1",
            }
        ]
        self.dead_letters: list[dict[str, object]] = []
        self.saved_queries: dict[str, dict[str, object]] = {}

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        normalized = " ".join(query.split()).lower()
        if "insert into pairing_codes" in normalized:
            peer_id, code_hash, expires_at, consumed_at = params
            self.pairing_codes[int(peer_id)] = {
                "peer_id": int(peer_id),
                "code_hash": str(code_hash),
                "expires_at": str(expires_at),
                "consumed_at": consumed_at,
            }
            return
        if "insert into paired_peers" in normalized:
            self.paired_peers.add(int(params[0]))
            return
        if "insert into checkpoints" in normalized:
            peer_id, last_seen, last_committed, status, current_message_id, degradation_reason = params
            self.checkpoints[int(peer_id)] = {
                "peer_id": int(peer_id),
                "last_seen_message_id": int(last_seen),
                "last_committed_message_id": int(last_committed),
                "status": str(status),
                "current_message_id": current_message_id,
                "degradation_reason": degradation_reason,
            }
            return
        raise AssertionError(f"unexpected execute query: {normalized}")

    def fetchone(self, query: str, params: tuple[object, ...]) -> dict[str, object] | None:
        normalized = " ".join(query.split()).lower()
        if "delete from saved_dead_letter_queries" in normalized:
            removed = self.saved_queries.pop(str(params[0]), None)
            return None if removed is None else {"name": removed["name"]}
        if "from pairing_codes" in normalized:
            return self.pairing_codes.get(int(params[0]))
        if "from paired_peers" in normalized:
            peer_id = int(params[0])
            return {"peer_id": peer_id} if peer_id in self.paired_peers else None
        if "from checkpoints" in normalized:
            return self.checkpoints.get(int(params[0]))
        if "from saved_dead_letter_queries" in normalized and "where name =" in normalized:
            return self.saved_queries.get(str(params[0]))
        if "insert into audit_events" in normalized:
            event_type, peer_id, status, details = params
            next_id = len(self.audit_events) + 1
            event = {
                "id": f"evt-{next_id}",
                "ts": f"2026-03-16T20:{next_id:02d}:00Z",
                "event_type": str(event_type),
                "peer_id": peer_id,
                "status": str(status),
                "details": dict(details),
                "cursor": f"cursor-{next_id}",
            }
            self.audit_events.append(event)
            return event
        if "insert into dead_letters" in normalized:
            peer_id, message_id, reason, attempt, priority, text, details = params
            next_id = len(self.dead_letters) + 1
            record = {
                "id": f"dlq-{next_id}",
                "ts": f"2026-03-16T21:{next_id:02d}:00Z",
                "acknowledged_at": None,
                "peer_id": int(peer_id),
                "message_id": int(message_id),
                "reason": str(reason),
                "attempt": int(attempt),
                "priority": str(priority),
                "text": str(text),
                "details": dict(details),
            }
            self.dead_letters.append(record)
            return record
        if "update dead_letters" in normalized:
            dead_letter_id = str(params[0])
            for record in self.dead_letters:
                if record["id"] != dead_letter_id:
                    continue
                if record["acknowledged_at"] is None:
                    record["acknowledged_at"] = "2026-03-16T22:00:00Z"
                return record
            return None
        if "insert into saved_dead_letter_queries" in normalized:
            name, description, filters = params
            existing = self.saved_queries.get(str(name))
            record = {
                "name": str(name),
                "description": description,
                "filters": dict(filters),
                "created_at": existing["created_at"] if existing is not None else "2026-03-16T23:00:00Z",
                "updated_at": "2026-03-16T23:05:00Z",
            }
            self.saved_queries[str(name)] = record
            return record
        raise AssertionError(f"unexpected fetchone query: {normalized}")

    def fetchall(self, query: str, params: tuple[object, ...]) -> list[dict[str, object]]:
        normalized = " ".join(query.split()).lower()
        if "from paired_peers" in normalized:
            return [{"peer_id": peer_id} for peer_id in sorted(self.paired_peers)]
        if "from checkpoints" in normalized:
            return [self.checkpoints[peer_id] for peer_id in sorted(self.checkpoints)]
        if "from audit_events" in normalized:
            return list(self.audit_events)
        if "from dead_letters" in normalized:
            return list(self.dead_letters)
        if "from saved_dead_letter_queries" in normalized:
            return [self.saved_queries[name] for name in sorted(self.saved_queries)]
        raise AssertionError(f"unexpected fetchall query: {normalized}")


def test_postgres_pairing_repository_round_trip() -> None:
    session = FakePostgresSession()
    repository = PostgresPairingRepository(session)
    record = PairingCodeRecord(
        peer_id=42,
        code_hash=hash_pairing_code("ABC12345"),
        expires_at=datetime.fromisoformat("2026-03-16T20:00:00+00:00"),
        consumed_at=None,
    )

    repository.save_code(42, record)
    repository.mark_paired(42)

    assert repository.get_code(42) == record
    assert repository.is_paired(42) is True
    assert repository.list_paired_peers() == [42]


def test_postgres_checkpoint_repository_round_trip() -> None:
    session = FakePostgresSession()
    repository = PostgresCheckpointRepository(session)
    state = CheckpointState(
        peer_id=42,
        last_seen_message_id=9,
        last_committed_message_id=7,
        status="idle",
        current_message_id=None,
        degradation_reason=None,
    )

    repository.save(state)

    assert repository.get(42) == state
    assert repository.get_or_create(42) == state
    assert repository.list_states() == [state]


def test_postgres_audit_repository_appends_and_lists_events() -> None:
    session = FakePostgresSession()
    repository = PostgresAuditRepository(session)

    repository.append_event(
        event_type="message_processed",
        peer_id=42,
        status="ok",
        details={"message_id": 8},
    )
    result = repository.list_events(limit=10)

    assert result["items"][-1]["event_type"] == "message_processed"
    assert result["items"][-1]["peer_id"] == 42
    assert result["next_cursor"] == "cursor-2"


def test_postgres_dead_letter_repository_appends_and_lists_records() -> None:
    session = FakePostgresSession()
    repository = PostgresDeadLetterRepository(session)

    record = repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )

    assert record["peer_id"] == 42
    assert record["priority"] == "critical"
    assert repository.list_dead_letters() == [record]

    acked = repository.ack_dead_letter(record["id"])

    assert acked is not None
    assert acked["acknowledged_at"] == "2026-03-16T22:00:00Z"


def test_postgres_saved_query_repository_round_trip() -> None:
    session = FakePostgresSession()
    repository = PostgresSavedDeadLetterQueryRepository(session)

    saved = repository.save_query(
        name="critical-unresolved",
        description="Critical unresolved dead letters",
        filters={"preset": "critical", "priority": "critical"},
    )

    assert repository.get_query("critical-unresolved") == saved
    assert repository.list_queries() == [saved]
    assert repository.delete_query("critical-unresolved") is True
    assert repository.get_query("critical-unresolved") is None
