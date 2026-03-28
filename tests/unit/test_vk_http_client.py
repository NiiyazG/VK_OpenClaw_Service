import json
from unittest.mock import patch

from vk_openclaw_service.infra.vk.client_http import VkApiClient, VkApiError
from vk_openclaw_service.workers.polling_service import HistoryMessage


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_get_history_maps_vk_response_to_history_messages() -> None:
    client = VkApiClient(token="token")
    payload = {
        "response": {
            "items": [
                {"id": 1, "peer_id": 42, "text": "/ask hello", "out": 0},
                {"id": 2, "peer_id": 42, "text": "/status", "out": 1},
            ]
        }
    }

    with patch("vk_openclaw_service.infra.vk.client_http.urllib.request.urlopen", return_value=FakeResponse(payload)):
        history = client.get_history(42)

    assert history == [
        HistoryMessage(message_id=1, peer_id=42, text="/ask hello", outgoing=False),
        HistoryMessage(message_id=2, peer_id=42, text="/status", outgoing=True),
    ]


def test_send_text_returns_vk_response_id() -> None:
    client = VkApiClient(token="token")
    payload = {"response": 123}

    with patch("vk_openclaw_service.infra.vk.client_http.urllib.request.urlopen", return_value=FakeResponse(payload)):
        response = client.send_text(42, "hello")

    assert response == 123


def test_vk_api_error_is_raised_from_error_payload() -> None:
    client = VkApiClient(token="token")
    payload = {"error": {"error_code": 901, "error_msg": "can't send messages"}}

    with patch("vk_openclaw_service.infra.vk.client_http.urllib.request.urlopen", return_value=FakeResponse(payload)):
        try:
            client.send_text(42, "hello")
        except VkApiError as exc:
            assert exc.code == 901
        else:
            raise AssertionError("expected VkApiError")
