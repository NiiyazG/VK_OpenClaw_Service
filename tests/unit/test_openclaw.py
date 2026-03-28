import subprocess
from unittest.mock import patch

from vk_openclaw_service.domain.openclaw import OpenClawExecutionError, OpenClawTimeoutError, run_openclaw_command


def test_run_openclaw_command_returns_stdout_on_success() -> None:
    completed = subprocess.CompletedProcess(
        args=["openclaw"],
        returncode=0,
        stdout="answer",
        stderr="",
    )

    with patch("vk_openclaw_service.domain.openclaw.subprocess.run", return_value=completed) as run_mock:
        result = run_openclaw_command("openclaw", "hello", timeout_seconds=5)

    assert result == "answer"
    run_mock.assert_called_once()


def test_run_openclaw_command_raises_timeout_error() -> None:
    with patch(
        "vk_openclaw_service.domain.openclaw.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["openclaw"], timeout=5),
    ):
        try:
            run_openclaw_command("openclaw", "hello", timeout_seconds=5)
        except OpenClawTimeoutError as exc:
            assert "timed out" in str(exc)
        else:
            raise AssertionError("expected OpenClawTimeoutError")


def test_run_openclaw_command_sanitizes_stderr_on_failure() -> None:
    completed = subprocess.CompletedProcess(
        args=["openclaw"],
        returncode=1,
        stdout="",
        stderr="Traceback (most recent call last): /tmp/secret",
    )

    with patch("vk_openclaw_service.domain.openclaw.subprocess.run", return_value=completed):
        try:
            run_openclaw_command("openclaw", "hello", timeout_seconds=5)
        except OpenClawExecutionError as exc:
            assert "Traceback" not in str(exc)
            assert "/tmp/secret" not in str(exc)
        else:
            raise AssertionError("expected OpenClawExecutionError")
