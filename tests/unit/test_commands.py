from vk_openclaw_service.domain.commands import (
    CommandDecision,
    handle_command,
    handle_command_with_free_text,
    parse_command,
)


def test_parse_command_splits_command_and_argument() -> None:
    assert parse_command("/ask hello world") == ("/ask", "hello world")
    assert parse_command("/status") == ("/status", "")


def test_help_command_returns_static_reply() -> None:
    decision = handle_command(
        peer_id=42,
        text="/help",
        paired=True,
        status_payload={"mode": "plain"},
    )

    assert decision.action == "reply"
    assert "/ask <text>" in decision.reply
    assert "free-text mode" in decision.reply


def test_status_command_returns_status_payload_for_paired_peer() -> None:
    decision = handle_command(
        peer_id=42,
        text="/status",
        paired=True,
        status_payload={"mode": "plain"},
    )

    assert decision.action == "reply"
    assert decision.reply == '{"mode": "plain"}'


def test_pair_command_returns_pair_action() -> None:
    decision = handle_command(
        peer_id=42,
        text="/pair ABC12345",
        paired=False,
        status_payload={"mode": "plain"},
    )

    assert decision.action == "pair"
    assert decision.argument == "ABC12345"


def test_ask_command_requires_pairing() -> None:
    decision = handle_command(
        peer_id=42,
        text="/ask hello",
        paired=False,
        status_payload={"mode": "plain"},
    )

    assert decision.action == "reply"
    assert "Pair this phone first" in decision.reply


def test_ask_command_creates_openclaw_action_for_paired_peer() -> None:
    decision = handle_command(
        peer_id=42,
        text="/ask hello",
        paired=True,
        status_payload={"mode": "plain"},
    )

    assert decision.action == "openclaw"
    assert decision.argument == "hello"


def test_unknown_command_is_rejected() -> None:
    decision = handle_command(
        peer_id=42,
        text="/unknown",
        paired=True,
        status_payload={"mode": "plain"},
    )

    assert decision == CommandDecision(action="reply", reply="Unknown or blocked command.", argument="")


def test_handle_command_ignores_empty_text() -> None:
    decision = handle_command(
        peer_id=42,
        text="   ",
        paired=True,
        status_payload={"mode": "plain"},
    )

    assert decision == CommandDecision(action="ignored", reply="", argument="")


def test_free_text_routes_to_openclaw_when_enabled_for_paired_peer() -> None:
    decision = handle_command_with_free_text(
        peer_id=42,
        text="hello openclaw",
        paired=True,
        status_payload={"mode": "plain"},
        free_text_ask_enabled=True,
    )

    assert decision == CommandDecision(action="openclaw", argument="hello openclaw")


def test_free_text_requires_pairing_when_enabled() -> None:
    decision = handle_command_with_free_text(
        peer_id=42,
        text="hello openclaw",
        paired=False,
        status_payload={"mode": "plain"},
        free_text_ask_enabled=True,
    )

    assert decision == CommandDecision(
        action="reply",
        reply="Pair this phone first with /pair <code>.",
        argument="",
    )


def test_free_text_rejected_when_disabled() -> None:
    decision = handle_command_with_free_text(
        peer_id=42,
        text="hello openclaw",
        paired=True,
        status_payload={"mode": "plain"},
        free_text_ask_enabled=False,
    )

    assert decision == CommandDecision(action="reply", reply="Unknown or blocked command.", argument="")
