from __future__ import annotations

import sys
import types
from unittest.mock import patch

from vk_openclaw_service.cli import main


def test_cli_install_dispatches_to_installer() -> None:
    with patch("vk_openclaw_service.cli.installer.run_install", return_value=0) as install_mock:
        exit_code = main(["install", "--non-interactive"])

    assert exit_code == 0
    install_mock.assert_called_once()


def test_cli_start_dispatches_to_systemd_start() -> None:
    with patch("vk_openclaw_service.cli.installer.systemd_user", return_value=0) as command_mock:
        exit_code = main(["start"])

    assert exit_code == 0
    command_mock.assert_called_once_with("start")


def test_cli_status_dispatches_to_systemd_status() -> None:
    with patch("vk_openclaw_service.cli.installer.systemd_user_status", return_value=0) as status_mock:
        exit_code = main(["status"])

    assert exit_code == 0
    status_mock.assert_called_once_with()


def test_cli_run_worker_forwards_flags() -> None:
    with patch("vk_openclaw_service.cli.worker_main", return_value=0) as worker_mock:
        exit_code = main(
            [
                "run-worker",
                "--once",
                "--interval-seconds",
                "7",
                "--retry-backoff-seconds",
                "1.5",
                "--max-backoff-seconds",
                "20",
            ]
        )

    assert exit_code == 0
    worker_mock.assert_called_once_with(
        [
            "--once",
            "--interval-seconds",
            "7.0",
            "--retry-backoff-seconds",
            "1.5",
            "--max-backoff-seconds",
            "20.0",
        ]
    )


def test_cli_run_api_calls_uvicorn(monkeypatch) -> None:
    called: list[tuple[str, str, int]] = []

    def fake_run(app: str, *, host: str, port: int) -> None:
        called.append((app, host, port))

    fake_uvicorn = types.SimpleNamespace(run=fake_run)
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

    exit_code = main(["run-api", "--host", "0.0.0.0", "--port", "9000"])

    assert exit_code == 0
    assert called == [("vk_openclaw_service.main:app", "0.0.0.0", 9000)]