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

    env_text = installer.render_env_local(config, target_os="linux")

    assert "ADMIN_API_TOKEN=admin-token" in env_text
    assert "VK_ACCESS_TOKEN=vk-token" in env_text
    assert "PERSISTENCE_MODE=file" in env_text
    assert "INSTALL_TARGET_OS=linux" in env_text


def test_redact_env_preview_masks_sensitive_values() -> None:
    env_text = "\n".join(
        [
            "ADMIN_API_TOKEN=admin-secret",
            "VK_ACCESS_TOKEN=vk-secret",
            "DATABASE_DSN=postgresql://user:pass@localhost:5432/app",
            "VK_ALLOWED_PEERS=42",
        ]
    )
    preview = installer.redact_env_preview(env_text)
    assert "admin-secret" not in preview
    assert "vk-secret" not in preview
    assert "postgresql://user:pass" not in preview
    assert "VK_ALLOWED_PEERS=42" in preview


def test_format_secret_status() -> None:
    assert installer.format_secret_status("") == "EMPTY"
    assert installer.format_secret_status("   ") == "EMPTY"
    assert installer.format_secret_status("abcd") == "SET (4 chars)"


def test_secret_fingerprint_is_stable_and_redacted() -> None:
    fp1 = installer.secret_fingerprint("token-value")
    fp2 = installer.secret_fingerprint("token-value")
    assert fp1 == fp2
    assert len(fp1) == 12
    assert fp1 != "token-value"
    assert installer.secret_fingerprint("") == "n/a"


def test_render_secret_confirmation_hides_values() -> None:
    config = installer.InstallConfig(
        admin_api_token="admin-secret",
        vk_access_token="vk-secret",
        vk_allowed_peers="42",
        persistence_mode="file",
        database_dsn="",
        redis_dsn="",
        openclaw_command="openclaw",
    )
    rendered = installer.render_secret_confirmation(config, platform_name="linux")
    assert "admin-secret" not in rendered
    assert "vk-secret" not in rendered
    assert "SET (12 chars)" in rendered
    assert "SET (9 chars)" in rendered
    assert "fingerprint:" in rendered
    assert "Подтверждение секретов" in rendered


def test_render_systemd_units_contains_execstart_and_envfile(tmp_path: Path) -> None:
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


def test_render_winsw_xml_contains_expected_commands(tmp_path: Path) -> None:
    env_path = tmp_path / ".env.local"
    env_path.write_text("ADMIN_API_TOKEN=secret\nVK_ALLOWED_PEERS=42\n", encoding="utf-8")
    xml = installer.render_winsw_xml(
        working_directory=tmp_path,
        env_path=env_path,
        cli_executable="C:\\vk-openclaw.exe",
        environment=installer.load_env_file(env_path),
    )
    assert "<id>vk-openclaw-service</id>" in xml
    assert "run-api --host 127.0.0.1 --port 8000" in xml
    assert "run-worker --interval-seconds 5" in xml
    assert str(env_path) in xml
    assert "name=\"ADMIN_API_TOKEN\"" in xml


def test_load_env_file_parses_key_values(tmp_path: Path) -> None:
    env_path = tmp_path / ".env.local"
    env_path.write_text(
        "# comment\nADMIN_API_TOKEN=abc\nVK_ALLOWED_PEERS=42\nEMPTY=\ninvalid_line\n",
        encoding="utf-8",
    )
    parsed = installer.load_env_file(env_path)
    assert parsed["ADMIN_API_TOKEN"] == "abc"
    assert parsed["VK_ALLOWED_PEERS"] == "42"
    assert parsed["EMPTY"] == ""


def test_prompt_install_config_non_interactive_uses_json_config(tmp_path: Path) -> None:
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


def test_prompt_install_config_auto_generated_admin_one_time_reveal(monkeypatch, capsys) -> None:
    inputs = iter(
        [
            "hidden",  # ADMIN mode
            "",  # confirm one-time reveal
            "hidden",  # VK mode
            "42",  # VK_ALLOWED_PEERS
        ]
    )
    secrets_input = iter(["", "vk-hidden-token"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr(installer, "getpass", lambda _: next(secrets_input))
    monkeypatch.setattr(installer.secrets, "token_hex", lambda n: "a" * 64)

    config = installer.prompt_install_config(non_interactive=False, config_path=None, platform_name="linux")
    output = capsys.readouterr().out

    assert config.admin_api_token == "a" * 64
    assert config.persistence_mode == "file"
    assert config.database_dsn == ""
    assert config.redis_dsn == ""
    assert config.openclaw_command == installer._default_openclaw_command()
    assert "ADMIN_API_TOKEN=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in output
    assert "shown once" in output


def test_prompt_install_config_paste_visible_for_vk_token(monkeypatch) -> None:
    inputs = iter(
        [
            "hidden",  # ADMIN mode
            "paste-visible",  # VK mode
            "vk-visible-token",  # VK token
            "42",  # peers
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr(installer, "getpass", lambda _: "admin-token")

    config = installer.prompt_install_config(non_interactive=False, config_path=None, platform_name="linux")
    assert config.vk_access_token == "vk-visible-token"
    assert config.persistence_mode == "file"
    assert config.openclaw_command == installer._default_openclaw_command()


def test_run_setup_blocks_when_openclaw_missing(monkeypatch, capsys) -> None:
    monkeypatch.setattr(installer, "detect_platform", lambda: "linux")
    monkeypatch.setattr(installer, "check_systemd_user_available", lambda: (True, ""))
    monkeypatch.setattr(installer, "check_openclaw_installed", lambda: (False, "missing"))

    exit_code = installer.run_setup(non_interactive=True, config_path=None, dry_run=False)

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "openclaw" in output.lower()


def test_run_setup_dry_run_skips_writes_and_service_install(monkeypatch, tmp_path: Path, capsys) -> None:
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
    monkeypatch.setattr(installer, "detect_platform", lambda: "linux")
    monkeypatch.setattr(installer, "check_systemd_user_available", lambda: (True, ""))
    monkeypatch.setattr(installer, "check_openclaw_installed", lambda: (True, ""))
    monkeypatch.setattr(installer, "resolve_cli_executable", lambda: "/tmp/vk-openclaw")

    called = {"write": False, "install": False}

    def fake_write(path: Path, content: str) -> None:
        called["write"] = True

    def fake_install(*args, **kwargs) -> int:
        called["install"] = True
        return 0

    monkeypatch.setattr(installer, "write_env_local", fake_write)
    monkeypatch.setattr(installer, "install_service_files", fake_install)

    exit_code = installer.run_setup(non_interactive=True, config_path=config_path, dry_run=True)
    output = capsys.readouterr().out
    assert exit_code == 0
    assert called["write"] is False
    assert called["install"] is False
    assert "SET (11 chars)" in output
    assert "SET (8 chars)" in output
    assert "admin-token" not in output
    assert "vk-token" not in output
    assert "Режим dry-run" in output
    assert "Dry-run mode" in output
    assert "Author: Гарипов Нияз Варисович февраль 2026" in output
    assert "- Email: garipovn@yandex.ru" in output
    assert "- License: MIT (`LICENSE`)" in output
    assert "fingerprint:" in output


def test_run_setup_linux_non_interactive_writes_env_and_units(tmp_path: Path, monkeypatch, capsys) -> None:
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
    monkeypatch.setattr(installer, "detect_platform", lambda: "linux")
    monkeypatch.setattr(installer, "check_systemd_user_available", lambda: (True, ""))
    monkeypatch.setattr(installer, "check_openclaw_installed", lambda: (True, ""))
    monkeypatch.setattr(installer, "resolve_cli_executable", lambda: "/tmp/vk-openclaw")

    class FakeProcess:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(installer.subprocess, "run", lambda *args, **kwargs: FakeProcess())

    exit_code = installer.run_setup(non_interactive=True, config_path=config_path, dry_run=False)
    output = capsys.readouterr().out

    env_path = workdir / ".env.local"
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    assert exit_code == 0
    assert env_path.exists()
    assert (unit_dir / installer.SYSTEMD_UNIT_API).exists()
    assert (unit_dir / installer.SYSTEMD_UNIT_WORKER).exists()
    assert "Подтверждение секретов" in output
    assert "Secret confirmation" in output
    assert "SET (11 chars)" in output
    assert "SET (8 chars)" in output
    assert "admin-token" not in output
    assert "vk-token" not in output
    assert "fingerprint:" in output
    assert "Where to find tokens later" in output


def test_run_setup_windows_requires_winsw(monkeypatch, capsys) -> None:
    monkeypatch.setattr(installer, "detect_platform", lambda: "windows")
    monkeypatch.setattr(installer, "check_openclaw_installed", lambda: (True, ""))
    monkeypatch.setattr(installer, "resolve_winsw_executable", lambda: None)

    exit_code = installer.run_setup(non_interactive=True, config_path=None, dry_run=False)
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "winsw" in output.lower()


def test_manage_service_linux_uses_systemd(monkeypatch) -> None:
    monkeypatch.setattr(installer, "detect_platform", lambda: "linux")

    captured: list[list[str]] = []

    class FakeProcess:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, **kwargs):
        captured.append(args)
        return FakeProcess()

    monkeypatch.setattr(installer.subprocess, "run", fake_run)
    assert installer.manage_service("start") == 0
    assert captured[0][:2] == ["systemctl", "--user"]


def test_manage_service_windows_uses_winsw(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(installer, "detect_platform", lambda: "windows")
    exe = tmp_path / "winsw.exe"
    exe.write_text("stub", encoding="utf-8")
    monkeypatch.setattr(installer, "resolve_winsw_executable", lambda: exe)
    monkeypatch.setattr(installer, "resolve_winsw_base_path", lambda: tmp_path / "vk-openclaw-service")

    captured: list[list[str]] = []

    class FakeProcess:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, **kwargs):
        captured.append(args)
        return FakeProcess()

    monkeypatch.setattr(installer.subprocess, "run", fake_run)
    assert installer.manage_service("status") == 0
    assert str(exe) in captured[0][0]


def test_peer_list_from_payload_parses_ints_and_numeric_strings() -> None:
    payload = {"items": [42, "77", "bad", None]}
    assert installer._peer_list_from_payload(payload) == {42, 77}


def test_run_pairing_helper_uses_paired_peers_endpoint(monkeypatch, capsys) -> None:
    calls: list[str] = []
    config = installer.InstallConfig(
        admin_api_token="admin-token",
        vk_access_token="vk-token",
        vk_allowed_peers="42",
        persistence_mode="file",
        database_dsn="",
        redis_dsn="",
        openclaw_command="openclaw",
    )

    inputs = iter(["y", "", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr(installer.time, "sleep", lambda _: None)

    def fake_http_json(url: str, *, method: str, payload: dict[str, object], bearer_token: str) -> dict[str, object]:
        calls.append(url)
        if url.endswith("/api/v1/pairing/code"):
            return {"peer_id": 42, "code": "ABCD1234"}
        if url.endswith("/api/v1/pairing/peers"):
            return {"items": [42], "count": 1}
        if url.endswith("/api/v1/status"):
            return {"mode": "plain"}
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(installer, "_http_json", fake_http_json)

    installer.run_pairing_helper(config, platform_name="linux")
    output = capsys.readouterr().out

    assert any(url.endswith("/api/v1/pairing/peers") for url in calls)
    assert not any(url.endswith("/api/v1/pairing/verify") for url in calls)
    assert "Pairing confirmed via VK." in output
