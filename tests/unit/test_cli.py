from __future__ import annotations

import sys
import types
from unittest.mock import patch

from vk_openclaw_service.cli import main
from vk_openclaw_service.core.settings import RuntimeSettings


def test_cli_setup_dispatches_to_installer() -> None:
    with patch("vk_openclaw_service.cli.installer.run_setup", return_value=0) as setup_mock:
        exit_code = main(["setup", "--non-interactive", "--dry-run"])

    assert exit_code == 0
    setup_mock.assert_called_once()


def test_cli_install_alias_dispatches_to_setup() -> None:
    with patch("vk_openclaw_service.cli.installer.run_setup", return_value=0) as setup_mock:
        exit_code = main(["install", "--non-interactive"])

    assert exit_code == 0
    setup_mock.assert_called_once()


def test_cli_start_dispatches_to_service_backend() -> None:
    with patch("vk_openclaw_service.cli.installer.manage_service", return_value=0) as command_mock:
        exit_code = main(["start"])

    assert exit_code == 0
    command_mock.assert_called_once_with("start")


def test_cli_status_dispatches_to_service_backend() -> None:
    with patch("vk_openclaw_service.cli.installer.manage_service", return_value=0) as status_mock:
        exit_code = main(["status"])

    assert exit_code == 0
    status_mock.assert_called_once_with("status")


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


def test_cli_run_all_dispatches_to_launcher() -> None:
    settings = RuntimeSettings(vk_access_token="token")
    with patch("vk_openclaw_service.cli.get_settings", return_value=settings):
        with patch("vk_openclaw_service.cli.start_all", return_value=(True, "started")) as start_all_mock:
            with patch("vk_openclaw_service.cli.status_all", return_value={"log_file": "./state/vk-openclaw.log"}):
                exit_code = main(["run-all", "--wait-for-gateway"])
    assert exit_code == 0
    start_all_mock.assert_called_once_with(settings, wait_for_gateway_enabled=True)


def test_cli_stop_all_dispatches_to_launcher() -> None:
    settings = RuntimeSettings(vk_access_token="token")
    with patch("vk_openclaw_service.cli.get_settings", return_value=settings):
        with patch("vk_openclaw_service.cli.stop_all", return_value=(True, "stopped")) as stop_all_mock:
            exit_code = main(["stop-all"])
    assert exit_code == 0
    stop_all_mock.assert_called_once_with(settings)


def test_cli_doctor_dispatches_to_doctor() -> None:
    with patch("vk_openclaw_service.cli.run_doctor", return_value=0) as doctor_mock:
        exit_code = main(["doctor"])
    assert exit_code == 0
    doctor_mock.assert_called_once()
