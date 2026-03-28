from fastapi.testclient import TestClient
from unittest.mock import patch

from vk_openclaw_service.main import create_app
from vk_openclaw_service.services.worker_lease import WorkerLease, WorkerLeaseRecord


def test_status_endpoint_returns_expected_shape() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/status", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "plain"
    assert payload["storage"]["mode"] == "memory"
    assert payload["worker"]["state"] == "idle"
    assert payload["worker"]["identity"]["configured_owner_id"] == "worker-default"
    assert payload["worker"]["identity"]["held"] is False
    assert payload["worker"]["identity"]["stale"] is False
    assert payload["worker"]["identity"]["acquired_at"] is None
    assert payload["worker"]["identity"]["refreshed_at"] is None
    assert payload["worker"]["identity"]["previous_owner_id"] is None
    assert payload["worker"]["identity"]["takeover_at"] is None
    assert payload["worker"]["identity"]["takeover_count"] == 0
    assert payload["paired_peers"] == 0
    assert payload["checkpoint"]["last_committed_message_id"] is None
    assert payload["dead_letters"]["count"] == 0
    assert payload["dead_letters"]["last_dead_letter_at"] is None
    assert payload["dead_letters"]["by_priority"] == {"normal": 0, "high": 0, "critical": 0}
    assert payload["dead_letters"]["by_reason"] == {}
    assert payload["saved_queries"]["count"] == 0


def test_health_endpoint_returns_ok_checks(runtime_settings_factory) -> None:
    client = TestClient(create_app(settings=runtime_settings_factory(vk_access_token="vk-token", worker_id="worker-a")))

    response = client.get("/api/v1/health", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"][0]["component"] == "api"
    assert payload["checks"][0]["status"] == "ok"
    assert payload["checks"][1]["component"] == "settings"
    assert {"component": "storage", "status": "ok", "reason": None} in payload["checks"]
    assert {"component": "dead_letters", "status": "ok", "reason": None} in payload["checks"]
    assert {"component": "worker_lease", "status": "ok", "reason": None} in payload["checks"]


def test_admin_endpoints_require_bearer_token() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/status")

    assert response.status_code == 401
    assert client.get("/api/v1/audit/dead-letters").status_code == 401
    assert client.post("/api/v1/audit/dead-letters/dlq-1/ack").status_code == 401


def test_status_endpoint_reflects_runtime_state() -> None:
    app = create_app()
    app.state.container.pairing_repository.mark_paired(42)
    app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=9,
        reason="delivery_rejected",
        attempt=1,
        text="/ask later",
        details={"outcome": "reject"},
    )
    app.state.container.saved_query_repository.save_query(
        name="critical-unresolved",
        description="Critical unresolved dead letters",
        filters={"preset": "critical"},
    )
    app.state.container.checkpoint_repository.save(
        app.state.container.checkpoint_repository.get_or_create(42).__class__(
            peer_id=42,
            last_seen_message_id=7,
            last_committed_message_id=7,
            status="idle",
            current_message_id=None,
            degradation_reason=None,
        )
    )
    client = TestClient(app)

    response = client.get("/api/v1/status", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["paired_peers"] == 1
    assert payload["worker"]["identity"]["configured_owner_id"] == "worker-default"
    assert payload["worker"]["identity"]["owner_id"] is None
    assert payload["worker"]["identity"]["takeover_count"] == 0
    assert payload["checkpoint"]["peer_id"] == 42
    assert payload["checkpoint"]["last_committed_message_id"] == 7
    assert payload["dead_letters"]["count"] == 2
    assert payload["dead_letters"]["last_dead_letter_at"] is not None
    assert payload["dead_letters"]["by_priority"] == {"normal": 0, "high": 1, "critical": 1}
    assert payload["dead_letters"]["by_reason"] == {
        "retry_budget_exhausted": 1,
        "delivery_rejected": 1,
    }
    assert payload["saved_queries"]["count"] == 1


def test_health_endpoint_reflects_missing_vk_token_as_degraded() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v1/health", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert {"component": "vk_client", "status": "degraded", "reason": "missing_access_token"} in payload["checks"]


def test_health_endpoint_reflects_dead_letters_as_degraded() -> None:
    app = create_app()
    app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    client = TestClient(app)

    response = client.get("/api/v1/health", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert {
        "component": "dead_letters",
        "status": "degraded",
        "reason": "1_dead_letters_present:retry_budget_exhausted",
    } in payload["checks"]


def test_health_endpoint_reflects_stale_worker_lease_as_degraded(runtime_settings_factory) -> None:
    app = create_app(settings=runtime_settings_factory(worker_id="worker-a", worker_lease_ttl_sec=15))
    app.state.container.worker_lease.store.claims["vk-openclaw:worker-lease"] = WorkerLeaseRecord(
        token="token-1",
        owner_id="worker-b",
        acquired_at=100.0,
        refreshed_at=100.0,
    )
    app.state.container.worker_lease = WorkerLease(
        store=app.state.container.worker_lease.store,
        owner_id="worker-a",
        key="vk-openclaw:worker-lease",
        ttl_seconds=15,
        now=lambda: 120.0,
    )
    client = TestClient(app)

    response = client.get("/api/v1/health", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert {"component": "worker_lease", "status": "degraded", "reason": "stale_lease_detected"} in payload["checks"]


def test_status_endpoint_reports_takeover_metadata(runtime_settings_factory) -> None:
    app = create_app(settings=runtime_settings_factory(worker_id="worker-a", worker_lease_ttl_sec=15))
    store = app.state.container.worker_lease.store
    store.claims["vk-openclaw:worker-lease"] = WorkerLeaseRecord(
        token="token-1",
        owner_id="worker-b",
        acquired_at=100.0,
        refreshed_at=100.0,
    )
    app.state.container.worker_lease = WorkerLease(
        store=store,
        owner_id="worker-a",
        key="vk-openclaw:worker-lease",
        ttl_seconds=15,
        now=lambda: 120.0,
    )
    token = app.state.container.worker_lease.acquire()
    assert token is not None
    client = TestClient(app)

    response = client.get("/api/v1/status", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    identity = response.json()["worker"]["identity"]
    assert identity["owner_id"] == "worker-a"
    assert identity["previous_owner_id"] == "worker-b"
    assert identity["takeover_at"] == 120.0
    assert identity["takeover_count"] == 1


def test_status_and_health_ignore_acknowledged_dead_letters() -> None:
    app = create_app()
    record = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    app.state.container.dead_letter_repository.ack_dead_letter(record["id"])
    client = TestClient(app)

    status_response = client.get("/api/v1/status", headers={"Authorization": "Bearer test-admin-token"})
    health_response = client.get("/api/v1/health", headers={"Authorization": "Bearer test-admin-token"})

    assert status_response.status_code == 200
    assert status_response.json()["dead_letters"]["count"] == 0
    assert status_response.json()["dead_letters"]["last_dead_letter_at"] is None
    assert status_response.json()["dead_letters"]["by_priority"] == {"normal": 0, "high": 0, "critical": 0}
    assert status_response.json()["dead_letters"]["by_reason"] == {}
    assert health_response.status_code == 200
    assert {"component": "dead_letters", "status": "ok", "reason": None} in health_response.json()["checks"]


def test_health_endpoint_reflects_database_mode_without_dsns_as_degraded(runtime_settings_factory) -> None:
    app = create_app(settings=runtime_settings_factory(persistence_mode="database", vk_access_token="vk-token"))
    client = TestClient(app)

    response = client.get("/api/v1/health", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert {
        "component": "storage",
        "status": "degraded",
        "reason": "missing_database_or_redis_dsn",
    } in payload["checks"]


def test_health_endpoint_reflects_missing_storage_drivers_as_degraded(runtime_settings_factory) -> None:
    with patch("vk_openclaw_service.infra.persistence.probe_postgres_driver") as probe_postgres_mock:
        with patch("vk_openclaw_service.infra.persistence.probe_redis_driver") as probe_redis_mock:
            probe_postgres_mock.return_value = type(
                "State", (), {"available": False, "reason": "missing_postgres_driver"}
            )()
            probe_redis_mock.return_value = type(
                "State", (), {"available": False, "reason": "missing_redis_driver"}
            )()
            app = create_app(
                settings=runtime_settings_factory(
                    persistence_mode="database",
                    database_dsn="postgresql://user:pass@localhost:5432/app",
                    redis_dsn="redis://localhost:6379/0",
                    vk_access_token="vk-token",
                )
            )
    client = TestClient(app)

    response = client.get("/api/v1/health", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert {
        "component": "storage",
        "status": "degraded",
        "reason": "missing_postgres_driver+missing_redis_driver",
    } in payload["checks"]


def test_health_endpoint_is_ok_when_database_storage_session_is_available(runtime_settings_factory) -> None:
    with patch("vk_openclaw_service.infra.persistence.probe_postgres_driver") as probe_postgres_mock:
        with patch("vk_openclaw_service.infra.persistence.probe_redis_driver") as probe_redis_mock:
            with patch("vk_openclaw_service.infra.persistence.build_postgres_adapter") as build_postgres_adapter_mock:
                with patch("vk_openclaw_service.infra.persistence.ensure_postgres_schema") as ensure_schema_mock:
                    probe_postgres_mock.return_value = type("State", (), {"available": True, "reason": None})()
                    probe_redis_mock.return_value = type("State", (), {"available": True, "reason": None})()
                    build_postgres_adapter_mock.return_value.open_session.return_value = type(
                        "S", (), {"ping": lambda self: True, "fetchall": lambda self, query, params: []}
                    )()
                    ensure_schema_mock.return_value = None
                    app = create_app(
                        settings=runtime_settings_factory(
                            persistence_mode="database",
                            database_dsn="postgresql://user:pass@localhost:5432/app",
                            redis_dsn="redis://localhost:6379/0",
                            vk_access_token="vk-token",
                        )
                    )
    client = TestClient(app)

    response = client.get("/api/v1/health", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert {"component": "storage", "status": "ok", "reason": None} in payload["checks"]


def test_health_endpoint_reflects_database_schema_bootstrap_failure(runtime_settings_factory) -> None:
    with patch("vk_openclaw_service.infra.persistence.probe_postgres_driver") as probe_postgres_mock:
        with patch("vk_openclaw_service.infra.persistence.probe_redis_driver") as probe_redis_mock:
            with patch("vk_openclaw_service.infra.persistence.build_postgres_adapter") as build_postgres_adapter_mock:
                with patch("vk_openclaw_service.infra.persistence.ensure_postgres_schema") as ensure_schema_mock:
                    probe_postgres_mock.return_value = type("State", (), {"available": True, "reason": None})()
                    probe_redis_mock.return_value = type("State", (), {"available": True, "reason": None})()
                    build_postgres_adapter_mock.return_value.open_session.return_value = type(
                        "S", (), {"ping": lambda self: True}
                    )()
                    ensure_schema_mock.side_effect = RuntimeError("boom")
                    app = create_app(
                        settings=runtime_settings_factory(
                            persistence_mode="database",
                            database_dsn="postgresql://user:pass@localhost:5432/app",
                            redis_dsn="redis://localhost:6379/0",
                            vk_access_token="vk-token",
                        )
                    )
    client = TestClient(app)

    response = client.get("/api/v1/health", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert {
        "component": "storage",
        "status": "degraded",
        "reason": "database_schema_bootstrap_failed",
    } in payload["checks"]
