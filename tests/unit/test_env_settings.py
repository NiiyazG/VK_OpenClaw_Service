from vk_openclaw_service.core.settings import RuntimeSettings, load_settings_from_env


def test_load_settings_from_env_reads_overrides() -> None:
    env = {
        "ADMIN_API_TOKEN": "env-admin",
        "VK_ACCESS_TOKEN": "vk-token",
        "VK_ALLOWED_PEERS": "42,43,44",
        "PERSISTENCE_MODE": "database",
        "DATABASE_DSN": "postgresql://user:pass@localhost:5432/app",
        "REDIS_DSN": "redis://localhost:6379/0",
        "VK_MODE": "e2e-required",
        "PAIR_CODE_TTL_SEC": "900",
        "VK_RATE_LIMIT_PER_MIN": "11",
        "VK_MAX_ATTACHMENTS": "5",
        "VK_MAX_FILE_MB": "21",
        "OPENCLAW_COMMAND": "/usr/local/bin/openclaw",
        "OPENCLAW_TIMEOUT_SEC": "120",
        "STATE_DIR": "./state",
        "WORKER_INTERVAL_SEC": "7.5",
        "WORKER_RETRY_BACKOFF_SEC": "1.5",
        "WORKER_MAX_BACKOFF_SEC": "25.0",
        "WORKER_ID": "worker-a",
        "WORKER_LEASE_TTL_SEC": "17",
        "WORKER_LEASE_KEY": "custom-worker-lease",
        "RETRY_QUEUE_MAX_ATTEMPTS": "4",
        "RETRY_QUEUE_BASE_BACKOFF_SEC": "6.5",
        "RETRY_QUEUE_MAX_BACKOFF_SEC": "55.0",
        "REPLAY_TTL_SEC": "123",
        "RETRY_QUEUE_KEY": "custom-retry",
        "FREE_TEXT_ASK_ENABLED": "true",
    }

    settings = load_settings_from_env(env)

    assert settings == RuntimeSettings(
        admin_api_token="env-admin",
        vk_access_token="vk-token",
        allowed_peers={42, 43, 44},
        persistence_mode="database",
        database_dsn="postgresql://user:pass@localhost:5432/app",
        redis_dsn="redis://localhost:6379/0",
        vk_mode="e2e-required",
        pair_code_ttl_sec=900,
        rate_per_min=11,
        max_attachments=5,
        max_file_mb=21,
        openclaw_command="/usr/local/bin/openclaw",
        openclaw_timeout_sec=120,
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


def test_load_settings_from_env_falls_back_to_defaults() -> None:
    settings = load_settings_from_env({})

    assert settings == RuntimeSettings()
    assert settings.worker_id == "worker-default"


def test_load_settings_from_env_ignores_invalid_ints() -> None:
    settings = load_settings_from_env(
        {
            "VK_RATE_LIMIT_PER_MIN": "oops",
            "VK_MAX_ATTACHMENTS": "-1",
            "VK_MAX_FILE_MB": "bad",
        }
    )

    assert settings.rate_per_min == 6
    assert settings.max_attachments == 2
    assert settings.max_file_mb == 10
    assert settings.pair_code_ttl_sec == 600
    assert settings.openclaw_timeout_sec == 120
    assert settings.state_dir == "./state"
    assert settings.persistence_mode == "file"
    assert settings.database_dsn == ""
    assert settings.redis_dsn == ""
    assert settings.worker_interval_sec == 5.0
    assert settings.worker_retry_backoff_sec == 1.0
    assert settings.worker_max_backoff_sec == 30.0
    assert settings.worker_id == "worker-default"
    assert settings.worker_lease_ttl_sec == 15
    assert settings.worker_lease_key == "vk-openclaw:worker-lease"
    assert settings.retry_queue_max_attempts == 3
    assert settings.retry_queue_base_backoff_sec == 5.0
    assert settings.retry_queue_max_backoff_sec == 60.0
    assert settings.replay_ttl_sec == 300
    assert settings.retry_queue_key == "vk-openclaw:retry"
    assert settings.free_text_ask_enabled is False


def test_load_settings_from_env_ignores_invalid_peer_values() -> None:
    settings = load_settings_from_env({"VK_ALLOWED_PEERS": "42,abc,,43"})

    assert settings.allowed_peers == {42, 43}


def test_load_settings_from_env_ignores_invalid_ttl() -> None:
    settings = load_settings_from_env({"PAIR_CODE_TTL_SEC": "-1"})

    assert settings.pair_code_ttl_sec == 600


def test_load_settings_from_env_ignores_invalid_worker_float_values() -> None:
    settings = load_settings_from_env(
        {
            "WORKER_INTERVAL_SEC": "bad",
            "WORKER_RETRY_BACKOFF_SEC": "0",
            "WORKER_MAX_BACKOFF_SEC": "-2",
            "WORKER_LEASE_TTL_SEC": "-3",
            "RETRY_QUEUE_MAX_ATTEMPTS": "0",
            "RETRY_QUEUE_BASE_BACKOFF_SEC": "bad",
            "RETRY_QUEUE_MAX_BACKOFF_SEC": "0",
        }
    )

    assert settings.worker_interval_sec == 5.0
    assert settings.worker_retry_backoff_sec == 1.0
    assert settings.worker_max_backoff_sec == 30.0
    assert settings.worker_lease_ttl_sec == 15
    assert settings.retry_queue_max_attempts == 3
    assert settings.retry_queue_base_backoff_sec == 5.0
    assert settings.retry_queue_max_backoff_sec == 60.0


def test_load_settings_from_env_ignores_invalid_replay_ttl() -> None:
    settings = load_settings_from_env({"REPLAY_TTL_SEC": "-1"})

    assert settings.replay_ttl_sec == 300


def test_load_settings_from_env_rejects_unknown_persistence_mode() -> None:
    settings = load_settings_from_env({"PERSISTENCE_MODE": "weird"})

    assert settings.persistence_mode == "file"


def test_load_settings_from_env_parses_free_text_flag() -> None:
    enabled = load_settings_from_env({"FREE_TEXT_ASK_ENABLED": "yes"})
    disabled = load_settings_from_env({"FREE_TEXT_ASK_ENABLED": "no"})
    invalid = load_settings_from_env({"FREE_TEXT_ASK_ENABLED": "maybe"})

    assert enabled.free_text_ask_enabled is True
    assert disabled.free_text_ask_enabled is False
    assert invalid.free_text_ask_enabled is False
