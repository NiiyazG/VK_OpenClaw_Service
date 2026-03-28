"""HTTP-based VK API client."""

from __future__ import annotations

import json
import secrets
import urllib.parse
import urllib.request
from dataclasses import dataclass

from vk_openclaw_service.workers.polling_service import HistoryMessage


@dataclass(frozen=True)
class VkApiError(Exception):
    code: int
    message: str

    def __str__(self) -> str:
        return f"VK API error {self.code}: {self.message}"


class VkApiClient:
    api_url = "https://api.vk.com/method/"
    api_version = "5.199"

    def __init__(self, token: str) -> None:
        self.token = token

    def call(self, method: str, params: dict[str, object]) -> object:
        body = urllib.parse.urlencode(
            {"access_token": self.token, "v": self.api_version, **params}
        ).encode("utf-8")
        request = urllib.request.Request(
            self.api_url + method,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
            payload = json.loads(response.read().decode("utf-8"))
        if "error" in payload:
            error = payload["error"]
            raise VkApiError(code=int(error["error_code"]), message=str(error["error_msg"]))
        return payload["response"]

    def get_history(self, peer_id: int) -> list[HistoryMessage]:
        response = self.call("messages.getHistory", {"peer_id": peer_id, "count": 200})
        items = response.get("items", []) if isinstance(response, dict) else []
        return [
            HistoryMessage(
                message_id=int(item.get("id", 0)),
                peer_id=int(item.get("peer_id", peer_id)),
                text=str(item.get("text", "")),
                outgoing=bool(item.get("out", 0)),
            )
            for item in items
        ]

    def send_text(self, peer_id: int, text: str) -> int:
        response = self.call(
            "messages.send",
            {
                "peer_id": peer_id,
                "random_id": secrets.randbelow(2_147_483_647 - 1) + 1,
                "message": text,
            },
        )
        if not isinstance(response, int):
            raise ValueError("messages_send_response_was_not_int")
        return response
