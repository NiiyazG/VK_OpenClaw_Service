from unittest.mock import patch

from vk_openclaw_service.infra.postgres import (
    build_postgres_adapter,
    ensure_postgres_schema,
    probe_postgres_driver,
)
from vk_openclaw_service.infra.redis_adapter import build_redis_adapter, probe_redis_driver


def test_probe_postgres_driver_reports_missing_driver() -> None:
    state = probe_postgres_driver(module_finder=lambda _: None)

    assert state.available is False
    assert state.reason == "missing_postgres_driver"


def test_probe_postgres_driver_accepts_psycopg() -> None:
    state = probe_postgres_driver(module_finder=lambda name: object() if name == "psycopg" else None)

    assert state.available is True
    assert state.reason is None


def test_probe_redis_driver_reports_missing_driver() -> None:
    state = probe_redis_driver(module_finder=lambda _: None)

    assert state.available is False
    assert state.reason == "missing_redis_driver"


def test_probe_redis_driver_accepts_installed_module() -> None:
    state = probe_redis_driver(module_finder=lambda name: object() if name == "redis" else None)

    assert state.available is True
    assert state.reason is None


def test_build_storage_adapters_preserve_dsns() -> None:
    postgres = build_postgres_adapter("postgresql://user:pass@localhost:5432/app")
    redis = build_redis_adapter("redis://localhost:6379/0")

    assert postgres.dsn == "postgresql://user:pass@localhost:5432/app"
    assert redis.dsn == "redis://localhost:6379/0"


def test_redis_adapter_opens_session_and_increments_with_ttl() -> None:
    class FakeRedisClient:
        def __init__(self) -> None:
            self.values: dict[str, int] = {}
            self.expire_calls: list[tuple[str, int]] = []

        def incr(self, key: str) -> int:
            self.values[key] = self.values.get(key, 0) + 1
            return self.values[key]

        def expire(self, key: str, ttl_seconds: int) -> None:
            self.expire_calls.append((key, ttl_seconds))

    class FakeModule:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.client = FakeRedisClient()

        def from_url(self, dsn: str):
            self.calls.append(dsn)
            return self.client

    module = FakeModule()
    adapter = build_redis_adapter("redis://localhost:6379/0")

    session = adapter.open_session(module_loader=lambda: module)
    first = session.increment("rate:openclaw:42", 60)
    second = session.increment("rate:openclaw:42", 60)

    assert module.calls == ["redis://localhost:6379/0"]
    assert first == 1
    assert second == 2
    assert module.client.expire_calls == [("rate:openclaw:42", 60)]


def test_redis_session_claim_once_uses_nx_and_ttl() -> None:
    class FakeRedisClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, bool, int]] = []
            self.claimed = False

        def set(self, key: str, value: str, *, nx: bool, ex: int):
            self.calls.append((key, value, nx, ex))
            if self.claimed:
                return False
            self.claimed = True
            return True

    class FakeModule:
        def __init__(self) -> None:
            self.client = FakeRedisClient()

        def from_url(self, dsn: str):
            return self.client

    session = build_redis_adapter("redis://localhost:6379/0").open_session(module_loader=lambda: FakeModule())

    first = session.claim_once("replay:42:8", 300)
    second = session.claim_once("replay:42:8", 300)

    assert first is True
    assert second is False


def test_redis_session_acquire_and_release_worker_lease() -> None:
    class FakeRedisClient:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}
            self.expire_calls: list[tuple[str, int]] = []

        def set(self, key: str, value: str, *, nx: bool, ex: int):
            if nx and key in self.values:
                return False
            self.values[key] = value
            return True

        def get(self, key: str):
            return self.values.get(key)

        def expire(self, key: str, ttl_seconds: int) -> None:
            self.expire_calls.append((key, ttl_seconds))

        def delete(self, key: str) -> None:
            self.values.pop(key, None)

    class FakeModule:
        def __init__(self) -> None:
            self.client = FakeRedisClient()

        def from_url(self, dsn: str):
            return self.client

    session = build_redis_adapter("redis://localhost:6379/0").open_session(module_loader=lambda: FakeModule())

    with patch("vk_openclaw_service.infra.redis_adapter.time.time", side_effect=[100.0, 125.0, 130.0]):
        assert session.acquire("worker:lease", "token-1", "worker-a", 15) is True
        assert session.acquire("worker:lease", "token-2", "worker-b", 15) is True
        assert session.refresh("worker:lease", "token-2", 15) is True
    assert session.client.expire_calls == [("worker:lease", 15)]
    session.release("worker:lease", "token-1")
    assert session.client.values["worker:lease"] == (
        '{"acquired_at": 125.0, "owner_id": "worker-b", "previous_owner_id": "worker-a", "refreshed_at": 130.0, "takeover_at": 125.0, "takeover_count": 1, "token": "token-2"}'
    )
    session.release("worker:lease", "token-2")
    assert "worker:lease" not in session.client.values


def test_redis_session_acquire_takes_over_stale_worker_lease() -> None:
    class FakeRedisClient:
        def __init__(self) -> None:
            self.values = {
                "worker:lease": '{"acquired_at": 100.0, "owner_id": "worker-b", "refreshed_at": 100.0, "token": "token-1"}'
            }

        def set(self, key: str, value: str, *, nx: bool, ex: int):
            self.values[key] = value
            return True

        def get(self, key: str):
            return self.values.get(key)

    class FakeModule:
        def __init__(self) -> None:
            self.client = FakeRedisClient()

        def from_url(self, dsn: str):
            return self.client

    session = build_redis_adapter("redis://localhost:6379/0").open_session(module_loader=lambda: FakeModule())

    with patch("vk_openclaw_service.infra.redis_adapter.time.time", return_value=120.0):
        acquired = session.acquire("worker:lease", "token-2", "worker-a", 15)

    assert acquired is True
    assert session.client.values["worker:lease"] == (
        '{"acquired_at": 120.0, "owner_id": "worker-a", "previous_owner_id": "worker-b", "refreshed_at": 120.0, "takeover_at": 120.0, "takeover_count": 1, "token": "token-2"}'
    )


def test_redis_session_enqueue_pushes_json_payload() -> None:
    class FakeRedisClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def rpush(self, key: str, value: str) -> None:
            self.calls.append((key, value))

    class FakeModule:
        def __init__(self) -> None:
            self.client = FakeRedisClient()

        def from_url(self, dsn: str):
            return self.client

    session = build_redis_adapter("redis://localhost:6379/0").open_session(module_loader=lambda: FakeModule())

    session.enqueue("vk-openclaw:retry", {"peer_id": 42, "message_id": 8})

    assert session.client.calls == [("vk-openclaw:retry", '{"message_id": 8, "peer_id": 42}')]


def test_redis_session_dequeue_ready_skips_not_ready_head_item() -> None:
    class FakeRedisClient:
        def __init__(self) -> None:
            self.items = [
                '{"available_at": 200.0, "message_id": 1}',
                '{"available_at": 100.0, "message_id": 2}',
            ]
            self.rotations: list[str] = []

        def llen(self, key: str) -> int:
            return len(self.items)

        def lpop(self, key: str):
            if not self.items:
                return None
            return self.items.pop(0)

        def rpush(self, key: str, value: str) -> None:
            self.rotations.append(value)
            self.items.append(value)

    class FakeModule:
        def __init__(self) -> None:
            self.client = FakeRedisClient()

        def from_url(self, dsn: str):
            return self.client

    session = build_redis_adapter("redis://localhost:6379/0").open_session(module_loader=lambda: FakeModule())

    payload = session.dequeue_ready("vk-openclaw:retry", 150.0)

    assert payload == {"available_at": 100.0, "message_id": 2}


def test_postgres_adapter_opens_session_with_loaded_module() -> None:
    class FakeModule:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def connect(self, dsn: str):
            self.calls.append(dsn)
            return object()

    module = FakeModule()
    adapter = build_postgres_adapter("postgresql://user:pass@localhost:5432/app")

    session = adapter.open_session(module_loader=lambda: module)

    assert module.calls == ["postgresql://user:pass@localhost:5432/app"]
    assert session.connection is not None


def test_postgres_session_ping_returns_true_on_select_1() -> None:
    class FakeCursor:
        description = [("ok",)]

        def execute(self, query: str, params: tuple[object, ...]) -> None:
            self.query = query

        def fetchone(self):
            return (1,)

        def close(self) -> None:
            pass

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def commit(self) -> None:
            pass

    session = build_postgres_adapter("postgresql://user:pass@localhost:5432/app").open_session(
        module_loader=lambda: type("M", (), {"connect": lambda _, dsn: FakeConnection()})()
    )

    assert session.ping() is True


def test_ensure_postgres_schema_executes_all_statements() -> None:
    calls: list[str] = []

    class FakeSession:
        def execute(self, query: str, params: tuple[object, ...]) -> None:
            calls.append(" ".join(query.split()).lower())

    ensure_postgres_schema(FakeSession())

    assert len(calls) == 6
    assert "create table if not exists pairing_codes" in calls[0]
