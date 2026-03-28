from fastapi.testclient import TestClient

from vk_openclaw_service.main import create_app


def test_config_validate_accepts_valid_payload() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/config/validate",
        json={
            "source": "payload",
            "settings": {
                "vk_access_token": "token",
                "admin_api_token": "admin",
                "openclaw_command": "/usr/local/bin/openclaw",
            },
        },
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "issues": []}


def test_config_validate_reports_missing_fields() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/config/validate",
        json={
            "source": "payload",
            "settings": {
                "vk_access_token": "",
                "admin_api_token": "admin",
                "openclaw_command": "",
            },
        },
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert {"field": "vk_access_token", "message": "must not be empty"} in payload["issues"]
    assert {"field": "openclaw_command", "message": "must not be empty"} in payload["issues"]


def test_config_validate_requires_admin_token() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/config/validate",
        json={"source": "payload", "settings": {}},
    )

    assert response.status_code == 401


def test_config_validate_rejects_database_mode_without_storage_dsns() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/config/validate",
        json={
            "source": "payload",
            "settings": {
                "vk_access_token": "token",
                "admin_api_token": "admin",
                "openclaw_command": "/usr/local/bin/openclaw",
                "persistence_mode": "database",
                "database_dsn": "",
                "redis_dsn": "",
            },
        },
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert {
        "field": "database_dsn",
        "message": "must not be empty when persistence_mode=database",
    } in response.json()["issues"]
    assert {
        "field": "redis_dsn",
        "message": "must not be empty when persistence_mode=database",
    } in response.json()["issues"]


def test_config_validate_rejects_invalid_worker_settings() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/config/validate",
        json={
            "source": "payload",
            "settings": {
                "vk_access_token": "token",
                "admin_api_token": "admin",
                "openclaw_command": "/usr/local/bin/openclaw",
                "worker_interval_sec": 0,
                "worker_retry_backoff_sec": -1,
                "worker_lease_ttl_sec": 0,
                "retry_queue_max_attempts": 0,
                "retry_queue_base_backoff_sec": 0,
                "retry_queue_max_backoff_sec": -5,
            },
        },
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert {"field": "worker_interval_sec", "message": "must be > 0"} in response.json()["issues"]
    assert {"field": "worker_retry_backoff_sec", "message": "must be > 0"} in response.json()["issues"]
    assert {"field": "worker_lease_ttl_sec", "message": "must be > 0"} in response.json()["issues"]
    assert {"field": "retry_queue_max_attempts", "message": "must be > 0"} in response.json()["issues"]
    assert {"field": "retry_queue_base_backoff_sec", "message": "must be > 0"} in response.json()["issues"]
    assert {"field": "retry_queue_max_backoff_sec", "message": "must be > 0"} in response.json()["issues"]


def test_config_validate_rejects_invalid_free_text_flag_type() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/config/validate",
        json={
            "source": "payload",
            "settings": {
                "vk_access_token": "token",
                "admin_api_token": "admin",
                "openclaw_command": "/usr/local/bin/openclaw",
                "free_text_ask_enabled": "yes",
            },
        },
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert {"field": "free_text_ask_enabled", "message": "must be boolean"} in response.json()["issues"]
