from fastapi.testclient import TestClient
from unittest.mock import patch

from vk_openclaw_service.core.settings import RuntimeSettings
from vk_openclaw_service.infra.repositories.audit import FileAuditRepository
from vk_openclaw_service.infra.repositories.checkpoints import FileCheckpointRepository
from vk_openclaw_service.infra.repositories.dead_letters import FileDeadLetterRepository
from vk_openclaw_service.infra.repositories.pairing import FilePairingRepository
from vk_openclaw_service.infra.repositories.audit import InMemoryAuditRepository
from vk_openclaw_service.infra.repositories.checkpoints import InMemoryCheckpointRepository
from vk_openclaw_service.infra.repositories.dead_letters import InMemoryDeadLetterRepository
from vk_openclaw_service.infra.repositories.pairing import InMemoryPairingRepository
from vk_openclaw_service.infra.repositories.saved_queries import (
    FileSavedDeadLetterQueryRepository,
    InMemorySavedDeadLetterQueryRepository,
)
from vk_openclaw_service.infra.repositories.postgres import (
    PostgresAuditRepository,
    PostgresCheckpointRepository,
    PostgresDeadLetterRepository,
    PostgresPairingRepository,
    PostgresSavedDeadLetterQueryRepository,
)
from vk_openclaw_service.main import create_app
from vk_openclaw_service.bootstrap.container import build_container


def test_create_app_accepts_custom_runtime_settings_for_admin_token(runtime_settings_factory) -> None:
    app = create_app(settings=runtime_settings_factory(admin_api_token="custom-token"))
    client = TestClient(app)

    rejected = client.get("/api/v1/status", headers={"Authorization": "Bearer test-admin-token"})
    accepted = client.get("/api/v1/status", headers={"Authorization": "Bearer custom-token"})

    assert rejected.status_code == 401
    assert accepted.status_code == 200


def test_create_app_uses_custom_settings_in_status_payload(runtime_settings_factory) -> None:
    app = create_app(
        settings=runtime_settings_factory(
            admin_api_token="custom-token",
            vk_mode="e2e-required",
            rate_per_min=9,
            max_attachments=4,
            max_file_mb=15,
        )
    )
    client = TestClient(app)

    response = client.get("/api/v1/status", headers={"Authorization": "Bearer custom-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "e2e-required"
    assert payload["limits"]["rate_per_min"] == 9


def test_create_app_uses_shared_container_state_for_pairing_flow() -> None:
    client = TestClient(create_app())

    code_response = client.post(
        "/api/v1/pairing/code",
        json={"peer_id": 42},
        headers={"Authorization": "Bearer test-admin-token"},
    )
    verify_response = client.post(
        "/api/v1/pairing/verify",
        json={"peer_id": 42, "code": code_response.json()["code"]},
    )

    assert code_response.status_code == 200
    assert verify_response.status_code == 200


def test_build_container_creates_vk_runtime_service(runtime_settings_factory) -> None:
    container = build_container(
        runtime_settings_factory(
            admin_api_token="custom-token",
            vk_access_token="vk-token",
            allowed_peers={42, 43},
            pair_code_ttl_sec=900,
            openclaw_command="/usr/local/bin/openclaw",
            openclaw_timeout_sec=45,
        )
    )

    assert container.vk_runtime_service is not None
    assert container.pairing_service.allowed_peers == {42, 43}
    assert container.pairing_service.ttl_seconds == 900


def test_container_worker_uses_real_openclaw_adapter_function(runtime_settings_factory) -> None:
    container = build_container(
        runtime_settings_factory(
            openclaw_command="/usr/local/bin/openclaw",
            openclaw_timeout_sec=45,
        )
    )

    with patch("vk_openclaw_service.bootstrap.container.run_openclaw_command", return_value="ok") as runner:
        result = container.worker_service.openclaw_runner("hello")

    assert result == "ok"
    runner.assert_called_once_with("/usr/local/bin/openclaw", "hello", timeout_seconds=45)


def test_container_worker_uses_vk_client_for_reply_delivery(runtime_settings_factory) -> None:
    container = build_container(
        runtime_settings_factory(
            vk_access_token="vk-token",
        )
    )

    with patch.object(container.vk_client, "send_text", return_value=123) as sender:
        result = container.worker_service.send_text(42, "hello")

    assert result == 123
    sender.assert_called_once_with(42, "hello")


def test_create_app_health_is_ok_with_vk_token_present(runtime_settings_factory) -> None:
    app = create_app(settings=runtime_settings_factory(vk_access_token="vk-token"))
    client = TestClient(app)

    response = client.get("/api/v1/health", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_build_container_uses_file_backed_repositories(tmp_path) -> None:
    container = build_container(
        RuntimeSettings(
            state_dir=str(tmp_path),
        )
    )

    assert isinstance(container.audit_repository, FileAuditRepository)
    assert isinstance(container.pairing_repository, FilePairingRepository)
    assert isinstance(container.checkpoint_repository, FileCheckpointRepository)
    assert isinstance(container.dead_letter_repository, FileDeadLetterRepository)
    assert isinstance(container.saved_query_repository, FileSavedDeadLetterQueryRepository)


def test_build_container_uses_in_memory_repositories_when_configured(runtime_settings_factory) -> None:
    container = build_container(
        runtime_settings_factory(
            persistence_mode="memory",
        )
    )

    assert isinstance(container.audit_repository, InMemoryAuditRepository)
    assert isinstance(container.pairing_repository, InMemoryPairingRepository)
    assert isinstance(container.checkpoint_repository, InMemoryCheckpointRepository)
    assert isinstance(container.dead_letter_repository, InMemoryDeadLetterRepository)
    assert isinstance(container.saved_query_repository, InMemorySavedDeadLetterQueryRepository)


def test_build_container_falls_back_to_file_repositories_when_database_mode_is_unconfigured(runtime_settings_factory) -> None:
    container = build_container(runtime_settings_factory(persistence_mode="database"))

    assert container.storage.mode == "database"
    assert container.storage.ready is False
    assert container.storage.fallback_mode == "file"
    assert container.storage.reason == "missing_database_or_redis_dsn"
    assert isinstance(container.audit_repository, FileAuditRepository)


def test_build_container_reports_missing_storage_drivers_in_database_mode(runtime_settings_factory) -> None:
    with patch("vk_openclaw_service.infra.persistence.probe_postgres_driver") as probe_postgres_mock:
        with patch("vk_openclaw_service.infra.persistence.probe_redis_driver") as probe_redis_mock:
            probe_postgres_mock.return_value = type("State", (), {"available": False, "reason": "missing_postgres_driver"})()
            probe_redis_mock.return_value = type("State", (), {"available": False, "reason": "missing_redis_driver"})()
            container = build_container(
                runtime_settings_factory(
                    persistence_mode="database",
                    database_dsn="postgresql://user:pass@localhost:5432/app",
                    redis_dsn="redis://localhost:6379/0",
                )
            )

    assert container.storage.mode == "database"
    assert container.storage.ready is False
    assert container.storage.reason == "missing_postgres_driver+missing_redis_driver"
    assert container.storage.fallback_mode == "file"


def test_build_container_uses_postgres_repositories_when_database_mode_is_available(runtime_settings_factory) -> None:
    with patch("vk_openclaw_service.infra.persistence.probe_postgres_driver") as probe_postgres_mock:
        with patch("vk_openclaw_service.infra.persistence.probe_redis_driver") as probe_redis_mock:
            probe_postgres_mock.return_value = type("State", (), {"available": True, "reason": None})()
            probe_redis_mock.return_value = type("State", (), {"available": True, "reason": None})()
            with patch("vk_openclaw_service.infra.persistence.build_postgres_adapter") as build_postgres_adapter_mock:
                with patch("vk_openclaw_service.infra.persistence.ensure_postgres_schema") as ensure_schema_mock:
                    build_postgres_adapter_mock.return_value.open_session.return_value = type(
                        "S", (), {"ping": lambda self: True}
                    )()
                    ensure_schema_mock.return_value = None
                    container = build_container(
                        runtime_settings_factory(
                            persistence_mode="database",
                            database_dsn="postgresql://user:pass@localhost:5432/app",
                            redis_dsn="redis://localhost:6379/0",
                        )
                    )

    assert container.storage.mode == "database"
    assert container.storage.ready is True
    assert container.storage.reason is None
    assert container.storage.fallback_mode is None
    assert isinstance(container.pairing_repository, PostgresPairingRepository)
    assert isinstance(container.checkpoint_repository, PostgresCheckpointRepository)
    assert isinstance(container.audit_repository, PostgresAuditRepository)
    assert isinstance(container.dead_letter_repository, PostgresDeadLetterRepository)
    assert isinstance(container.saved_query_repository, PostgresSavedDeadLetterQueryRepository)


def test_build_container_falls_back_when_database_connection_fails(runtime_settings_factory) -> None:
    with patch("vk_openclaw_service.infra.persistence.probe_postgres_driver") as probe_postgres_mock:
        with patch("vk_openclaw_service.infra.persistence.probe_redis_driver") as probe_redis_mock:
            probe_postgres_mock.return_value = type("State", (), {"available": True, "reason": None})()
            probe_redis_mock.return_value = type("State", (), {"available": True, "reason": None})()
            with patch("vk_openclaw_service.infra.persistence.build_postgres_adapter") as build_postgres_adapter_mock:
                build_postgres_adapter_mock.return_value.open_session.side_effect = RuntimeError("boom")
                container = build_container(
                    runtime_settings_factory(
                        persistence_mode="database",
                        database_dsn="postgresql://user:pass@localhost:5432/app",
                        redis_dsn="redis://localhost:6379/0",
                    )
                )

    assert container.storage.mode == "database"
    assert container.storage.ready is False
    assert container.storage.reason == "database_connection_failed"
    assert container.storage.fallback_mode == "file"
    assert isinstance(container.audit_repository, FileAuditRepository)


def test_build_container_falls_back_when_database_ping_fails(runtime_settings_factory) -> None:
    fake_session = type("S", (), {"ping": lambda self: False})()
    with patch("vk_openclaw_service.infra.persistence.probe_postgres_driver") as probe_postgres_mock:
        with patch("vk_openclaw_service.infra.persistence.probe_redis_driver") as probe_redis_mock:
            probe_postgres_mock.return_value = type("State", (), {"available": True, "reason": None})()
            probe_redis_mock.return_value = type("State", (), {"available": True, "reason": None})()
            with patch("vk_openclaw_service.infra.persistence.build_postgres_adapter") as build_postgres_adapter_mock:
                build_postgres_adapter_mock.return_value.open_session.return_value = fake_session
                container = build_container(
                    runtime_settings_factory(
                        persistence_mode="database",
                        database_dsn="postgresql://user:pass@localhost:5432/app",
                        redis_dsn="redis://localhost:6379/0",
                    )
                )

    assert container.storage.ready is False
    assert container.storage.reason == "database_ping_failed"
    assert container.storage.fallback_mode == "file"


def test_build_container_falls_back_when_database_schema_bootstrap_fails(runtime_settings_factory) -> None:
    fake_session = type("S", (), {"ping": lambda self: True})()
    with patch("vk_openclaw_service.infra.persistence.probe_postgres_driver") as probe_postgres_mock:
        with patch("vk_openclaw_service.infra.persistence.probe_redis_driver") as probe_redis_mock:
            probe_postgres_mock.return_value = type("State", (), {"available": True, "reason": None})()
            probe_redis_mock.return_value = type("State", (), {"available": True, "reason": None})()
            with patch("vk_openclaw_service.infra.persistence.build_postgres_adapter") as build_postgres_adapter_mock:
                with patch("vk_openclaw_service.infra.persistence.ensure_postgres_schema") as ensure_schema_mock:
                    build_postgres_adapter_mock.return_value.open_session.return_value = fake_session
                    ensure_schema_mock.side_effect = RuntimeError("boom")
                    container = build_container(
                        runtime_settings_factory(
                            persistence_mode="database",
                            database_dsn="postgresql://user:pass@localhost:5432/app",
                            redis_dsn="redis://localhost:6379/0",
                        )
                    )

    assert container.storage.ready is False
    assert container.storage.reason == "database_schema_bootstrap_failed"
    assert container.storage.fallback_mode == "file"


def test_build_container_uses_redis_backed_rate_limiter_when_available(runtime_settings_factory) -> None:
    with patch("vk_openclaw_service.bootstrap.container.probe_redis_driver") as probe_redis_mock:
        with patch("vk_openclaw_service.bootstrap.container.build_redis_adapter") as build_redis_adapter_mock:
            probe_redis_mock.return_value = type("State", (), {"available": True, "reason": None})()
            build_redis_adapter_mock.return_value.open_session.return_value = type(
                "RedisSession", (), {"increment": lambda self, key, ttl_seconds: 1}
            )()
            container = build_container(
                runtime_settings_factory(
                    redis_dsn="redis://localhost:6379/0",
                    rate_per_min=3,
                )
            )

    result = container.worker_service.rate_limiter.allow(peer_id=42, bucket="openclaw")

    assert result is True


def test_build_container_uses_redis_backed_replay_guard_when_available(runtime_settings_factory) -> None:
    class FakeRedisSession:
        def claim_once(self, key: str, ttl_seconds: int) -> bool:
            return True

        def increment(self, key: str, ttl_seconds: int) -> int:
            return 1

    with patch("vk_openclaw_service.bootstrap.container.probe_redis_driver") as probe_redis_mock:
        with patch("vk_openclaw_service.bootstrap.container.build_redis_adapter") as build_redis_adapter_mock:
            probe_redis_mock.return_value = type("State", (), {"available": True, "reason": None})()
            build_redis_adapter_mock.return_value.open_session.return_value = FakeRedisSession()
            container = build_container(
                runtime_settings_factory(
                    redis_dsn="redis://localhost:6379/0",
                    replay_ttl_sec=123,
                )
            )

    assert container.worker_service.replay_guard.claim(peer_id=42, message_id=8) is True


def test_build_container_uses_redis_backed_retry_queue_when_available(runtime_settings_factory) -> None:
    class FakeRedisSession:
        def claim_once(self, key: str, ttl_seconds: int) -> bool:
            return True

        def increment(self, key: str, ttl_seconds: int) -> int:
            return 1

        def enqueue(self, key: str, payload: dict[str, object]) -> None:
            self.last_enqueue = (key, payload)

    with patch("vk_openclaw_service.bootstrap.container.probe_redis_driver") as probe_redis_mock:
        with patch("vk_openclaw_service.bootstrap.container.build_redis_adapter") as build_redis_adapter_mock:
            probe_redis_mock.return_value = type("State", (), {"available": True, "reason": None})()
            build_redis_adapter_mock.return_value.open_session.return_value = FakeRedisSession()
            container = build_container(
                runtime_settings_factory(
                    redis_dsn="redis://localhost:6379/0",
                    retry_queue_key="custom-retry",
                    retry_queue_max_attempts=4,
                    retry_queue_base_backoff_sec=7.0,
                    retry_queue_max_backoff_sec=70.0,
                )
            )

    container.worker_service.retry_queue.enqueue_message(
        peer_id=42,
        message_id=8,
        text="/ask hello",
        paired=True,
        reason="delivery_retry_required",
        now_ts=100.0,
    )

    assert container.worker_service.retry_queue.store.last_enqueue == (
        "custom-retry",
        {
            "peer_id": 42,
            "message_id": 8,
            "text": "/ask hello",
            "paired": True,
            "reason": "delivery_retry_required",
            "attempt": 1,
            "available_at": 107.0,
        },
    )
    assert container.worker_service.retry_queue_max_attempts == 4


def test_build_container_uses_redis_backed_worker_lease_when_available(runtime_settings_factory) -> None:
    class FakeRedisSession:
        def acquire(self, key: str, token: str, owner_id: str, ttl_seconds: int) -> bool:
            self.last_acquire = (key, token, owner_id, ttl_seconds)
            return True

        def release(self, key: str, token: str) -> None:
            self.last_release = (key, token)

        def get(self, key: str):
            return None

    with patch("vk_openclaw_service.bootstrap.container.probe_redis_driver") as probe_redis_mock:
        with patch("vk_openclaw_service.bootstrap.container.build_redis_adapter") as build_redis_adapter_mock:
            probe_redis_mock.return_value = type("State", (), {"available": True, "reason": None})()
            build_redis_adapter_mock.return_value.open_session.return_value = FakeRedisSession()
            container = build_container(
                runtime_settings_factory(
                    redis_dsn="redis://localhost:6379/0",
                    worker_id="worker-a",
                    worker_lease_key="custom-worker-lease",
                    worker_lease_ttl_sec=17,
                )
            )

    acquired, result = container.worker_lease.run(lambda: "ok")

    assert acquired is True
    assert result == "ok"
    assert container.worker_lease.store.last_acquire[0] == "custom-worker-lease"
    assert container.worker_lease.store.last_acquire[2] == "worker-a"
    assert container.worker_lease.store.last_acquire[3] == 17


def test_build_container_worker_lease_uses_shared_audit_repository(runtime_settings_factory) -> None:
    container = build_container(runtime_settings_factory(worker_id="worker-a", worker_lease_ttl_sec=15))
    container.worker_lease.store.claims["vk-openclaw:worker-lease"] = type(
        "LeaseRecord",
        (),
        {
            "token": "token-1",
            "owner_id": "worker-b",
            "acquired_at": 100.0,
            "refreshed_at": 100.0,
            "previous_owner_id": None,
            "takeover_at": None,
            "takeover_count": 0,
        },
    )()
    container.worker_lease = container.worker_lease.__class__(
        store=container.worker_lease.store,
        audit_repository=container.audit_repository,
        owner_id="worker-a",
        key="vk-openclaw:worker-lease",
        ttl_seconds=15,
        now=lambda: 120.0,
    )

    token = container.worker_lease.acquire()

    assert token is not None
    assert container.audit_repository.events[-1]["event_type"] == "worker_lease_taken_over"
