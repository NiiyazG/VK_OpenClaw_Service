from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
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
from urllib import error, request
from urllib.parse import urlparse

SYSTEMD_UNIT_API = "vk-openclaw-api.service"
SYSTEMD_UNIT_WORKER = "vk-openclaw-worker.service"
WINDOWS_SERVICE_ID = "vk-openclaw-service"


@dataclass(frozen=True)
class InstallConfig:
    admin_api_token: str
    vk_access_token: str
    vk_allowed_peers: str
    persistence_mode: str
    database_dsn: str
    redis_dsn: str
    openclaw_command: str


def detect_platform() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if os.name == "posix":
        return "linux"
    return "unsupported"


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
    if not config.vk_allowed_peers.strip():
        errors.append("VK_ALLOWED_PEERS must not be empty.")
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

    print("\nVK OpenClaw setup wizard\n")
    print("What you need before start:")
    print("1) VK_ACCESS_TOKEN (VK ID / VK developer settings, message permissions)")
    print("2) VK_ALLOWED_PEERS (chat/dialog peer_id)")
    print("3) OPENCLAW_COMMAND (usually openclaw or ./openclaw_agent_wrapper.sh)")
    print("Docs: docs/vk_setup.md")
    print("Security: secrets are written only to local .env.local and should never be committed.\n")

    print("ADMIN_API_TOKEN secures admin API endpoints.")
    admin_input = getpass("ADMIN_API_TOKEN (Enter = auto-generate): ").strip()
    admin_token = admin_input or secrets.token_hex(32)
    if not admin_input:
        print("ADMIN_API_TOKEN was auto-generated.")

    print("\nVK_ACCESS_TOKEN: create in VK app/community bot settings.")
    vk_access_token = _prompt_non_empty("VK_ACCESS_TOKEN: ", secret_value=True)

    print("\nVK_ALLOWED_PEERS: peer_id for allowed dialog/chat, e.g. 2000000001 or 123456.")
    vk_allowed_peers = _prompt_with_default("VK_ALLOWED_PEERS", source.get("VK_ALLOWED_PEERS", "42"))

    mode_default = _normalize_mode(source.get("PERSISTENCE_MODE", "file"))
    print("\nPERSISTENCE_MODE options: file, memory, database.")
    mode = _prompt_with_default("PERSISTENCE_MODE", mode_default)
    mode = _normalize_mode(mode)

    database_dsn = ""
    redis_dsn = ""
    if mode == "database":
        print("DATABASE_DSN example: postgresql://user:pass@localhost:5432/dbname")
        database_dsn = _prompt_non_empty("DATABASE_DSN: ")
        print("REDIS_DSN example: redis://localhost:6379/0")
        redis_dsn = _prompt_non_empty("REDIS_DSN: ")

    print("\nOPENCLAW_COMMAND points to OpenClaw executable or wrapper script.")
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


def render_env_local(config: InstallConfig, *, target_os: str) -> str:
    completed_at = datetime.now(UTC).replace(microsecond=0).isoformat()
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
        f"INSTALL_TARGET_OS={target_os}",
        "SERVICE_MODE=system-service",
        f"SETUP_COMPLETED_AT={completed_at}",
    ]
    return "\n".join(lines) + "\n"


def redact_env_preview(content: str) -> str:
    secret_markers = ("TOKEN", "PASSWORD", "SECRET", "DSN", "KEY")
    redacted: list[str] = []
    for raw_line in content.splitlines():
        if "=" not in raw_line:
            redacted.append(raw_line)
            continue
        key, value = raw_line.split("=", 1)
        if any(marker in key for marker in secret_markers):
            redacted.append(f"{key}=***REDACTED***")
            continue
        redacted.append(f"{key}={value}")
    return "\n".join(redacted)


def write_env_local(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    if os.name == "posix":
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


def resolve_winsw_executable() -> Path | None:
    env_path = os.environ.get("WINSW_PATH", "").strip()
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate
    for candidate in (
        Path.cwd() / "tools" / "winsw" / "winsw.exe",
        Path.cwd() / "scripts" / "winsw.exe",
        Path.cwd() / "winsw.exe",
    ):
        if candidate.exists():
            return candidate
    return None


def resolve_winsw_base_path() -> Path:
    return Path.home() / ".vk-openclaw" / "winsw" / WINDOWS_SERVICE_ID


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip()
    return values


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def render_winsw_xml(
    *,
    working_directory: Path,
    env_path: Path,
    cli_executable: str,
    environment: dict[str, str] | None = None,
) -> str:
    cwd = _xml_escape(str(working_directory))
    env_file = _xml_escape(str(env_path))
    cli = _xml_escape(cli_executable)
    command = (
        f"Start-Process -FilePath '{cli}' -ArgumentList 'run-api --host 127.0.0.1 --port 8000' "
        f"-WorkingDirectory '{cwd}' -PassThru; "
        f"Start-Process -FilePath '{cli}' -ArgumentList 'run-worker --interval-seconds 5' "
        f"-WorkingDirectory '{cwd}' -Wait"
    )
    env_lines = [f"  <env name=\"VK_OPENCLAW_ENV_FILE\" value=\"{env_file}\" />"]
    for key, value in sorted((environment or {}).items()):
        env_lines.append(f"  <env name=\"{_xml_escape(key)}\" value=\"{_xml_escape(value)}\" />")
    return "\n".join(
        [
            "<service>",
            f"  <id>{WINDOWS_SERVICE_ID}</id>",
            "  <name>VK OpenClaw Service</name>",
            "  <description>VK OpenClaw API and worker runtime</description>",
            "  <executable>powershell.exe</executable>",
            f"  <arguments>-NoProfile -ExecutionPolicy Bypass -Command \"{command}\"</arguments>",
            *env_lines,
            f"  <workingdirectory>{cwd}</workingdirectory>",
            "  <log mode=\"roll-by-size\">",
            "    <sizeThreshold>10240</sizeThreshold>",
            "    <keepFiles>5</keepFiles>",
            "  </log>",
            "</service>",
            "",
        ]
    )


def install_service_files(*, platform_name: str, working_directory: Path, env_path: Path, cli_executable: str) -> int:
    if platform_name == "linux":
        unit_dir = Path.home() / ".config" / "systemd" / "user"
        rendered_units = render_systemd_units(
            working_directory=working_directory,
            env_path=env_path,
            cli_executable=cli_executable,
        )
        write_systemd_units(unit_dir, rendered_units)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)  # nosec
        subprocess.run(["systemctl", "--user", "enable", SYSTEMD_UNIT_API, SYSTEMD_UNIT_WORKER], check=False)  # nosec
        return 0

    if platform_name == "windows":
        winsw_source = resolve_winsw_executable()
        if winsw_source is None:
            print("Error: WinSW executable not found. Set WINSW_PATH or place winsw.exe under tools/winsw/.")
            return 1
        base = resolve_winsw_base_path()
        base.parent.mkdir(parents=True, exist_ok=True)
        xml_path = base.with_suffix(".xml")
        exe_path = base.with_suffix(".exe")
        xml_path.write_text(
            render_winsw_xml(
                working_directory=working_directory,
                env_path=env_path,
                cli_executable=cli_executable,
                environment=load_env_file(env_path),
            ),
            encoding="utf-8",
        )
        shutil.copy2(winsw_source, exe_path)
        subprocess.run([str(exe_path), "uninstall"], check=False)  # nosec
        result = subprocess.run([str(exe_path), "install"], check=False)  # nosec
        return int(result.returncode)

    print(f"Error: unsupported platform '{platform_name}'.")
    return 1


def manage_service(command: str) -> int:
    platform_name = detect_platform()
    if platform_name == "linux":
        if command == "status":
            result = subprocess.run(  # nosec
                ["systemctl", "--user", "--no-pager", "--full", "status", SYSTEMD_UNIT_API, SYSTEMD_UNIT_WORKER],
                check=False,
            )
            return int(result.returncode)
        result = subprocess.run(  # nosec
            ["systemctl", "--user", command, SYSTEMD_UNIT_API, SYSTEMD_UNIT_WORKER],
            check=False,
        )
        return int(result.returncode)

    if platform_name == "windows":
        base = resolve_winsw_base_path()
        exe_path = base.with_suffix(".exe")
        if not exe_path.exists():
            winsw = resolve_winsw_executable()
            if winsw is None:
                print("Error: WinSW service executable not found.")
                return 1
            exe_path = winsw
        result = subprocess.run([str(exe_path), command], check=False)  # nosec
        return int(result.returncode)

    print("Error: service management is unsupported on this platform.")
    return 1


def systemd_user(command: str) -> int:
    return manage_service(command)


def systemd_user_status() -> int:
    return manage_service("status")


def _detect_primary_peer(vk_allowed_peers: str) -> int | None:
    for item in vk_allowed_peers.split(","):
        raw = item.strip()
        if not raw:
            continue
        try:
            return int(raw)
        except ValueError:
            continue
    return None


def _http_json(url: str, *, method: str, payload: dict[str, object], bearer_token: str) -> dict[str, object]:
    method_upper = method.upper()
    data = None
    if method_upper != "GET":
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=data, method=method_upper)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {bearer_token}")
    with request.urlopen(req, timeout=8) as response:  # nosec B310
        body = response.read().decode("utf-8")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object response.")
    return parsed


def run_pairing_helper(config: InstallConfig) -> None:
    peer_id = _detect_primary_peer(config.vk_allowed_peers)
    if peer_id is None:
        print("Pairing helper skipped: could not parse VK_ALLOWED_PEERS.")
        return
    print("\nPairing helper")
    print("It will request a pair code from local API and provide VK command instructions.")
    proceed = input("Run pairing helper now? [Y/n]: ").strip().lower()
    if proceed.startswith("n"):
        print("Pairing helper skipped. You can run it later through API endpoints.")
        return

    base_url = input("API base URL [http://127.0.0.1:8000]: ").strip() or "http://127.0.0.1:8000"
    code_url = f"{base_url.rstrip('/')}/api/v1/pairing/code"
    verify_url = f"{base_url.rstrip('/')}/api/v1/pairing/verify"
    status_url = f"{base_url.rstrip('/')}/api/v1/status"
    try:
        code_payload = _http_json(
            code_url,
            method="POST",
            payload={"peer_id": peer_id},
            bearer_token=config.admin_api_token,
        )
        code = str(code_payload.get("code", "")).strip()
        if not code:
            print("Could not read code from /pairing/code response.")
            return
        print(f"Send this command in VK chat: /pair {code}")
        input("Press Enter after sending /pair ...")
        verify_payload = _http_json(
            verify_url,
            method="POST",
            payload={"peer_id": peer_id, "code": code},
            bearer_token=config.admin_api_token,
        )
        print(f"Pair verify response: {verify_payload}")
        status_payload = _http_json(
            status_url,
            method="GET",
            payload={},
            bearer_token=config.admin_api_token,
        )
        print(f"Status snapshot: {status_payload}")
        print("Pairing helper completed. Validate in VK: /status then /ask привет")
    except (error.HTTPError, error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        print(f"Pairing helper failed: {exc}")
        print("You can continue manually with /api/v1/pairing/code and /api/v1/pairing/verify.")


def run_setup(*, non_interactive: bool, config_path: Path | None, dry_run: bool) -> int:
    platform_name = detect_platform()
    if platform_name == "unsupported":
        print("Error: setup is supported only on Linux and Windows.")
        return 1

    if platform_name == "linux":
        systemd_ok, systemd_reason = check_systemd_user_available()
        if not systemd_ok:
            print("Error: systemd --user is unavailable.")
            print(systemd_reason)
            return 1
    if platform_name == "windows" and resolve_winsw_executable() is None and not dry_run:
        print("Error: WinSW is required on Windows. Set WINSW_PATH or provide tools/winsw/winsw.exe.")
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

    env_content = render_env_local(config, target_os=platform_name)
    workdir = Path.cwd()
    env_path = workdir / ".env.local"
    if dry_run:
        print("Dry-run mode: no files or services were changed.")
        print("Preview (.env.local redacted):")
        print(redact_env_preview(env_content))
        return 0

    write_env_local(env_path, env_content)

    install_code = install_service_files(
        platform_name=platform_name,
        working_directory=workdir,
        env_path=env_path,
        cli_executable=resolve_cli_executable(),
    )
    if install_code != 0:
        print("Service installation failed.")
        return install_code

    print("Setup completed.")
    print(f"- Config file: {env_path}")
    print("- Service mode: system-service")

    start_code = manage_service("start")
    if start_code != 0:
        print("Warning: service start returned non-zero status.")
    status_code = manage_service("status")
    if status_code != 0:
        print("Warning: service status returned non-zero status.")
    else:
        print("Service status check passed.")

    if not non_interactive:
        run_pairing_helper(config)
    return 0


def run_install(*, non_interactive: bool, config_path: Path | None) -> int:
    print("Notice: 'install' is deprecated. Use 'setup' for new flows.")
    return run_setup(non_interactive=non_interactive, config_path=config_path, dry_run=False)
