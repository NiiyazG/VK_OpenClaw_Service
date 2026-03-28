from fastapi.testclient import TestClient

from vk_openclaw_service.main import create_app


def test_dead_letters_returns_persisted_records() -> None:
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

    response = client.get(
        "/api/v1/audit/dead-letters",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["peer_id"] == 42
    assert payload["items"][0]["reason"] == "retry_budget_exhausted"
    assert payload["items"][0]["severity"] == "critical"
    assert payload["items"][0]["acknowledged_at"] is None


def test_dead_letters_respects_limit() -> None:
    app = create_app()
    repository = app.state.container.dead_letter_repository
    repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    repository.append_dead_letter(
        peer_id=43,
        message_id=9,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hi",
        details={"outcome": "retry"},
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/audit/dead-letters?limit=1",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert len(payload["items"]) == 1


def test_dead_letters_support_server_side_filters() -> None:
    app = create_app()
    first = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    second = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=43,
        message_id=9,
        reason="delivery_rejected",
        attempt=1,
        text="/ask hi",
        details={"outcome": "reject"},
    )
    app.state.container.dead_letter_repository.ack_dead_letter(second["id"])
    client = TestClient(app)

    response = client.get(
        "/api/v1/audit/dead-letters?acknowledged=false&reason=retry_budget_exhausted&peer_id=42",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == first["id"]


def test_dead_letters_support_severity_filter() -> None:
    app = create_app()
    critical = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=43,
        message_id=9,
        reason="delivery_rejected",
        attempt=1,
        text="/ask hi",
        details={"outcome": "reject"},
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/audit/dead-letters?severity=critical",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == critical["id"]
    assert payload["items"][0]["priority"] == "critical"


def test_dead_letters_support_priority_filter() -> None:
    app = create_app()
    critical = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=43,
        message_id=9,
        reason="delivery_rejected",
        attempt=1,
        text="/ask hi",
        details={"outcome": "reject"},
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/audit/dead-letters?priority=critical",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == critical["id"]


def test_dead_letters_support_time_window_filters() -> None:
    app = create_app()
    app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    second = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=9,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask later",
        details={"outcome": "retry"},
    )
    app.state.container.dead_letter_repository.items[0]["ts"] = "2026-03-17T10:00:00Z"
    app.state.container.dead_letter_repository.items[1]["ts"] = "2026-03-17T11:00:00Z"
    client = TestClient(app)

    response = client.get(
        "/api/v1/audit/dead-letters?created_after=2026-03-17T10:30:00Z&created_before=2026-03-17T11:30:00Z",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == second["id"]


def test_dead_letters_support_acknowledged_time_filters() -> None:
    app = create_app()
    first = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    second = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=9,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask later",
        details={"outcome": "retry"},
    )
    app.state.container.dead_letter_repository.ack_dead_letter(first["id"])
    app.state.container.dead_letter_repository.ack_dead_letter(second["id"])
    app.state.container.dead_letter_repository.items[0]["acknowledged_at"] = "2026-03-17T10:00:00Z"
    app.state.container.dead_letter_repository.items[1]["acknowledged_at"] = "2026-03-17T11:00:00Z"
    client = TestClient(app)

    response = client.get(
        "/api/v1/audit/dead-letters?acknowledged=true&acknowledged_after=2026-03-17T10:30:00Z&acknowledged_before=2026-03-17T11:30:00Z",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == second["id"]


def test_dead_letters_requires_admin_token() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/audit/dead-letters")

    assert response.status_code == 401
    assert client.get("/api/v1/audit/dead-letters/presets").status_code == 401
    assert client.post("/api/v1/audit/dead-letters/ack-bulk").status_code == 401
    assert client.post("/api/v1/audit/dead-letters/ack-query").status_code == 401


def test_dead_letter_presets_endpoint_returns_known_presets() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/v1/audit/dead-letters/presets",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(item["name"] == "unresolved" for item in payload["items"])
    assert any(item["name"] == "retry_exhausted" for item in payload["items"])
    assert any(item["name"] == "critical" for item in payload["items"])


def test_saved_dead_letter_queries_support_crud_and_execution() -> None:
    app = create_app()
    first = app.state.container.dead_letter_repository.append_dead_letter(
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
    client = TestClient(app)

    save_response = client.put(
        "/api/v1/audit/dead-letters/saved/critical-unresolved",
        json={"description": "Critical unresolved", "preset": "critical", "priority": "critical"},
        headers={"Authorization": "Bearer test-admin-token"},
    )
    list_response = client.get(
        "/api/v1/audit/dead-letters/saved",
        headers={"Authorization": "Bearer test-admin-token"},
    )
    get_response = client.get(
        "/api/v1/audit/dead-letters/saved/critical-unresolved",
        headers={"Authorization": "Bearer test-admin-token"},
    )
    items_response = client.get(
        "/api/v1/audit/dead-letters/saved/critical-unresolved/items",
        headers={"Authorization": "Bearer test-admin-token"},
    )
    ack_response = client.post(
        "/api/v1/audit/dead-letters/saved/critical-unresolved/ack",
        headers={"Authorization": "Bearer test-admin-token"},
    )
    delete_response = client.delete(
        "/api/v1/audit/dead-letters/saved/critical-unresolved",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert save_response.status_code == 200
    assert save_response.json()["name"] == "critical-unresolved"
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["name"] == "critical-unresolved"
    assert get_response.status_code == 200
    assert get_response.json()["filters"] == {"preset": "critical", "priority": "critical"}
    assert items_response.status_code == 200
    assert items_response.json()["items"][0]["id"] == first["id"]
    assert ack_response.status_code == 200
    assert ack_response.json()["count"] == 1
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True


def test_dead_letters_can_be_acknowledged() -> None:
    app = create_app()
    record = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    client = TestClient(app)

    response = client.post(
        f"/api/v1/audit/dead-letters/{record['id']}/ack",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == record["id"]
    assert response.json()["acknowledged_at"] is not None
    assert app.state.container.audit_repository.events[-1]["event_type"] == "dead_letter_acknowledged"
    assert app.state.container.audit_repository.events[-1]["details"]["requested_by"] == "admin_api"


def test_dead_letters_ack_records_operator_id_when_provided() -> None:
    app = create_app()
    record = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    client = TestClient(app)

    response = client.post(
        f"/api/v1/audit/dead-letters/{record['id']}/ack",
        headers={
            "Authorization": "Bearer test-admin-token",
            "X-Operator-Id": "ops-user-1",
        },
    )

    assert response.status_code == 200
    assert app.state.container.audit_repository.events[-1]["event_type"] == "dead_letter_acknowledged"
    assert app.state.container.audit_repository.events[-1]["details"]["requested_by"] == "ops-user-1"


def test_dead_letter_ack_returns_not_found_for_unknown_record() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/audit/dead-letters/dlq-missing/ack",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 404


def test_dead_letters_can_be_acknowledged_in_bulk() -> None:
    app = create_app()
    first = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    second = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=43,
        message_id=9,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hi",
        details={"outcome": "retry"},
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/audit/dead-letters/ack-bulk",
        json={"dead_letter_ids": [first["id"], second["id"], "dlq-missing"]},
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert [item["id"] for item in payload["acknowledged"]] == [first["id"], second["id"]]
    assert payload["not_found"] == ["dlq-missing"]
    assert app.state.container.audit_repository.events[-1]["event_type"] == "dead_letter_acknowledged"
    assert app.state.container.audit_repository.events[-1]["details"]["requested_by"] == "admin_api"


def test_dead_letters_bulk_ack_records_operator_id_when_provided() -> None:
    app = create_app()
    record = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/audit/dead-letters/ack-bulk",
        json={"dead_letter_ids": [record["id"]]},
        headers={
            "Authorization": "Bearer test-admin-token",
            "X-Operator-Id": "ops-user-1",
        },
    )

    assert response.status_code == 200
    assert app.state.container.audit_repository.events[-1]["event_type"] == "dead_letter_acknowledged"
    assert app.state.container.audit_repository.events[-1]["details"]["requested_by"] == "ops-user-1"


def test_dead_letters_can_be_acknowledged_by_query() -> None:
    app = create_app()
    first = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    second = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=9,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask again",
        details={"outcome": "retry"},
    )
    app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=43,
        message_id=10,
        reason="delivery_rejected",
        attempt=1,
        text="/ask hi",
        details={"outcome": "reject"},
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/audit/dead-letters/ack-query",
        json={
            "acknowledged": False,
            "reason": "retry_budget_exhausted",
            "peer_id": 42,
            "limit": 10,
        },
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] == 2
    assert payload["count"] == 2
    assert [item["id"] for item in payload["acknowledged"]] == [first["id"], second["id"]]


def test_dead_letters_list_supports_named_presets() -> None:
    app = create_app()
    first = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    second = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=9,
        reason="delivery_rejected",
        attempt=1,
        text="/ask later",
        details={"outcome": "reject"},
    )
    app.state.container.dead_letter_repository.ack_dead_letter(second["id"])
    client = TestClient(app)

    response = client.get(
        "/api/v1/audit/dead-letters?preset=retry_exhausted",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == first["id"]


def test_dead_letters_list_allows_explicit_filters_to_override_preset() -> None:
    app = create_app()
    app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    second = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=9,
        reason="delivery_rejected",
        attempt=1,
        text="/ask later",
        details={"outcome": "reject"},
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/audit/dead-letters?preset=retry_exhausted&reason=delivery_rejected",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == second["id"]


def test_dead_letters_query_ack_respects_limit_and_operator_id() -> None:
    app = create_app()
    first = app.state.container.dead_letter_repository.append_dead_letter(
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
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask again",
        details={"outcome": "retry"},
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/audit/dead-letters/ack-query",
        json={
            "acknowledged": False,
            "reason": "retry_budget_exhausted",
            "peer_id": 42,
            "limit": 1,
        },
        headers={
            "Authorization": "Bearer test-admin-token",
            "X-Operator-Id": "ops-user-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] == 2
    assert payload["count"] == 1
    assert payload["acknowledged"][0]["id"] == first["id"]
    assert app.state.container.audit_repository.events[-1]["details"]["requested_by"] == "ops-user-1"
    assert app.state.container.dead_letter_repository.list_dead_letters()[1]["acknowledged_at"] is None


def test_dead_letters_query_ack_supports_time_window_filters() -> None:
    app = create_app()
    app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=8,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask hello",
        details={"outcome": "retry"},
    )
    second = app.state.container.dead_letter_repository.append_dead_letter(
        peer_id=42,
        message_id=9,
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask later",
        details={"outcome": "retry"},
    )
    app.state.container.dead_letter_repository.items[0]["ts"] = "2026-03-17T10:00:00Z"
    app.state.container.dead_letter_repository.items[1]["ts"] = "2026-03-17T11:00:00Z"
    client = TestClient(app)

    response = client.post(
        "/api/v1/audit/dead-letters/ack-query",
        json={
            "acknowledged": False,
            "created_after": "2026-03-17T10:30:00Z",
            "created_before": "2026-03-17T11:30:00Z",
            "limit": 10,
        },
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] == 1
    assert payload["count"] == 1
    assert payload["acknowledged"][0]["id"] == second["id"]
    assert app.state.container.dead_letter_repository.list_dead_letters()[0]["acknowledged_at"] is None


def test_dead_letters_query_ack_supports_acknowledged_time_filters() -> None:
    app = create_app()
    first = app.state.container.dead_letter_repository.append_dead_letter(
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
        reason="retry_budget_exhausted",
        attempt=3,
        text="/ask later",
        details={"outcome": "retry"},
    )
    app.state.container.dead_letter_repository.ack_dead_letter(first["id"])
    app.state.container.dead_letter_repository.items[0]["acknowledged_at"] = "2026-03-17T10:00:00Z"
    app.state.container.dead_letter_repository.items[1]["acknowledged_at"] = None
    client = TestClient(app)

    response = client.post(
        "/api/v1/audit/dead-letters/ack-query",
        json={
            "acknowledged": True,
            "acknowledged_after": "2026-03-17T09:30:00Z",
            "acknowledged_before": "2026-03-17T10:30:00Z",
            "limit": 10,
        },
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] == 1
    assert payload["count"] == 1
    assert payload["acknowledged"][0]["id"] == first["id"]


def test_dead_letters_query_ack_supports_named_presets() -> None:
    app = create_app()
    first = app.state.container.dead_letter_repository.append_dead_letter(
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
    client = TestClient(app)

    response = client.post(
        "/api/v1/audit/dead-letters/ack-query",
        json={"preset": "retry_exhausted", "limit": 10},
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] == 1
    assert payload["count"] == 1
    assert payload["acknowledged"][0]["id"] == first["id"]


def test_dead_letters_list_supports_critical_preset() -> None:
    app = create_app()
    critical = app.state.container.dead_letter_repository.append_dead_letter(
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
    client = TestClient(app)

    response = client.get(
        "/api/v1/audit/dead-letters?preset=critical",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["id"] == critical["id"]
