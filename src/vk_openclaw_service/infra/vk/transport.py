"""VK transport error classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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


def classify_vk_send_failure(error: Exception) -> VkDeliveryOutcome:
    if isinstance(error, (TimeoutError, ConnectionError)):
        return VkDeliveryOutcome.RETRY
    if isinstance(error, VkApiError):
        if error.code in RETRYABLE_API_CODES:
            return VkDeliveryOutcome.RETRY
        return VkDeliveryOutcome.REJECT
    return VkDeliveryOutcome.REJECT
