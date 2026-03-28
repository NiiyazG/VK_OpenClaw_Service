"""OpenClaw command execution."""

from __future__ import annotations

import re
import shlex
import subprocess  # nosec B404


TRACE_RE = re.compile(r"Traceback \(most recent call last\):", re.MULTILINE)
PATH_RE = re.compile(r"(/[^\s]+)+")


class OpenClawExecutionError(RuntimeError):
    """Raised when OpenClaw returns a non-zero exit code."""


class OpenClawTimeoutError(TimeoutError):
    """Raised when OpenClaw exceeds the configured timeout."""


def sanitize_output(text: str) -> str:
    cleaned = TRACE_RE.sub("[traceback omitted]", text)
    cleaned = PATH_RE.sub("[path]", cleaned)
    return cleaned.strip() or "OpenClaw returned an empty response."


def run_openclaw_command(command: str, prompt: str, *, timeout_seconds: int) -> str:
    try:
        completed = subprocess.run(
            shlex.split(command),
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )  # nosec B603
    except subprocess.TimeoutExpired as exc:
        raise OpenClawTimeoutError(f"OpenClaw timed out after {timeout_seconds} seconds") from exc

    if completed.returncode != 0:
        raise OpenClawExecutionError(sanitize_output(completed.stderr))
    return sanitize_output(completed.stdout)
