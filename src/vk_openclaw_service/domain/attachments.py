"""Attachment validation policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AttachmentSource(StrEnum):
    PHOTO = "photo"
    DOC = "doc"


@dataclass(frozen=True)
class AttachmentCandidate:
    source: AttachmentSource
    original_name: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class AttachmentPolicy:
    allowed_mime: set[str]
    max_file_mb: int


@dataclass(frozen=True)
class AcceptedAttachment:
    safe_name: str
    mime: str
    size_bytes: int


class AttachmentRejection(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def validate_attachment(candidate: AttachmentCandidate, policy: AttachmentPolicy) -> AcceptedAttachment:
    if candidate.size_bytes > policy.max_file_mb * 1024 * 1024:
        raise AttachmentRejection("size_limit")
    if candidate.content_type not in policy.allowed_mime:
        raise AttachmentRejection("unsupported_mime")

    if candidate.content_type == "image/jpeg":
        safe_name = _ensure_extension(candidate.original_name, ".jpg")
    elif candidate.content_type == "application/pdf":
        safe_name = _ensure_extension(candidate.original_name, ".pdf")
    else:
        safe_name = candidate.original_name

    return AcceptedAttachment(
        safe_name=safe_name,
        mime=candidate.content_type,
        size_bytes=candidate.size_bytes,
    )


def _ensure_extension(name: str, extension: str) -> str:
    stem = name.rsplit(".", 1)[0]
    return f"{stem}{extension}"
