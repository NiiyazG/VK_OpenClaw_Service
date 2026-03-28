"""Application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from vk_openclaw_service.api.routes.audit import router as audit_router
from vk_openclaw_service.api.routes.config import router as config_router
from vk_openclaw_service.api.routes.dead_letters import router as dead_letter_router
from vk_openclaw_service.api.routes.pairing import router as pairing_router
from vk_openclaw_service.api.routes.system import router as system_router
from vk_openclaw_service.bootstrap.container import build_container
from vk_openclaw_service.core.settings import RuntimeSettings


def create_app(*, settings: RuntimeSettings | None = None) -> FastAPI:
    app = FastAPI(title="vk-openclaw-service", version="0.0.1")
    app.state.container = build_container(settings)
    app.include_router(system_router)
    app.include_router(pairing_router)
    app.include_router(config_router)
    app.include_router(audit_router)
    app.include_router(dead_letter_router)
    return app


app = create_app()
