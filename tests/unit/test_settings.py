from vk_openclaw_service.core.settings import RuntimeSettings
from vk_openclaw_service.services.system_status import build_status_payload


def test_runtime_settings_expose_configured_admin_token_and_limits() -> None:
    settings = RuntimeSettings(
        admin_api_token="secret-token",
        vk_access_token="vk-token",
        allowed_peers={42, 43},
        persistence_mode="database",
        database_dsn="postgresql://user:pass@localhost:5432/app",
        redis_dsn="redis://localhost:6379/0",
        vk_mode="e2e-optional",
        pair_code_ttl_sec=900,
        rate_per_min=12,
        max_attachments=3,
        max_file_mb=20,
        openclaw_command="/usr/local/bin/openclaw",
        openclaw_timeout_sec=45,
        state_dir="./state",
        worker_interval_sec=7.5,
        worker_retry_backoff_sec=1.5,
        worker_max_backoff_sec=25.0,
        worker_id="worker-a",
        worker_lease_ttl_sec=17,
        worker_lease_key="custom-worker-lease",
        retry_queue_max_attempts=4,
        retry_queue_base_backoff_sec=6.5,
        retry_queue_max_backoff_sec=55.0,
        replay_ttl_sec=123,
        retry_queue_key="custom-retry",
        free_text_ask_enabled=True,
    )

    assert settings.admin_api_token == "secret-token"
    assert settings.vk_access_token == "vk-token"
    assert settings.allowed_peers == {42, 43}
    assert settings.persistence_mode == "database"
    assert settings.database_dsn == "postgresql://user:pass@localhost:5432/app"
    assert settings.redis_dsn == "redis://localhost:6379/0"
    assert settings.vk_mode == "e2e-optional"
    assert settings.pair_code_ttl_sec == 900
    assert settings.rate_per_min == 12
    assert settings.max_attachments == 3
    assert settings.max_file_mb == 20
    assert settings.openclaw_command == "/usr/local/bin/openclaw"
    assert settings.openclaw_timeout_sec == 45
    assert settings.state_dir == "./state"
    assert settings.worker_interval_sec == 7.5
    assert settings.worker_retry_backoff_sec == 1.5
    assert settings.worker_max_backoff_sec == 25.0
    assert settings.worker_id == "worker-a"
    assert settings.worker_lease_ttl_sec == 17
    assert settings.worker_lease_key == "custom-worker-lease"
    assert settings.retry_queue_max_attempts == 4
    assert settings.retry_queue_base_backoff_sec == 6.5
    assert settings.retry_queue_max_backoff_sec == 55.0
    assert settings.replay_ttl_sec == 123
    assert settings.retry_queue_key == "custom-retry"
    assert settings.free_text_ask_enabled is True


def test_status_payload_uses_runtime_settings_values() -> None:
    settings = RuntimeSettings(
        admin_api_token="secret-token",
        vk_access_token="vk-token",
        allowed_peers={42},
        persistence_mode="file",
        database_dsn="",
        redis_dsn="",
        vk_mode="e2e-required",
        pair_code_ttl_sec=900,
        rate_per_min=9,
        max_attachments=4,
        max_file_mb=15,
        openclaw_command="/usr/local/bin/openclaw",
        openclaw_timeout_sec=45,
        state_dir="./state",
        worker_interval_sec=5.0,
        worker_retry_backoff_sec=1.0,
        worker_max_backoff_sec=30.0,
        worker_id="worker-default",
        worker_lease_ttl_sec=15,
        worker_lease_key="vk-openclaw:worker-lease",
        retry_queue_max_attempts=3,
        retry_queue_base_backoff_sec=5.0,
        retry_queue_max_backoff_sec=60.0,
        replay_ttl_sec=300,
        retry_queue_key="vk-openclaw:retry",
        free_text_ask_enabled=False,
    )

    payload = build_status_payload(settings=settings, paired_peers_count=0, last_checkpoint=None)

    assert payload["mode"] == "e2e-required"
    assert payload["limits"]["rate_per_min"] == 9
    assert payload["limits"]["max_attachments"] == 4
    assert payload["limits"]["max_file_mb"] == 15
    assert payload["dead_letters"]["count"] == 0
    assert payload["dead_letters"]["last_dead_letter_at"] is None
    assert payload["worker"]["identity"]["configured_owner_id"] == "worker-default"
    assert payload["worker"]["identity"]["stale"] is False
    assert payload["worker"]["identity"]["acquired_at"] is None
    assert payload["worker"]["identity"]["refreshed_at"] is None
    assert payload["worker"]["identity"]["previous_owner_id"] is None
    assert payload["worker"]["identity"]["takeover_at"] is None
    assert payload["worker"]["identity"]["takeover_count"] == 0
