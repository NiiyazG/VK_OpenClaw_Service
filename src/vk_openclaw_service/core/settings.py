"""Runtime settings abstraction."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import AbstractSet

_LOGGER = logging.getLogger(__name__)
_DOTENV_LOADED = False

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - tested via monkeypatch
    load_dotenv = None  # type: ignore[assignment]


@dataclass(frozen=True)
class RuntimeSettings:
    admin_api_token: str = "test-admin-token"
    vk_access_token: str = ""
    allowed_peers: frozenset[int] = frozenset({42})
    persistence_mode: str = "file"
    database_dsn: str = ""
    redis_dsn: str = ""
    vk_mode: str = "plain"
    pair_code_ttl_sec: int = 600
    rate_per_min: int = 6
    max_attachments: int = 2
    max_file_mb: int = 10
    openclaw_command: str = "openclaw"
    openclaw_timeout_sec: int = 120
    state_dir: str = "./state"
    worker_interval_sec: float = 5.0
    worker_retry_backoff_sec: float = 1.0
    worker_max_backoff_sec: float = 30.0
    worker_id: str = "worker-default"
    worker_lease_ttl_sec: int = 15
    worker_lease_key: str = "vk-openclaw:worker-lease"
    retry_queue_max_attempts: int = 3
    retry_queue_base_backoff_sec: float = 5.0
    retry_queue_max_backoff_sec: float = 60.0
    replay_ttl_sec: int = 300
    retry_queue_key: str = "vk-openclaw:retry"
    free_text_ask_enabled: bool = False


def load_settings_from_env(env: dict[str, str] | None = None) -> RuntimeSettings:
    source = env or os.environ
    return RuntimeSettings(
        admin_api_token=source.get("ADMIN_API_TOKEN", RuntimeSettings.admin_api_token),
        vk_access_token=source.get("VK_ACCESS_TOKEN", RuntimeSettings.vk_access_token),
        allowed_peers=frozenset(_parse_peer_ids(source.get("VK_ALLOWED_PEERS"), RuntimeSettings.allowed_peers)),
        persistence_mode=_parse_persistence_mode(
            source.get("PERSISTENCE_MODE"), RuntimeSettings.persistence_mode
        ),
        database_dsn=source.get("DATABASE_DSN", RuntimeSettings.database_dsn),
        redis_dsn=source.get("REDIS_DSN", RuntimeSettings.redis_dsn),
        vk_mode=source.get("VK_MODE", RuntimeSettings.vk_mode),
        pair_code_ttl_sec=_parse_positive_int(source.get("PAIR_CODE_TTL_SEC"), RuntimeSettings.pair_code_ttl_sec),
        rate_per_min=_parse_positive_int(source.get("VK_RATE_LIMIT_PER_MIN"), RuntimeSettings.rate_per_min),
        max_attachments=_parse_positive_int(source.get("VK_MAX_ATTACHMENTS"), RuntimeSettings.max_attachments),
        max_file_mb=_parse_positive_int(source.get("VK_MAX_FILE_MB"), RuntimeSettings.max_file_mb),
        openclaw_command=source.get("OPENCLAW_COMMAND", RuntimeSettings.openclaw_command),
        openclaw_timeout_sec=_parse_positive_int(source.get("OPENCLAW_TIMEOUT_SEC"), RuntimeSettings.openclaw_timeout_sec),
        state_dir=source.get("STATE_DIR", RuntimeSettings.state_dir),
        worker_interval_sec=_parse_positive_float(source.get("WORKER_INTERVAL_SEC"), RuntimeSettings.worker_interval_sec),
        worker_retry_backoff_sec=_parse_positive_float(
            source.get("WORKER_RETRY_BACKOFF_SEC"), RuntimeSettings.worker_retry_backoff_sec
        ),
        worker_max_backoff_sec=_parse_positive_float(
            source.get("WORKER_MAX_BACKOFF_SEC"), RuntimeSettings.worker_max_backoff_sec
        ),
        worker_id=source.get("WORKER_ID", RuntimeSettings.worker_id),
        worker_lease_ttl_sec=_parse_positive_int(
            source.get("WORKER_LEASE_TTL_SEC"), RuntimeSettings.worker_lease_ttl_sec
        ),
        worker_lease_key=source.get("WORKER_LEASE_KEY", RuntimeSettings.worker_lease_key),
        retry_queue_max_attempts=_parse_positive_int(
            source.get("RETRY_QUEUE_MAX_ATTEMPTS"), RuntimeSettings.retry_queue_max_attempts
        ),
        retry_queue_base_backoff_sec=_parse_positive_float(
            source.get("RETRY_QUEUE_BASE_BACKOFF_SEC"), RuntimeSettings.retry_queue_base_backoff_sec
        ),
        retry_queue_max_backoff_sec=_parse_positive_float(
            source.get("RETRY_QUEUE_MAX_BACKOFF_SEC"), RuntimeSettings.retry_queue_max_backoff_sec
        ),
        replay_ttl_sec=_parse_positive_int(source.get("REPLAY_TTL_SEC"), RuntimeSettings.replay_ttl_sec),
        retry_queue_key=source.get("RETRY_QUEUE_KEY", RuntimeSettings.retry_queue_key),
        free_text_ask_enabled=_parse_bool(
            source.get("FREE_TEXT_ASK_ENABLED"), RuntimeSettings.free_text_ask_enabled
        ),
    )


def _parse_positive_int(raw: str | None, default: int) -> int:
    try:
        value = int(raw) if raw is not None else default
    except ValueError:
        return default
    return value if value > 0 else default


def _parse_peer_ids(raw: str | None, default: AbstractSet[int]) -> set[int]:
    if raw is None:
        return set(default)
    peers: set[int] = set()
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            peers.add(int(value))
        except ValueError:
            continue
    return peers or set(default)


def _parse_positive_float(raw: str | None, default: float) -> float:
    try:
        value = float(raw) if raw is not None else default
    except ValueError:
        return default
    return value if value > 0 else default


def _parse_persistence_mode(raw: str | None, default: str) -> str:
    if raw is None:
        return default
    value = raw.strip().lower()
    return value if value in {"file", "memory", "database"} else default


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _project_env_local_path() -> Path:
    return Path(__file__).parent.parent.parent.parent / ".env.local"


def _ensure_env_loaded() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    env_path = _project_env_local_path()
    if load_dotenv is None:
        if env_path.exists():
            _LOGGER.warning("python-dotenv is not installed; .env.local was not auto-loaded")
        _DOTENV_LOADED = True
        return
    load_dotenv(dotenv_path=env_path, override=False)
    _DOTENV_LOADED = True


_settings: RuntimeSettings | None = None


def reload_settings() -> RuntimeSettings:
    global _settings, _DOTENV_LOADED
    _DOTENV_LOADED = False
    _ensure_env_loaded()
    _settings = load_settings_from_env()
    return _settings


def get_settings(reload: bool = False) -> RuntimeSettings:
    global _settings
    if reload or _settings is None:
        return reload_settings()
    return _settings
