"""Pairing API schemas."""

from __future__ import annotations

from pydantic import BaseModel


class PairingCodeRequest(BaseModel):
    peer_id: int


class PairingCodeResponse(BaseModel):
    peer_id: int
    code: str
    expires_at: str


class PairingVerifyRequest(BaseModel):
    peer_id: int
    code: str
