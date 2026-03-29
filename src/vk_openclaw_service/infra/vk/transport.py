"""VK transport error classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import socket
from urllib.error import URLError


class VkDeliveryOutcome(StrEnum):
    RETRY = "retry"
    REJECT = "reject"


@dataclass(frozen=True)
class VkApiError(Exception):
    code: int
    message: str

    def __str__(self) -> str:
        return f"VK API error {self.code}: {self.message}"


RETRYABLE_API_CODES = {6, 9, 10}


def _vk_error_code(error: Exception) -> int | None:
    code = getattr(error, "code", None)
    if isinstance(code, int):
        return code
    return None


def classify_vk_send_failure(error: Exception) -> VkDeliveryOutcome:
    if isinstance(error, (TimeoutError, ConnectionError, URLError, socket.gaierror)):
        return VkDeliveryOutcome.RETRY
    vk_code = _vk_error_code(error)
    if vk_code is not None:
        if vk_code in RETRYABLE_API_CODES:
            return VkDeliveryOutcome.RETRY
        return VkDeliveryOutcome.REJECT
    return VkDeliveryOutcome.REJECT
