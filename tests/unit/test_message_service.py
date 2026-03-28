from vk_openclaw_service.services.message_service import process_message


def test_process_message_returns_help_reply() -> None:
    result = process_message(
        peer_id=42,
        text="/help",
        paired=True,
        status_payload={"mode": "plain"},
        openclaw_runner=lambda prompt: "unused",
    )

    assert result["action"] == "reply"
    assert "/ask <text>" in result["reply"]
    assert "free-text mode" in result["reply"]


def test_process_message_returns_status_reply() -> None:
    result = process_message(
        peer_id=42,
        text="/status",
        paired=True,
        status_payload={"mode": "plain"},
        openclaw_runner=lambda prompt: "unused",
    )

    assert result == {"action": "reply", "reply": '{"mode": "plain"}'}


def test_process_message_executes_openclaw_for_ask() -> None:
    result = process_message(
        peer_id=42,
        text="/ask hello",
        paired=True,
        status_payload={"mode": "plain"},
        openclaw_runner=lambda prompt: f"ran:{prompt}",
    )

    assert result == {"action": "reply", "reply": "ran:hello"}


def test_process_message_returns_pair_action() -> None:
    result = process_message(
        peer_id=42,
        text="/pair ABC12345",
        paired=False,
        status_payload={"mode": "plain"},
        openclaw_runner=lambda prompt: "unused",
    )

    assert result == {"action": "pair", "code": "ABC12345"}


def test_process_message_rejects_openclaw_when_rate_limited() -> None:
    result = process_message(
        peer_id=42,
        text="/ask hello",
        paired=True,
        status_payload={"mode": "plain"},
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        rate_limiter=type("Limiter", (), {"allow": lambda self, **kwargs: False})(),
    )

    assert result == {"action": "reply", "reply": "Rate limit exceeded. Try again later."}


def test_process_message_routes_free_text_when_enabled() -> None:
    result = process_message(
        peer_id=42,
        text="hello",
        paired=True,
        status_payload={"mode": "plain"},
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        free_text_ask_enabled=True,
    )

    assert result == {"action": "reply", "reply": "ran:hello"}


def test_process_message_ignores_empty_text() -> None:
    result = process_message(
        peer_id=42,
        text="   ",
        paired=True,
        status_payload={"mode": "plain"},
        openclaw_runner=lambda prompt: f"ran:{prompt}",
        free_text_ask_enabled=True,
    )

    assert result == {"action": "ignored"}
