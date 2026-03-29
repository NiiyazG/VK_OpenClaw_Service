from fastapi.testclient import TestClient

from vk_openclaw_service.main import create_app


def test_pairing_code_endpoint_creates_code_for_allowed_peer() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/pairing/code",
        json={"peer_id": 42},
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["code"]) == 8
    assert payload["peer_id"] == 42


def test_pairing_code_endpoint_rejects_non_allowlisted_peer(runtime_settings_factory) -> None:
    client = TestClient(create_app(settings=runtime_settings_factory(allowed_peers={42})))

    response = client.post(
        "/api/v1/pairing/code",
        json={"peer_id": 999},
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 403


def test_pairing_code_endpoint_uses_custom_allowed_peers_from_settings(runtime_settings_factory) -> None:
    client = TestClient(create_app(settings=runtime_settings_factory(allowed_peers={77})))

    accepted = client.post(
        "/api/v1/pairing/code",
        json={"peer_id": 77},
        headers={"Authorization": "Bearer test-admin-token"},
    )
    rejected = client.post(
        "/api/v1/pairing/code",
        json={"peer_id": 42},
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert accepted.status_code == 200
    assert rejected.status_code == 403


def test_pairing_verify_endpoint_marks_peer_paired(runtime_settings_factory) -> None:
    client = TestClient(create_app(settings=runtime_settings_factory(pair_code_ttl_sec=900)))
    code_response = client.post(
        "/api/v1/pairing/code",
        json={"peer_id": 42},
        headers={"Authorization": "Bearer test-admin-token"},
    )
    code = code_response.json()["code"]

    verify_response = client.post(
        "/api/v1/pairing/verify",
        json={"peer_id": 42, "code": code},
    )

    assert verify_response.status_code == 200
    assert verify_response.json() == {"status": "paired"}

    peers_response = client.get(
        "/api/v1/pairing/peers",
        headers={"Authorization": "Bearer test-admin-token"},
    )
    assert peers_response.status_code == 200
    assert peers_response.json() == {"items": [42], "count": 1}


def test_pairing_verify_endpoint_rejects_invalid_code(runtime_settings_factory) -> None:
    client = TestClient(create_app(settings=runtime_settings_factory(pair_code_ttl_sec=900)))
    client.post(
        "/api/v1/pairing/code",
        json={"peer_id": 42},
        headers={"Authorization": "Bearer test-admin-token"},
    )

    verify_response = client.post(
        "/api/v1/pairing/verify",
        json={"peer_id": 42, "code": "BADCODE1"},
    )

    assert verify_response.status_code == 403


def test_pairing_peers_endpoint_requires_admin_token() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/pairing/peers")
    assert response.status_code == 401
