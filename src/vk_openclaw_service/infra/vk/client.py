"""VK client interface."""

from __future__ import annotations

from typing import Protocol

from vk_openclaw_service.workers.polling_service import HistoryMessage


class VkClient(Protocol):
    def get_history(self, peer_id: int) -> list[HistoryMessage]:
        """Return history items for a peer."""
