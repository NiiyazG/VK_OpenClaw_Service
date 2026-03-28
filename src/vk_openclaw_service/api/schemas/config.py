"""Config API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ConfigValidateRequest(BaseModel):
    source: str
    settings: dict[str, Any] | None = None


class ConfigIssue(BaseModel):
    field: str
    message: str


class ConfigValidateResponse(BaseModel):
    valid: bool
    issues: list[ConfigIssue]
