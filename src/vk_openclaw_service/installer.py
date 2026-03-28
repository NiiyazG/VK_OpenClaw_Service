from __future__ import annotations

from dataclasses import dataclass
from getpass import getpass
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import socket
import subprocess  # nosec B404
import sys
from urllib.parse import urlparse

SYSTEMD_UNIT_API = "vk-openclaw-api.service"
SYSTEMD_UNIT_WORKER = "vk-openclaw-worker.service"


@dataclass(frozen=True)
class InstallConfig:
    admin_api_token: str
    vk_access_token: str
    vk_allowed_peers: str
    persistence_mode: str
    database_dsn: str
    redis_dsn: str
    openclaw_command: str


def detect_wsl() -> bool:
    if os.name != "posix":
        return False
    version_path = Path("/proc/version")
    if not version_path.exists():
        return False
    content = version_path.read_text(encoding="utf-8", errors="ignore").lower()
    return "microsoft" in content or "wsl" in content


def check_systemd_user_available() -> tuple[bool, str]:
    if shutil.which("systemctl") is None:
        return False, "systemctl command was not found in PATH."
    result = subprocess.run(  # nosec
        ["systemctl", "--user", "show-environment"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True, ""
    stderr = result.stderr.strip() or result.stdout.strip() or "systemctl --user is unavailable"
    return False, stderr


def check_openclaw_installed() -> tuple[bool, str]:
    if shutil.which("openclaw") is not None:
        return True, ""
    return False, "openclaw command was not found in PATH."


def validate_install_config(config: InstallConfig) -> list[str]:
    errors: list[str] = []
    if not config.admin_api_token.strip():
        errors.append("ADMIN_API_TOKEN must not be empty.")
    if not config.vk_access_token.strip():
        errors.append("VK_ACCESS_TOKEN must not be empty.")
    mode = config.persistence_mode.strip().lower()
    if mode not in {"file", "memory", "database"}:
        errors.append("PERSISTENCE_MODE must be one of: file, memory, database.")
    if mode == "database":
        if not config.database_dsn.strip():
            errors.append("DATABASE_DSN is required when PERSISTENCE_MODE=database.")
        if not config.redis_dsn.strip():
            errors.append("REDIS_DSN is required when PERSISTENCE_MODE=database.")
    return errors


def _check_endpoint_reachable(dsn: str, default_port: int) -> tuple[bool, str]:
    parsed = urlparse(dsn)
    if not parsed.hostname:
        return False, f"Invalid DSN: {dsn}"
    port = parsed.port or default_port
    try:
        with socket.create_connection((parsed.hostname, port), timeout=2):
            return True, ""
    except OSError as exc:
        return False, f"{parsed.hostname}:{port} is unreachable ({exc})."


def connectivity_warnings(config: InstallConfig) -> list[str]:
    warnings: list[str] = []
    if config.persistence_mode != "database":
        return warnings
    db_ok, db_msg = _check_endpoint_reachable(config.database_dsn, 5432)
    if not db_ok:
        warnings.append(f"DATABASE_DSN check: {db_msg}")
    redis_ok, redis_msg = _check_endpoint_reachable(config.redis_dsn, 6379)
    if not redis_ok:
        warnings.append(f"REDIS_DSN check: {redis_msg}")
    return warnings


def _prompt_non_empty(prompt: str, *, secret_value: bool = False) -> str:
    while True:
        value = (getpass(prompt) if secret_value else input(prompt)).strip()
        if value:
            return value
        print("Value cannot be empty.")


def _prompt_with_default(prompt: str, default: str) -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def _default_openclaw_command() -> str:
    wrapper = Path.cwd() / "openclaw_agent_wrapper.sh"
    if wrapper.exists():
        return "./openclaw_agent_wrapper.sh"
    return "openclaw"


def _normalize_mode(raw_mode: str) -> str:
    mode = raw_mode.strip().lower()
    if mode in {"file", "memory", "database"}:
        return mode
    return "file"


def load_config_file(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Config file must be a JSON object.")
    return {str(key): str(value) for key, value in payload.items()}


def prompt_install_config(*, non_interactive: bool, config_path: Path | None) -> InstallConfig:
    source: dict[str, str] = {}
    if config_path is not None:
        source = load_config_file(config_path)

    if non_interactive:
        admin_token = source.get("ADMIN_API_TOKEN", "").strip() or secrets.token_hex(32)
        return InstallConfig(
            admin_api_token=admin_token,
            vk_access_token=source.get("VK_ACCESS_TOKEN", "").strip(),
            vk_allowed_peers=source.get("VK_ALLOWED_PEERS", "42").strip() or "42",
            persistence_mode=_normalize_mode(source.get("PERSISTENCE_MODE", "file")),
            database_dsn=source.get("DATABASE_DSN", "").strip(),
            redis_dsn=source.get("REDIS_DSN", "").strip(),
            openclaw_command=source.get("OPENCLAW_COMMAND", _default_openclaw_command()).strip()
            or _default_openclaw_command(),
        )

    print("\nVK OpenClaw interactive setup (WSL)\n")
    print("Hint: ADMIN_API_TOKEN can be generated with: openssl rand -hex 32")
    print("Hint: VK_ACCESS_TOKEN is created in VK Dev / VK ID for your app or community bot.")
    print("Hint: VK_ALLOWED_PEERS is peer_id (chat/dialog id). You can get it from VK API")
    print("      messages.getConversations/messages.getHistory or from worker logs.")
    print("Hint: secrets are saved to local .env.local only. Do not commit it to git.")
    print("VK docs: https://dev.vk.com/ru/api/access-token/getting-started")
    print("If you choose database mode, DATABASE_DSN and REDIS_DSN are required.")

    admin_input = getpass("ADMIN_API_TOKEN (Enter = auto-generate): ").strip()
    admin_token = admin_input or secrets.token_hex(32)
    if not admin_input:
        print("ADMIN_API_TOKEN was auto-generated.")
    vk_access_token = _prompt_non_empty("VK_ACCESS_TOKEN: ", secret_value=True)
    vk_allowed_peers = _prompt_with_default("VK_ALLOWED_PEERS", source.get("VK_ALLOWED_PEERS", "42"))

    mode_default = _normalize_mode(source.get("PERSISTENCE_MODE", "file"))
    mode = _prompt_with_default("PERSISTENCE_MODE (file/memory/database)", mode_default)
    mode = _normalize_mode(mode)

    database_dsn = ""
    redis_dsn = ""
    if mode == "database":
        print("DATABASE_DSN example: postgresql://user:pass@localhost:5432/dbname")
        print("REDIS_DSN example: redis://localhost:6379/0")
        database_dsn = _prompt_non_empty("DATABASE_DSN: ")
        redis_dsn = _prompt_non_empty("REDIS_DSN: ")

    print("Hint: OPENCLAW_COMMAND is usually ./openclaw_agent_wrapper.sh (or openclaw).")
    openclaw_command = _prompt_with_default("OPENCLAW_COMMAND", _default_openclaw_command())

    return InstallConfig(
        admin_api_token=admin_token,
        vk_access_token=vk_access_token,
        vk_allowed_peers=vk_allowed_peers,
        persistence_mode=mode,
        database_dsn=database_dsn,
        redis_dsn=redis_dsn,
        openclaw_command=openclaw_command,
    )


def render_env_local(config: InstallConfig) -> str:
    lines = [
        f"ADMIN_API_TOKEN={config.admin_api_token}",
        f"VK_ACCESS_TOKEN={config.vk_access_token}",
        f"VK_ALLOWED_PEERS={config.vk_allowed_peers}",
        f"PERSISTENCE_MODE={config.persistence_mode}",
        f"DATABASE_DSN={config.database_dsn}",
        f"REDIS_DSN={config.redis_dsn}",
        "VK_MODE=plain",
        "FREE_TEXT_ASK_ENABLED=false",
        "PAIR_CODE_TTL_SEC=600",
        "VK_RATE_LIMIT_PER_MIN=6",
        "VK_MAX_ATTACHMENTS=2",
        "VK_MAX_FILE_MB=10",
        f"OPENCLAW_COMMAND={config.openclaw_command}",
        "OPENCLAW_TIMEOUT_SEC=120",
        "STATE_DIR=./state",
        "WORKER_INTERVAL_SEC=5",
        "WORKER_RETRY_BACKOFF_SEC=1",
        "WORKER_MAX_BACKOFF_SEC=30",
        "WORKER_ID=worker-default",
        "WORKER_LEASE_TTL_SEC=15",
        "WORKER_LEASE_KEY=vk-openclaw:worker-lease",
        "RETRY_QUEUE_MAX_ATTEMPTS=3",
        "RETRY_QUEUE_BASE_BACKOFF_SEC=5",
        "RETRY_QUEUE_MAX_BACKOFF_SEC=60",
        "REPLAY_TTL_SEC=300",
        "RETRY_QUEUE_KEY=vk-openclaw:retry",
    ]
    return "\n".join(lines) + "\n"


def write_env_local(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    os.chmod(path, 0o600)


def resolve_cli_executable() -> str:
    argv0 = Path(sys.argv[0])
    if argv0.exists():
        return str(argv0.resolve())
    from_path = shutil.which("vk-openclaw")
    if from_path is not None:
        return from_path
    return "vk-openclaw"


def _quote(value: str) -> str:
    return shlex.quote(value)


def render_systemd_units(*, working_directory: Path, env_path: Path, cli_executable: str) -> dict[str, str]:
    wd = _quote(str(working_directory))
    env_file = _quote(str(env_path))
    exe = _quote(cli_executable)

    common = [
        "[Unit]",
        "Description=vk-openclaw service",
        "After=network-online.target",
        "Wants=network-online.target",
        "",
        "[Service]",
        "Type=simple",
        f"WorkingDirectory={wd}",
        f"EnvironmentFile={env_file}",
        "Restart=always",
        "RestartSec=2",
    ]

    api_lines = common + [
        f"ExecStart={exe} run-api --host 127.0.0.1 --port 8000",
        "",
        "[Install]",
        "WantedBy=default.target",
    ]
    worker_lines = common + [
        f"ExecStart={exe} run-worker --interval-seconds 5",
        "",
        "[Install]",
        "WantedBy=default.target",
    ]

    return {
        SYSTEMD_UNIT_API: "\n".join(api_lines) + "\n",
        SYSTEMD_UNIT_WORKER: "\n".join(worker_lines) + "\n",
    }


def write_systemd_units(unit_dir: Path, rendered_units: dict[str, str]) -> None:
    unit_dir.mkdir(parents=True, exist_ok=True)
    for file_name, content in rendered_units.items():
        (unit_dir / file_name).write_text(content, encoding="utf-8")


def systemd_user(command: str) -> int:
    result = subprocess.run(  # nosec
        ["systemctl", "--user", command, SYSTEMD_UNIT_API, SYSTEMD_UNIT_WORKER],
        check=False,
    )
    return result.returncode


def systemd_user_status() -> int:
    result = subprocess.run(  # nosec
        ["systemctl", "--user", "--no-pager", "--full", "status", SYSTEMD_UNIT_API, SYSTEMD_UNIT_WORKER],
        check=False,
    )
    return result.returncode


def run_install(*, non_interactive: bool, config_path: Path | None) -> int:
    if not detect_wsl():
        print("Error: installer is supported only on WSL Linux.")
        return 1

    systemd_ok, systemd_reason = check_systemd_user_available()
    if not systemd_ok:
        print("Error: systemd --user is unavailable.")
        print(systemd_reason)
        print("Enable systemd in WSL (/etc/wsl.conf -> [boot] systemd=true), then run: wsl --shutdown")
        return 1

    openclaw_ok, openclaw_reason = check_openclaw_installed()
    if not openclaw_ok:
        print("Error: openclaw is not installed.")
        print(openclaw_reason)
        print("Install openclaw and verify with: openclaw --version")
        return 1

    config = prompt_install_config(non_interactive=non_interactive, config_path=config_path)
    errors = validate_install_config(config)
    if errors:
        print("Config validation failed:")
        for issue in errors:
            print(f"- {issue}")
        return 1

    warnings = connectivity_warnings(config)
    if warnings:
        print("Connectivity warnings:")
        for line in warnings:
            print(f"- {line}")

    workdir = Path.cwd()
    env_path = workdir / ".env.local"
    write_env_local(env_path, render_env_local(config))

    unit_dir = Path.home() / ".config" / "systemd" / "user"
    rendered_units = render_systemd_units(
        working_directory=workdir,
        env_path=env_path,
        cli_executable=resolve_cli_executable(),
    )
    write_systemd_units(unit_dir, rendered_units)

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)  # nosec
    subprocess.run(["systemctl", "--user", "enable", SYSTEMD_UNIT_API, SYSTEMD_UNIT_WORKER], check=False)  # nosec

    print("Install completed.")
    print(f"- Config file: {env_path} (chmod 600)")
    print(f"- Units: {unit_dir / SYSTEMD_UNIT_API}, {unit_dir / SYSTEMD_UNIT_WORKER}")
    print("Next step: run 'vk-openclaw start' and verify with 'vk-openclaw status'.")
    return 0
