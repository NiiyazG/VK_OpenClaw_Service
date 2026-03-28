"""Static system payloads for the initial API skeleton."""

from __future__ import annotations

from vk_openclaw_service.core.settings import RuntimeSettings, get_settings
from vk_openclaw_service.domain.checkpoints import CheckpointState


def build_status_payload(
    settings: RuntimeSettings | None = None,
    *,
    paired_peers_count: int = 0,
    last_checkpoint: CheckpointState | None = None,
    dead_letter_count: int = 0,
    last_dead_letter_at: str | None = None,
    dead_letter_priority_counts: dict[str, int] | None = None,
    dead_letter_reason_counts: dict[str, int] | None = None,
    saved_query_count: int = 0,
    worker_identity: dict[str, object] | None = None,
    storage_mode: str = "file",
    storage_ready: bool = True,
    storage_reason: str | None = None,
    storage_fallback_mode: str | None = None,
) -> dict:
    runtime_settings = settings or get_settings()
    return {
        "mode": runtime_settings.vk_mode,
        "worker": {
            "state": "idle",
            "lag_messages": 0,
            "last_success_at": None,
            "identity": worker_identity
            or {
                "configured_owner_id": runtime_settings.worker_id,
                "lease_key": runtime_settings.worker_lease_key,
                "held": False,
                "owner_id": None,
                "held_by_self": False,
                "stale": False,
                "acquired_at": None,
                "refreshed_at": None,
                "previous_owner_id": None,
                "takeover_at": None,
                "takeover_count": 0,
                "ttl_seconds": runtime_settings.worker_lease_ttl_sec,
            },
        },
        "paired_peers": paired_peers_count,
        "storage": {
            "mode": storage_mode,
            "ready": storage_ready,
            "reason": storage_reason,
            "fallback_mode": storage_fallback_mode,
        },
        "limits": {
            "rate_per_min": runtime_settings.rate_per_min,
            "max_attachments": runtime_settings.max_attachments,
            "max_file_mb": runtime_settings.max_file_mb,
        },
        "checkpoint": {
            "peer_id": last_checkpoint.peer_id if last_checkpoint else None,
            "last_committed_message_id": (
                last_checkpoint.last_committed_message_id if last_checkpoint else None
            ),
        },
        "dead_letters": {
            "count": dead_letter_count,
            "last_dead_letter_at": last_dead_letter_at,
            "by_priority": dead_letter_priority_counts
            or {
                "normal": 0,
                "high": 0,
                "critical": 0,
            },
            "by_reason": dead_letter_reason_counts or {},
        },
        "saved_queries": {
            "count": saved_query_count,
        },
    }

def build_health_payload(
    *,
    has_vk_token: bool,
    storage_ready: bool,
    storage_reason: str | None,
    dead_letter_count: int = 0,
    dead_letter_top_reason: str | None = None,
    worker_identity: dict[str, object] | None = None,
) -> dict:
    checks = [
        {
            "component": "api",
            "status": "ok",
            "reason": None,
        },
        {
            "component": "settings",
            "status": "ok",
            "reason": None,
        },
        {
            "component": "storage",
            "status": "ok" if storage_ready else "degraded",
            "reason": None if storage_ready else storage_reason,
        },
        {
            "component": "dead_letters",
            "status": "ok" if dead_letter_count == 0 else "degraded",
            "reason": (
                None
                if dead_letter_count == 0
                else (
                    f"{dead_letter_count}_dead_letters_present:{dead_letter_top_reason}"
                    if dead_letter_top_reason is not None
                    else f"{dead_letter_count}_dead_letters_present"
                )
            ),
        },
        {
            "component": "worker_lease",
            "status": (
                "degraded"
                if worker_identity is not None and bool(worker_identity.get("stale"))
                else "ok"
            ),
            "reason": (
                "stale_lease_detected"
                if worker_identity is not None and bool(worker_identity.get("stale"))
                else (
                    None
                    if worker_identity is None or worker_identity.get("owner_id") is None
                    else f"owner:{worker_identity['owner_id']}"
                )
            ),
        },
    ]
    status_value = "ok"
    if not storage_ready or dead_letter_count > 0:
        status_value = "degraded"
    if worker_identity is not None and bool(worker_identity.get("stale")):
        status_value = "degraded"
    if has_vk_token:
        checks.append(
            {
                "component": "vk_client",
                "status": "ok",
                "reason": None,
            }
        )
    else:
        checks.append(
            {
                "component": "vk_client",
                "status": "degraded",
                "reason": "missing_access_token",
            }
        )
        status_value = "degraded"
    return {
        "status": status_value,
        "checks": checks,
    }
