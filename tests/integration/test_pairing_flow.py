from fastapi.testclient import TestClient

from vk_openclaw_service.core.settings import RuntimeSettings
from vk_openclaw_service.main import create_app


def test_pairing_flow_updates_shared_repository_state() -> None:
    app = create_app()
    client = TestClient(app)

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
    audit_response = client.get(
        "/api/v1/audit/events",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    repository = app.state.container.pairing_repository
    stored_record = repository.get_code(42)

    assert code_response.status_code == 200
    assert verify_response.status_code == 200
    assert verify_response.json() == {"status": "paired"}
    assert repository.is_paired(42) is True
    assert stored_record is not None
    assert stored_record.consumed_at is not None
    assert [item["event_type"] for item in audit_response.json()["items"][-2:]] == [
        "pairing_code_created",
        "pairing_verified",
    ]


def test_pairing_persists_across_app_restart(tmp_path) -> None:
    settings = RuntimeSettings(
        admin_api_token="admin-token",
        vk_access_token="vk-token",
        allowed_peers=frozenset({42}),
        persistence_mode="file",
        state_dir=str(tmp_path / "state"),
    )
    app1 = create_app(settings=settings)
    client1 = TestClient(app1)
    code_response = client1.post(
        "/api/v1/pairing/code",
        json={"peer_id": 42},
        headers={"Authorization": "Bearer admin-token"},
    )
    code = code_response.json()["code"]
    verify_response = client1.post("/api/v1/pairing/verify", json={"peer_id": 42, "code": code})
    assert verify_response.status_code == 200

    app2 = create_app(settings=settings)
    repository = app2.state.container.pairing_repository
    assert repository.is_paired(42) is True
    assert 42 in repository.list_paired_peers()
