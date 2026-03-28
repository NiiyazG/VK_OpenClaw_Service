"""Reply delivery service."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from vk_openclaw_service.infra.vk.transport import VkDeliveryOutcome


class TextSender(Protocol):
    def send_text(self, peer_id: int, text: str) -> int:
        """Send a text message."""


def deliver_reply(
    *,
    sender: TextSender,
    peer_id: int,
    text: str,
    classify_failure: Callable[[Exception], VkDeliveryOutcome],
) -> VkDeliveryOutcome | None:
    try:
        sender.send_text(peer_id, text)
    except Exception as exc:
        return classify_failure(exc)
    return None
