from fastapi.testclient import TestClient

from vk_openclaw_service.main import create_app


def test_status_and_config_validation_share_runtime_settings(runtime_settings_factory) -> None:
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

    status_response = client.get(
        "/api/v1/status",
        headers={"Authorization": "Bearer custom-token"},
    )
    config_response = client.post(
        "/api/v1/config/validate",
        json={
            "source": "payload",
            "settings": {
                "vk_access_token": "token",
                "admin_api_token": "admin",
                "openclaw_command": "/usr/local/bin/openclaw",
            },
        },
        headers={"Authorization": "Bearer custom-token"},
    )

    assert status_response.status_code == 200
    assert status_response.json()["mode"] == "e2e-required"
    assert status_response.json()["limits"]["rate_per_min"] == 9
    assert config_response.status_code == 200
    assert config_response.json() == {"valid": True, "issues": []}
