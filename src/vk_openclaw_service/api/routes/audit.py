"""Audit routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from vk_openclaw_service.api.deps import get_container, get_operator_id, require_admin_token
from vk_openclaw_service.bootstrap.container import AppContainer
from vk_openclaw_service.services.audit_service import (
    build_audit_summary,
    get_worker_lease_snapshot,
    list_audit_events,
    reset_stale_worker_lease,
)


router = APIRouter(prefix="/api/v1/audit", tags=["audit"], dependencies=[Depends(require_admin_token)])


@router.get("/events")
def get_audit_events(
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    container: AppContainer = Depends(get_container),
) -> dict:
    return list_audit_events(container.audit_repository, cursor=cursor, limit=limit)


@router.get("/summary")
def get_audit_summary(container: AppContainer = Depends(get_container)) -> dict[str, object]:
    return build_audit_summary(
        container.audit_repository,
        container.dead_letter_repository,
        container.saved_query_repository,
        container.worker_lease,
    )


@router.get("/worker-lease")
def get_worker_lease(container: AppContainer = Depends(get_container)) -> dict[str, object]:
    return get_worker_lease_snapshot(container.worker_lease)


@router.post("/worker-lease/reset")
def reset_worker_lease(
    container: AppContainer = Depends(get_container),
    operator_id: str = Depends(get_operator_id),
) -> dict[str, object]:
    released = reset_stale_worker_lease(container.worker_lease, operator_id=operator_id)
    if released is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="worker_lease_not_stale_or_missing")
    return {
        "reset": True,
        "released": released,
        "current": container.worker_lease.snapshot(),
    }
