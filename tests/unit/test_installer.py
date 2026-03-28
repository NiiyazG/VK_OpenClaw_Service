from __future__ import annotations

import json
from pathlib import Path

from vk_openclaw_service import installer


def test_validate_install_config_requires_database_dsns() -> None:
    config = installer.InstallConfig(
        admin_api_token="admin",
        vk_access_token="vk",
        vk_allowed_peers="42",
        persistence_mode="database",
        database_dsn="",
        redis_dsn="",
        openclaw_command="openclaw",
    )

    errors = installer.validate_install_config(config)

    assert any("DATABASE_DSN" in item for item in errors)
    assert any("REDIS_DSN" in item for item in errors)


def test_render_env_local_contains_expected_keys() -> None:
    config = installer.InstallConfig(
        admin_api_token="admin-token",
        vk_access_token="vk-token",
        vk_allowed_peers="42",
        persistence_mode="file",
        database_dsn="",
        redis_dsn="",
        openclaw_command="openclaw",
    )

    env_text = installer.render_env_local(config)

    assert "ADMIN_API_TOKEN=admin-token" in env_text
    assert "VK_ACCESS_TOKEN=vk-token" in env_text
    assert "PERSISTENCE_MODE=file" in env_text


def test_render_systemd_units_contains_execstart_and_envfile(tmp_path) -> None:
    env_path = tmp_path / ".env.local"
    units = installer.render_systemd_units(
        working_directory=tmp_path,
        env_path=env_path,
        cli_executable="/tmp/vk-openclaw",
    )

    api = units[installer.SYSTEMD_UNIT_API]
    worker = units[installer.SYSTEMD_UNIT_WORKER]

    assert "ExecStart=/tmp/vk-openclaw run-api --host 127.0.0.1 --port 8000" in api
    assert "ExecStart=/tmp/vk-openclaw run-worker --interval-seconds 5" in worker
    assert "EnvironmentFile=" in api


def test_prompt_install_config_non_interactive_uses_json_config(tmp_path) -> None:
    config_path = tmp_path / "install.json"
    config_path.write_text(
        json.dumps(
            {
                "VK_ACCESS_TOKEN": "vk-token",
                "VK_ALLOWED_PEERS": "42,43",
                "PERSISTENCE_MODE": "database",
                "DATABASE_DSN": "postgresql://user:pass@localhost:5432/app",
                "REDIS_DSN": "redis://localhost:6379/0",
                "OPENCLAW_COMMAND": "openclaw",
            }
        ),
        encoding="utf-8",
    )

    config = installer.prompt_install_config(non_interactive=True, config_path=config_path)

    assert config.vk_access_token == "vk-token"
    assert config.vk_allowed_peers == "42,43"
    assert config.persistence_mode == "database"
    assert config.admin_api_token


def test_run_install_blocks_when_openclaw_missing(monkeypatch, capsys) -> None:
    monkeypatch.setattr(installer, "detect_wsl", lambda: True)
    monkeypatch.setattr(installer, "check_systemd_user_available", lambda: (True, ""))
    monkeypatch.setattr(installer, "check_openclaw_installed", lambda: (False, "missing"))

    exit_code = installer.run_install(non_interactive=True, config_path=None)

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "openclaw" in output.lower()


def test_run_install_non_interactive_writes_env_and_units(tmp_path, monkeypatch) -> None:
    workdir = tmp_path / "repo"
    workdir.mkdir()
    config_path = workdir / "install.json"
    config_path.write_text(
        json.dumps(
            {
                "ADMIN_API_TOKEN": "admin-token",
                "VK_ACCESS_TOKEN": "vk-token",
                "VK_ALLOWED_PEERS": "42",
                "PERSISTENCE_MODE": "file",
                "OPENCLAW_COMMAND": "openclaw",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(workdir)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setattr(installer, "detect_wsl", lambda: True)
    monkeypatch.setattr(installer, "check_systemd_user_available", lambda: (True, ""))
    monkeypatch.setattr(installer, "check_openclaw_installed", lambda: (True, ""))
    monkeypatch.setattr(installer, "resolve_cli_executable", lambda: "/tmp/vk-openclaw")

    class FakeProcess:
        returncode = 0

    monkeypatch.setattr(installer.subprocess, "run", lambda *args, **kwargs: FakeProcess())

    exit_code = installer.run_install(non_interactive=True, config_path=config_path)

    env_path = workdir / ".env.local"
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    assert exit_code == 0
    assert env_path.exists()
    assert (unit_dir / installer.SYSTEMD_UNIT_API).exists()
    assert (unit_dir / installer.SYSTEMD_UNIT_WORKER).exists()

