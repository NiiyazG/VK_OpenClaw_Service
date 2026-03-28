"""Runtime configuration validation service."""

from __future__ import annotations


REQUIRED_FIELDS = (
    "vk_access_token",
    "admin_api_token",
    "openclaw_command",
)
VALID_PERSISTENCE_MODES = {"file", "memory", "database"}
POSITIVE_NUMBER_FIELDS = (
    "worker_interval_sec",
    "worker_retry_backoff_sec",
    "worker_max_backoff_sec",
    "worker_lease_ttl_sec",
    "retry_queue_max_attempts",
    "retry_queue_base_backoff_sec",
    "retry_queue_max_backoff_sec",
)
BOOLEAN_FIELDS = ("free_text_ask_enabled",)


def validate_settings(settings: dict | None) -> dict:
    payload = settings or {}
    issues: list[dict[str, str]] = []
    for field in REQUIRED_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            issues.append({"field": field, "message": "must not be empty"})
    persistence_mode = payload.get("persistence_mode", "file")
    if persistence_mode is not None:
        if not isinstance(persistence_mode, str) or persistence_mode not in VALID_PERSISTENCE_MODES:
            issues.append({"field": "persistence_mode", "message": "must be one of: database, file, memory"})
        elif persistence_mode == "database":
            for field in ("database_dsn", "redis_dsn"):
                value = payload.get(field)
                if not isinstance(value, str) or not value.strip():
                    issues.append({"field": field, "message": "must not be empty when persistence_mode=database"})
    for field in POSITIVE_NUMBER_FIELDS:
        if field not in payload:
            continue
        value = payload.get(field)
        if not isinstance(value, (int, float)) or value <= 0:
            issues.append({"field": field, "message": "must be > 0"})
    for field in BOOLEAN_FIELDS:
        if field not in payload:
            continue
        value = payload.get(field)
        if not isinstance(value, bool):
            issues.append({"field": field, "message": "must be boolean"})
    return {
        "valid": not issues,
        "issues": issues,
    }
