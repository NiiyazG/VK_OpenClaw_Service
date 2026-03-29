"""Pairing routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from vk_openclaw_service.api.deps import get_container, require_admin_token
from vk_openclaw_service.api.schemas.pairing import (
    PairingCodeRequest,
    PairingCodeResponse,
    PairingPeersResponse,
    PairingVerifyRequest,
)
from vk_openclaw_service.bootstrap.container import AppContainer


router = APIRouter(prefix="/api/v1/pairing", tags=["pairing"])


@router.post("/code", response_model=PairingCodeResponse, dependencies=[Depends(require_admin_token)])
def create_pairing_code(
    request: PairingCodeRequest,
    container: AppContainer = Depends(get_container),
) -> dict:
    return container.pairing_service.create_code(request.peer_id)


@router.post("/verify")
def verify_pairing_code(
    request: PairingVerifyRequest,
    container: AppContainer = Depends(get_container),
) -> dict:
    return container.pairing_service.verify_code(request.peer_id, request.code)


@router.get("/peers", response_model=PairingPeersResponse, dependencies=[Depends(require_admin_token)])
def list_paired_peers(
    container: AppContainer = Depends(get_container),
) -> dict:
    items = container.pairing_repository.list_paired_peers()
    return {"items": items, "count": len(items)}
