"""API dependencies."""

from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from vk_openclaw_service.bootstrap.container import AppContainer


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def require_admin_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    if authorization != f"Bearer {get_container(request).settings.admin_api_token}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized",
        )


def get_operator_id(x_operator_id: str | None = Header(default=None)) -> str:
    value = (x_operator_id or "").strip()
    return value or "admin_api"
