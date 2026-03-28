"""System status routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from vk_openclaw_service.api.deps import get_container, require_admin_token
from vk_openclaw_service.bootstrap.container import AppContainer
from vk_openclaw_service.services.system_status import build_health_payload, build_status_payload


router = APIRouter(prefix="/api/v1", tags=["system"], dependencies=[Depends(require_admin_token)])


@router.get("/status")
def get_status(container: AppContainer = Depends(get_container)) -> dict:
    checkpoints = container.checkpoint_repository.list_states()
    dead_letters = [
        item for item in container.dead_letter_repository.list_dead_letters() if item.get("acknowledged_at") is None
    ]
    priority_counts = {
        "normal": 0,
        "high": 0,
        "critical": 0,
    }
    reason_counts: dict[str, int] = {}
    for item in dead_letters:
        priority = str(item.get("priority") or "normal")
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
        reason = str(item.get("reason") or "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    last_checkpoint = max(checkpoints, key=lambda item: item.last_committed_message_id) if checkpoints else None
    last_dead_letter = dead_letters[-1] if dead_letters else None
    return build_status_payload(
        container.settings,
        paired_peers_count=len(container.pairing_repository.list_paired_peers()),
        last_checkpoint=last_checkpoint,
        dead_letter_count=len(dead_letters),
        last_dead_letter_at=last_dead_letter["ts"] if last_dead_letter else None,
        dead_letter_priority_counts=priority_counts,
        dead_letter_reason_counts=reason_counts,
        saved_query_count=len(container.saved_query_repository.list_queries()),
        worker_identity=container.worker_lease.snapshot(),
        storage_mode=container.storage.mode,
        storage_ready=container.storage.ready,
        storage_reason=container.storage.reason,
        storage_fallback_mode=container.storage.fallback_mode,
    )


@router.get("/health")
def get_health(container: AppContainer = Depends(get_container)) -> dict:
    dead_letters = [
        item for item in container.dead_letter_repository.list_dead_letters() if item.get("acknowledged_at") is None
    ]
    reason_counts: dict[str, int] = {}
    for item in dead_letters:
        reason = str(item.get("reason") or "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    top_reason = None
    if reason_counts:
        top_reason = max(reason_counts.items(), key=lambda item: item[1])[0]
    return build_health_payload(
        has_vk_token=bool(container.settings.vk_access_token),
        storage_ready=container.storage.ready,
        storage_reason=container.storage.reason,
        dead_letter_count=len(dead_letters),
        dead_letter_top_reason=top_reason,
        worker_identity=container.worker_lease.snapshot(),
    )
