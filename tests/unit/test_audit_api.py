from fastapi.testclient import TestClient

from vk_openclaw_service.main import create_app
from vk_openclaw_service.services.worker_lease import WorkerLease, WorkerLeaseRecord


def test_audit_events_returns_paginated_shape() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/v1/audit/events",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["items"], list)
    assert payload["items"][0]["event_type"] == "system_started"
    assert "next_cursor" in payload


def test_audit_events_supports_cursor_parameter() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/v1/audit/events?cursor=cursor-1&limit=1",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["next_cursor"] == "cursor-2"


def test_audit_events_requires_admin_token() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/audit/events")

    assert response.status_code == 401
    assert client.get("/api/v1/audit/summary").status_code == 401
    assert client.get("/api/v1/audit/worker-lease").status_code == 401
    assert client.post("/api/v1/audit/worker-lease/reset").status_code == 401


def test_audit_summary_returns_compact_operational_counts() -> None:
    app = create_app()
    app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    acknowledged = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=43,
        message_id=9,
        reason="delivery_rejected",
        attempt=1,
        text="/ask later",
        details={"outcome": "reject"},
    )
    app.state.container.dead_letter_repository.ack_dead_letter(acknowledged["id"])
    app.state.container.saved_query_repository.save_query(
        name="critical-unresolved",
        description="Critical unresolved dead letters",
        filters={"preset": "critical"},
    )
    client = TestClient(app)

    response = client.get("/api/v1/audit/summary", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["events"]["count"] >= 1
    assert payload["events"]["by_type"]["system_started"] >= 1
    assert "system_started" in payload["events"]["recent_types"]
    assert payload["dead_letters"]["count"] == 2
    assert payload["dead_letters"]["unresolved_count"] == 1
    assert payload["dead_letters"]["acknowledged_count"] == 1
    assert payload["dead_letters"]["unresolved_by_priority"] == {"normal": 0, "high": 0, "critical": 1}
    assert payload["dead_letters"]["unresolved_by_reason"] == {"retry_budget_exhausted": 1}
    assert payload["saved_queries"]["count"] == 1
    assert payload["saved_queries"]["names"] == ["critical-unresolved"]
    assert payload["worker_lease"]["takeover_count"] == 0
    assert payload["worker_lease"]["reset_count"] == 0


def test_audit_events_include_worker_lease_takeover_event(runtime_settings_factory) -> None:
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
        audit_repository=app.state.container.audit_repository,
        owner_id="worker-a",
        key="vk-openclaw:worker-lease",
        ttl_seconds=15,
        now=lambda: 120.0,
    )
    assert app.state.container.worker_lease.acquire() is not None
    client = TestClient(app)

    response = client.get("/api/v1/audit/events", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    assert response.json()["items"][-1]["event_type"] == "worker_lease_taken_over"
    assert response.json()["items"][-1]["details"]["requested_by"] == "worker:worker-a"
    assert response.json()["items"][-1]["details"]["trigger"] == "automatic_stale_takeover"


def test_worker_lease_endpoint_returns_current_snapshot(runtime_settings_factory) -> None:
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
        audit_repository=app.state.container.audit_repository,
        owner_id="worker-a",
        key="vk-openclaw:worker-lease",
        ttl_seconds=15,
        now=lambda: 120.0,
    )
    assert app.state.container.worker_lease.acquire() is not None
    client = TestClient(app)

    response = client.get("/api/v1/audit/worker-lease", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured_owner_id"] == "worker-a"
    assert payload["owner_id"] == "worker-a"
    assert payload["previous_owner_id"] == "worker-b"
    assert payload["takeover_at"] == 120.0
    assert payload["takeover_count"] == 1
    assert payload["stale"] is False


def test_worker_lease_reset_endpoint_resets_stale_lease(runtime_settings_factory) -> None:
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
        audit_repository=app.state.container.audit_repository,
        owner_id="worker-a",
        key="vk-openclaw:worker-lease",
        ttl_seconds=15,
        now=lambda: 120.0,
    )
    client = TestClient(app)

    response = client.post("/api/v1/audit/worker-lease/reset", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["reset"] is True
    assert payload["released"]["owner_id"] == "worker-b"
    assert payload["current"]["held"] is False
    assert app.state.container.audit_repository.events[-1]["event_type"] == "worker_lease_reset"
    assert app.state.container.audit_repository.events[-1]["details"]["requested_by"] == "admin_api"


def test_worker_lease_reset_endpoint_records_operator_id(runtime_settings_factory) -> None:
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
        audit_repository=app.state.container.audit_repository,
        owner_id="worker-a",
        key="vk-openclaw:worker-lease",
        ttl_seconds=15,
        now=lambda: 120.0,
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/audit/worker-lease/reset",
        headers={
            "Authorization": "Bearer test-admin-token",
            "X-Operator-Id": "ops-user-1",
        },
    )

    assert response.status_code == 200
    assert app.state.container.audit_repository.events[-1]["event_type"] == "worker_lease_reset"
    assert app.state.container.audit_repository.events[-1]["details"]["requested_by"] == "ops-user-1"


def test_worker_lease_reset_endpoint_rejects_active_lease(runtime_settings_factory) -> None:
    app = create_app(settings=runtime_settings_factory(worker_id="worker-a", worker_lease_ttl_sec=15))
    store = app.state.container.worker_lease.store
    store.claims["vk-openclaw:worker-lease"] = WorkerLeaseRecord(
        token="token-1",
        owner_id="worker-b",
        acquired_at=100.0,
        refreshed_at=110.0,
    )
    app.state.container.worker_lease = WorkerLease(
        store=store,
        audit_repository=app.state.container.audit_repository,
        owner_id="worker-a",
        key="vk-openclaw:worker-lease",
        ttl_seconds=15,
        now=lambda: 120.0,
    )
    client = TestClient(app)

    response = client.post("/api/v1/audit/worker-lease/reset", headers={"Authorization": "Bearer test-admin-token"})

    assert response.status_code == 409
    assert response.json()["detail"] == "worker_lease_not_stale_or_missing"
