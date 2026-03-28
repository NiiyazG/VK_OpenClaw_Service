"""Config validation routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from vk_openclaw_service.api.deps import require_admin_token
from vk_openclaw_service.api.schemas.config import ConfigValidateRequest, ConfigValidateResponse
from vk_openclaw_service.services.config_validation import validate_settings


router = APIRouter(prefix="/api/v1/config", tags=["config"], dependencies=[Depends(require_admin_token)])


@router.post("/validate", response_model=ConfigValidateResponse)
def validate_config(request: ConfigValidateRequest) -> dict:
    return validate_settings(request.settings)
