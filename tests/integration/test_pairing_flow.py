from fastapi.testclient import TestClient

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
