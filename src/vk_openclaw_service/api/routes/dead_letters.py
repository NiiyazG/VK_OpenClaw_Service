"""Dead-letter routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from typing import cast

from vk_openclaw_service.api.deps import get_container, get_operator_id, require_admin_token
from vk_openclaw_service.bootstrap.container import AppContainer
from vk_openclaw_service.services.dead_letter_service import (
    acknowledge_dead_letter,
    acknowledge_dead_letters,
    acknowledge_dead_letters_by_query,
    delete_saved_query,
    get_saved_query,
    list_dead_letters_filtered,
    list_dead_letter_query_presets,
    list_saved_queries,
    save_saved_query,
)


router = APIRouter(prefix="/api/v1/audit", tags=["audit"], dependencies=[Depends(require_admin_token)])


class BulkAckRequest(BaseModel):
    dead_letter_ids: list[str]


class BulkAckQueryRequest(BaseModel):
    preset: str | None = None
    acknowledged: bool | None = None
    reason: str | None = None
    severity: str | None = None
    priority: str | None = None
    peer_id: int | None = None
    created_after: str | None = None
    created_before: str | None = None
    acknowledged_after: str | None = None
    acknowledged_before: str | None = None
    limit: int = 100


class SavedQueryRequest(BaseModel):
    description: str | None = None
    preset: str | None = None
    acknowledged: bool | None = None
    reason: str | None = None
    severity: str | None = None
    priority: str | None = None
    peer_id: int | None = None
    created_after: str | None = None
    created_before: str | None = None
    acknowledged_after: str | None = None
    acknowledged_before: str | None = None


@router.get("/dead-letters/presets")
def get_dead_letter_presets() -> dict[str, object]:
    return list_dead_letter_query_presets()


@router.get("/dead-letters/saved")
def get_saved_dead_letter_queries(container: AppContainer = Depends(get_container)) -> dict[str, object]:
    return list_saved_queries(container.saved_query_repository)


@router.get("/dead-letters/saved/{query_name}")
def get_saved_dead_letter_query(query_name: str, container: AppContainer = Depends(get_container)) -> dict[str, object]:
    record = get_saved_query(container.saved_query_repository, name=query_name)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="saved_query_not_found")
    return record


@router.put("/dead-letters/saved/{query_name}")
def put_saved_dead_letter_query(
    query_name: str,
    payload: SavedQueryRequest,
    container: AppContainer = Depends(get_container),
    operator_id: str = Depends(get_operator_id),
) -> dict[str, object]:
    filters: dict[str, object] = {
        "preset": payload.preset,
        "acknowledged": payload.acknowledged,
        "reason": payload.reason,
        "severity": payload.severity,
        "priority": payload.priority,
        "peer_id": payload.peer_id,
        "created_after": payload.created_after,
        "created_before": payload.created_before,
        "acknowledged_after": payload.acknowledged_after,
        "acknowledged_before": payload.acknowledged_before,
    }
    normalized_filters = {key: value for key, value in filters.items() if value is not None}
    return save_saved_query(
        container.saved_query_repository,
        name=query_name,
        description=payload.description,
        filters=normalized_filters,
        audit_repository=container.audit_repository,
        operator_id=operator_id,
    )


@router.delete("/dead-letters/saved/{query_name}")
def delete_saved_dead_letter_query(
    query_name: str,
    container: AppContainer = Depends(get_container),
    operator_id: str = Depends(get_operator_id),
) -> dict[str, object]:
    if not delete_saved_query(
        container.saved_query_repository,
        name=query_name,
        audit_repository=container.audit_repository,
        operator_id=operator_id,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="saved_query_not_found")
    return {"deleted": True, "name": query_name}


@router.get("/dead-letters")
def get_dead_letters(
    limit: int = Query(default=50, ge=1, le=100),
    preset: str | None = Query(default=None),
    acknowledged: bool | None = Query(default=None),
    reason: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    peer_id: int | None = Query(default=None),
    created_after: str | None = Query(default=None),
    created_before: str | None = Query(default=None),
    acknowledged_after: str | None = Query(default=None),
    acknowledged_before: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
) -> dict[str, object]:
    return list_dead_letters_filtered(
        container.dead_letter_repository,
        limit=limit,
        preset=preset,
        acknowledged=acknowledged,
        reason=reason,
        severity=severity,
        priority=priority,
        peer_id=peer_id,
        created_after=created_after,
        created_before=created_before,
        acknowledged_after=acknowledged_after,
        acknowledged_before=acknowledged_before,
    )


@router.post("/dead-letters/{dead_letter_id}/ack")
def ack_dead_letter(
    dead_letter_id: str,
    container: AppContainer = Depends(get_container),
    operator_id: str = Depends(get_operator_id),
) -> dict[str, object]:
    record = acknowledge_dead_letter(
        container.dead_letter_repository,
        dead_letter_id=dead_letter_id,
        audit_repository=container.audit_repository,
        operator_id=operator_id,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dead_letter_not_found")
    return record


@router.post("/dead-letters/ack-bulk")
def ack_dead_letters_bulk(
    payload: BulkAckRequest,
    container: AppContainer = Depends(get_container),
    operator_id: str = Depends(get_operator_id),
) -> dict[str, object]:
    return acknowledge_dead_letters(
        container.dead_letter_repository,
        dead_letter_ids=payload.dead_letter_ids,
        audit_repository=container.audit_repository,
        operator_id=operator_id,
    )


@router.post("/dead-letters/ack-query")
def ack_dead_letters_query(
    payload: BulkAckQueryRequest,
    container: AppContainer = Depends(get_container),
    operator_id: str = Depends(get_operator_id),
) -> dict[str, object]:
    return acknowledge_dead_letters_by_query(
        container.dead_letter_repository,
        preset=payload.preset,
        acknowledged=payload.acknowledged,
        reason=payload.reason,
        severity=payload.severity,
        priority=payload.priority,
        peer_id=payload.peer_id,
        created_after=payload.created_after,
        created_before=payload.created_before,
        acknowledged_after=payload.acknowledged_after,
        acknowledged_before=payload.acknowledged_before,
        limit=payload.limit,
        audit_repository=container.audit_repository,
        operator_id=operator_id,
    )


@router.get("/dead-letters/saved/{query_name}/items")
def get_saved_dead_letter_query_items(
    query_name: str,
    limit: int = Query(default=50, ge=1, le=100),
    container: AppContainer = Depends(get_container),
) -> dict[str, object]:
    record = get_saved_query(container.saved_query_repository, name=query_name)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="saved_query_not_found")
    filters = cast(dict[str, object], record["filters"])
    return list_dead_letters_filtered(
        container.dead_letter_repository,
        limit=limit,
        preset=_filter_str(filters, "preset"),
        acknowledged=_filter_bool(filters, "acknowledged"),
        reason=_filter_str(filters, "reason"),
        severity=_filter_str(filters, "severity"),
        priority=_filter_str(filters, "priority"),
        peer_id=_filter_int(filters, "peer_id"),
        created_after=_filter_str(filters, "created_after"),
        created_before=_filter_str(filters, "created_before"),
        acknowledged_after=_filter_str(filters, "acknowledged_after"),
        acknowledged_before=_filter_str(filters, "acknowledged_before"),
    )


@router.post("/dead-letters/saved/{query_name}/ack")
def ack_saved_dead_letter_query(
    query_name: str,
    limit: int = Query(default=100, ge=1, le=500),
    container: AppContainer = Depends(get_container),
    operator_id: str = Depends(get_operator_id),
) -> dict[str, object]:
    record = get_saved_query(container.saved_query_repository, name=query_name)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="saved_query_not_found")
    filters = cast(dict[str, object], record["filters"])
    return acknowledge_dead_letters_by_query(
        container.dead_letter_repository,
        preset=_filter_str(filters, "preset"),
        acknowledged=_filter_bool(filters, "acknowledged"),
        reason=_filter_str(filters, "reason"),
        severity=_filter_str(filters, "severity"),
        priority=_filter_str(filters, "priority"),
        peer_id=_filter_int(filters, "peer_id"),
        created_after=_filter_str(filters, "created_after"),
        created_before=_filter_str(filters, "created_before"),
        acknowledged_after=_filter_str(filters, "acknowledged_after"),
        acknowledged_before=_filter_str(filters, "acknowledged_before"),
        limit=limit,
        audit_repository=container.audit_repository,
        operator_id=operator_id,
    )


def _filter_bool(filters: dict[str, object], key: str) -> bool | None:
    value = filters.get(key)
    return value if isinstance(value, bool) else None


def _filter_str(filters: dict[str, object], key: str) -> str | None:
    value = filters.get(key)
    return value if isinstance(value, str) else None


def _filter_int(filters: dict[str, object], key: str) -> int | None:
    value = filters.get(key)
    return value if isinstance(value, int) else None
