"""Message processing service."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from vk_openclaw_service.domain.commands import handle_command_with_free_text


class RateLimiter(Protocol):
    def allow(self, *, peer_id: int, bucket: str) -> bool: ...


def process_message(
    peer_id: int,
    text: str,
    paired: bool,
    status_payload: dict,
    openclaw_runner: Callable[[str], str],
    rate_limiter: RateLimiter | None = None,
    free_text_ask_enabled: bool = False,
) -> dict:
    decision = handle_command_with_free_text(
        peer_id=peer_id,
        text=text,
        paired=paired,
        status_payload=status_payload,
        free_text_ask_enabled=free_text_ask_enabled,
    )

    if decision.action == "openclaw":
        if rate_limiter is not None and not rate_limiter.allow(peer_id=peer_id, bucket="openclaw"):
            return {"action": "reply", "reply": "Rate limit exceeded. Try again later."}
        return {"action": "reply", "reply": openclaw_runner(decision.argument)}
    if decision.action == "ignored":
        return {"action": "ignored"}
    if decision.action == "pair":
        return {"action": "pair", "code": decision.argument}
    return {"action": "reply", "reply": decision.reply}
