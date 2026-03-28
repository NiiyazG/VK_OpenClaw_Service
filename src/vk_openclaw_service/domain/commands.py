"""Command parsing and policy decisions for incoming messages."""

from __future__ import annotations

import json
from dataclasses import dataclass


SAFE_COMMANDS = {"/help", "/status", "/pair", "/ask", "/ask-file", "/ask-image", "/encrypt-test"}


@dataclass(frozen=True)
class CommandDecision:
    action: str
    reply: str = ""
    argument: str = ""


def parse_command(message_text: str) -> tuple[str, str]:
    text = message_text.strip()
    if not text:
        return "", ""
    parts = text.split(maxsplit=1)
    command = parts[0]
    argument = parts[1] if len(parts) > 1 else ""
    return command, argument.strip()


def handle_command(peer_id: int, text: str, paired: bool, status_payload: dict) -> CommandDecision:
    del peer_id
    stripped = text.strip()
    if not stripped:
        return CommandDecision(action="ignored")
    if not stripped.startswith("/"):
        return CommandDecision(action="reply", reply="Unknown or blocked command.", argument="")

    command, argument = parse_command(stripped)

    if command not in SAFE_COMMANDS:
        return CommandDecision(action="reply", reply="Unknown or blocked command.", argument="")

    if command == "/help":
        return CommandDecision(
            action="reply",
            reply=(
                "Commands: /help, /status, /pair <code>, /ask <text>, /ask-file <text>, /ask-image <text>, "
                "/encrypt-test. When free-text mode is enabled, any non-slash message after pairing is treated as /ask."
            ),
        )

    if command == "/pair":
        return CommandDecision(action="pair", argument=argument)

    if command == "/status":
        if not paired:
            return CommandDecision(action="reply", reply="Pair this phone first with /pair <code>.")
        return CommandDecision(action="reply", reply=json.dumps(status_payload))

    if not paired:
        return CommandDecision(action="reply", reply="Pair this phone first with /pair <code>.")

    if command in {"/ask", "/ask-file", "/ask-image"}:
        return CommandDecision(action="openclaw", argument=argument)

    if command == "/encrypt-test":
        return CommandDecision(action="reply", reply="Encryption path is working.")

    return CommandDecision(action="reply", reply="Unknown or blocked command.", argument="")


def handle_command_with_free_text(
    peer_id: int,
    text: str,
    paired: bool,
    status_payload: dict,
    *,
    free_text_ask_enabled: bool,
) -> CommandDecision:
    stripped = text.strip()
    if not stripped:
        return CommandDecision(action="ignored")
    if stripped.startswith("/"):
        return handle_command(peer_id=peer_id, text=stripped, paired=paired, status_payload=status_payload)
    if not free_text_ask_enabled:
        return CommandDecision(action="reply", reply="Unknown or blocked command.", argument="")
    if not paired:
        return CommandDecision(action="reply", reply="Pair this phone first with /pair <code>.")
    return CommandDecision(action="openclaw", argument=stripped)
