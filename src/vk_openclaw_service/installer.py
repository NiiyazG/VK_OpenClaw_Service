from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import socket
import subprocess  # nosec B404
import sys
import time
from urllib import error, request
from urllib.parse import urlencode
from urllib.parse import urlparse

SYSTEMD_UNIT_API = "vk-openclaw-api.service"
SYSTEMD_UNIT_WORKER = "vk-openclaw-worker.service"
WINDOWS_SERVICE_ID = "vk-openclaw-service"
DEFAULT_LOCAL_API_BASE_URL = "http://127.0.0.1:8000"
API_BASE_URL_ENV = "VK_OPENCLAW_API_BASE_URL"
VK_API_BASE_URL = "https://api.vk.com/method"
VK_API_VERSION = "5.199"
AUTHOR_INFO_LINES = [
    "Author: Гарипов Нияз Варисович февраль 2026",
    "- Email: garipovn@yandex.ru",
    "- License: MIT (`LICENSE`)",
]


@dataclass(frozen=True)
class InstallConfig:
    admin_api_token: str
    vk_access_token: str
    vk_allowed_peers: str
    persistence_mode: str
    database_dsn: str
    redis_dsn: str
    openclaw_command: str


def _bi(platform_name: str, ru: str, en: str) -> str:
    if platform_name == "linux":
        return f"{ru} / {en}"
    return en


def _print_bi(platform_name: str, ru: str, en: str) -> None:
    print(_bi(platform_name, ru, en))


def print_author_info() -> None:
    for line in AUTHOR_INFO_LINES:
        print(line)


def format_secret_status(value: str) -> str:
    secret = value.strip()
    if not secret:
        return "EMPTY"
    return f"SET ({len(secret)} chars)"


def secret_fingerprint(value: str) -> str:
    secret = value.strip()
    if not secret:
        return "n/a"
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    return digest[:12]


def render_secret_confirmation(config: InstallConfig, *, platform_name: str) -> str:
    lines = [
        _bi(platform_name, "Подтверждение секретов:", "Secret confirmation:"),
        (
            f"- ADMIN_API_TOKEN: {format_secret_status(config.admin_api_token)}, "
            f"fingerprint: {secret_fingerprint(config.admin_api_token)}"
        ),
        (
            f"- VK_ACCESS_TOKEN: {format_secret_status(config.vk_access_token)}, "
            f"fingerprint: {secret_fingerprint(config.vk_access_token)}"
        ),
        _bi(
            platform_name,
            "Значения скрыты в целях безопасности.",
            "Values are hidden for security reasons.",
        ),
    ]
    return "\n".join(lines)


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


def _visual_break() -> None:
    print("\n" * 3 + "=" * 48)


def _prompt_secret_mode(*, platform_name: str, field_name: str, default_mode: str = "hidden") -> str:
    if platform_name != "linux":
        return "hidden"
    prompt = _bi(
        platform_name,
        f"{field_name}: режим ввода secret hidden/paste-visible [{default_mode}]: ",
        f"{field_name}: secret input mode hidden/paste-visible [{default_mode}]: ",
    )
    raw_mode = input(prompt).strip().lower()
    mode = raw_mode or default_mode
    if mode not in {"hidden", "paste-visible"}:
        _print_bi(
            platform_name,
            "Неизвестный режим, используем hidden.",
            "Unknown mode, falling back to hidden.",
        )
        return "hidden"
    return mode


def _prompt_secret_with_mode(*, prompt_label: str, platform_name: str, mode: str) -> str:
    while True:
        if mode == "paste-visible":
            value = input(prompt_label).strip()
        else:
            value = getpass(prompt_label).strip()
        if value:
            return value
        _print_bi(platform_name, "Значение не может быть пустым.", "Value cannot be empty.")


def _prompt_visible_required(*, prompt_label: str, platform_name: str) -> str:
    while True:
        value = input(prompt_label).strip()
        if value:
            return value
        _print_bi(platform_name, "Значение не может быть пустым.", "Value cannot be empty.")


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


def verify_vk_access_token(token: str) -> tuple[bool, str]:
    token_value = token.strip()
    if not token_value:
        return False, "VK API error: token is empty."
    body = urlencode(
        {
            "access_token": token_value,
            "v": VK_API_VERSION,
        }
    ).encode("utf-8")
    req = request.Request(
        url=f"{VK_API_BASE_URL}/users.get",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with request.urlopen(req, timeout=8) as response:  # nosec B310
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError) as exc:
        return False, f"VK API request failed: {exc}"
    except json.JSONDecodeError as exc:
        return False, f"VK API returned invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return False, "VK API returned unexpected response type."
    if "error" in payload:
        vk_error = payload["error"]
        if isinstance(vk_error, dict):
            code = vk_error.get("error_code", "unknown")
            message = vk_error.get("error_msg", "unknown error")
            return False, f"VK API error {code}: {message}"
        return False, f"VK API error: {vk_error}"
    response_obj = payload.get("response")
    if not isinstance(response_obj, list) or not response_obj:
        return False, "VK API returned empty response for users.get."
    return True, ""


def prompt_install_config(
    *,
    non_interactive: bool,
    config_path: Path | None,
    platform_name: str | None = None,
) -> InstallConfig:
    resolved_platform = platform_name or detect_platform()
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

    print()
    _print_bi(resolved_platform, "Мастер установки VK OpenClaw", "VK OpenClaw setup wizard")
    print()
    _print_bi(resolved_platform, "Перед началом нужно:", "What you need before start:")
    _print_bi(
        resolved_platform,
        "1) VK_ACCESS_TOKEN (сообщество VK -> Управление -> Дополнительно -> Работа с API -> Создать ключ)",
        "1) VK_ACCESS_TOKEN (VK community -> Manage -> Advanced -> API access -> Create key)",
    )
    _print_bi(
        resolved_platform,
        "2) VK_ALLOWED_PEERS (ID пользователя для ЛС или peer_id беседы)",
        "2) VK_ALLOWED_PEERS (user id for DM or chat peer_id)",
    )
    _print_bi(
        resolved_platform,
        "3) OPENCLAW_COMMAND (обычно openclaw или ./openclaw_agent_wrapper.sh)",
        "3) Advanced runtime options are selected automatically.",
    )
    _print_bi(resolved_platform, "Документация: docs/vk_setup.md", "Docs: docs/vk_setup.md")
    _print_bi(
        resolved_platform,
        "Безопасность: секреты пишутся только в .env.local и не коммитятся.",
        "Security: secrets are written only to local .env.local and should never be committed.",
    )
    print()

    _print_bi(
        resolved_platform,
        "ADMIN_API_TOKEN защищает admin API эндпоинты.",
        "ADMIN_API_TOKEN secures admin API endpoints.",
    )
    admin_token = secrets.token_hex(32)
    _print_bi(
        resolved_platform,
        "ADMIN_API_TOKEN сгенерирован автоматически.",
        "ADMIN_API_TOKEN was auto-generated.",
    )
    _print_bi(
        resolved_platform,
        "ВНИМАНИЕ: токен будет показан один раз. Сохраните его сейчас в менеджер паролей.",
        "WARNING: token will be shown once. Save it now in your password manager.",
    )
    print(f"ADMIN_API_TOKEN={admin_token}")
    input(
        _bi(
            resolved_platform,
            "Нажмите Enter после сохранения токена...",
            "Press Enter after saving the token...",
        )
    )
    _visual_break()

    print()
    _print_bi(
        resolved_platform,
        "VK_ACCESS_TOKEN: создайте в сообществе VK (Управление -> Дополнительно -> Работа с API -> Создать ключ).",
        "VK_ACCESS_TOKEN: create in VK community settings (Manage -> Advanced -> API access -> Create key).",
    )
    _print_bi(
        resolved_platform,
        "Вставьте токен в открытый ввод ниже (copy/paste).",
        "Paste token in visible input below (copy/paste).",
    )
    vk_access_token = _prompt_visible_required(
        prompt_label=_bi(resolved_platform, "VK_ACCESS_TOKEN: ", "VK_ACCESS_TOKEN: "),
        platform_name=resolved_platform,
    )

    print()
    _print_bi(
        resolved_platform,
        "VK_ALLOWED_PEERS: peer_id разрешенного чата/диалога, например 2000000001 или 123456.",
        "VK_ALLOWED_PEERS: peer_id for allowed dialog/chat, e.g. 2000000001 or 123456.",
    )
    vk_allowed_peers = _prompt_with_default(
        _bi(resolved_platform, "VK_ALLOWED_PEERS", "VK_ALLOWED_PEERS"),
        source.get("VK_ALLOWED_PEERS", "42"),
    )

    print()
    _print_bi(
        resolved_platform,
        "PERSISTENCE_MODE автоматически: file.",
        "PERSISTENCE_MODE is set automatically: file.",
    )
    _print_bi(
        resolved_platform,
        f"OPENCLAW_COMMAND автоматически: {_default_openclaw_command()}",
        f"OPENCLAW_COMMAND is set automatically: {_default_openclaw_command()}",
    )
    mode = "file"
    database_dsn = ""
    redis_dsn = ""
    openclaw_command = _default_openclaw_command()

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
        "FREE_TEXT_ASK_ENABLED=true",
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


def _parse_allowed_peers(vk_allowed_peers: str) -> list[int]:
    parsed: list[int] = []
    seen: set[int] = set()
    for item in vk_allowed_peers.split(","):
        raw = item.strip()
        if not raw:
            continue
        try:
            peer_id = int(raw)
        except ValueError:
            continue
        if peer_id in seen:
            continue
        seen.add(peer_id)
        parsed.append(peer_id)
    return parsed


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


def _peer_list_from_payload(payload: dict[str, object]) -> set[int]:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return set()
    peers: set[int] = set()
    for item in raw_items:
        if isinstance(item, int):
            peers.add(item)
            continue
        if isinstance(item, str):
            try:
                peers.add(int(item))
            except ValueError:
                continue
    return peers


def run_pairing_helper(config: InstallConfig, *, platform_name: str) -> None:
    allowed_peers = _parse_allowed_peers(config.vk_allowed_peers)
    if not allowed_peers:
        _print_bi(
            platform_name,
            "Pairing helper пропущен: не удалось разобрать VK_ALLOWED_PEERS.",
            "Pairing helper skipped: could not parse VK_ALLOWED_PEERS.",
        )
        return
    peer_id = allowed_peers[0]
    if len(allowed_peers) > 1:
        peers_text = ", ".join(str(item) for item in allowed_peers)
        _print_bi(
            platform_name,
            f"Найдено несколько VK_ALLOWED_PEERS: {peers_text}",
            f"Multiple VK_ALLOWED_PEERS detected: {peers_text}",
        )
        chosen_raw = _prompt_with_default(
            _bi(platform_name, "PAIRING_PEER_ID", "PAIRING_PEER_ID"),
            str(peer_id),
        )
        try:
            chosen_peer = int(chosen_raw)
        except ValueError:
            chosen_peer = peer_id
        if chosen_peer in allowed_peers:
            peer_id = chosen_peer
        else:
            _print_bi(
                platform_name,
                f"PAIRING_PEER_ID={chosen_raw} не входит в VK_ALLOWED_PEERS, используем {peer_id}.",
                f"PAIRING_PEER_ID={chosen_raw} is not in VK_ALLOWED_PEERS, using {peer_id}.",
            )
    print()
    _print_bi(platform_name, "Pairing helper", "Pairing helper")
    _print_bi(
        platform_name,
        "Будет запрошен pair code из локального API и показана команда для VK.",
        "It will request a pair code from local API and provide VK command instructions.",
    )
    proceed = input(_bi(platform_name, "Запустить pairing helper сейчас? [Y/n]: ", "Run pairing helper now? [Y/n]: "))
    proceed = proceed.strip().lower()
    if proceed.startswith("n"):
        _print_bi(
            platform_name,
            "Pairing helper пропущен. Можно запустить позже через API.",
            "Pairing helper skipped. You can run it later through API endpoints.",
        )
        return

    base_url = os.environ.get(API_BASE_URL_ENV, DEFAULT_LOCAL_API_BASE_URL).strip() or DEFAULT_LOCAL_API_BASE_URL
    _print_bi(
        platform_name,
        f"Используем API URL: {base_url} (override: {API_BASE_URL_ENV})",
        f"Using API URL: {base_url} (override: {API_BASE_URL_ENV})",
    )
    code_url = f"{base_url.rstrip('/')}/api/v1/pairing/code"
    peers_url = f"{base_url.rstrip('/')}/api/v1/pairing/peers"
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
            _print_bi(
                platform_name,
                "Не удалось прочитать код из ответа /pairing/code.",
                "Could not read code from /pairing/code response.",
            )
            return
        _print_bi(
            platform_name,
            f"Отправьте эту команду в VK чат: /pair {code}",
            f"Send this command in VK chat: /pair {code}",
        )
        input(_bi(platform_name, "Нажмите Enter после отправки /pair ...", "Press Enter after sending /pair ..."))
        peers_payload: dict[str, object] = {}
        paired = False
        for _ in range(15):
            peers_payload = _http_json(
                peers_url,
                method="GET",
                payload={},
                bearer_token=config.admin_api_token,
            )
            if peer_id in _peer_list_from_payload(peers_payload):
                paired = True
                break
            time.sleep(1)
        if paired:
            _print_bi(
                platform_name,
                f"Pairing подтвержден через VK. Peer {peer_id} найден в списке paired.",
                f"Pairing confirmed via VK. Peer {peer_id} is present in paired peers.",
            )
        else:
            _print_bi(
                platform_name,
                "Pairing не подтвержден: peer не появился в paired peers.",
                "Pairing not confirmed: peer did not appear in paired peers.",
            )
            _print_bi(
                platform_name,
                f"Текущий ответ pairing/peers: {peers_payload}",
                f"Current pairing/peers payload: {peers_payload}",
            )
        status_payload = _http_json(
            status_url,
            method="GET",
            payload={},
            bearer_token=config.admin_api_token,
        )
        _print_bi(platform_name, f"Снимок статуса: {status_payload}", f"Status snapshot: {status_payload}")
        if paired:
            _print_bi(
                platform_name,
                "Pairing helper завершен. Проверьте в VK: /status, затем /ask привет.",
                "Pairing helper completed. Validate in VK: /status then /ask hello.",
            )
        else:
            _print_bi(
                platform_name,
                "Pairing helper завершен с предупреждением: pairing не подтвержден.",
                "Pairing helper completed with warning: pairing was not confirmed.",
            )
    except (error.HTTPError, error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        _print_bi(platform_name, f"Ошибка pairing helper: {exc}", f"Pairing helper failed: {exc}")
        _print_bi(
            platform_name,
            "Можно продолжить вручную через /api/v1/pairing/code и команду /pair <code> в VK.",
            "You can continue manually with /api/v1/pairing/code and /pair <code> in VK.",
        )


def render_local_fallback_commands(*, working_directory: Path) -> list[str]:
    wd = shlex.quote(str(working_directory))
    return [
        f"cd {wd}",
        "source .venv/bin/activate",
        "set -a && source .env.local && set +a",
        "nohup ./.venv/bin/vk-openclaw run-api --host 127.0.0.1 --port 8000 >/tmp/vk_api.log 2>&1 &",
        "nohup ./.venv/bin/vk-openclaw run-worker --interval-seconds 5 >/tmp/vk_worker.log 2>&1 &",
        "tail -n 60 /tmp/vk_worker.log",
    ]


def run_setup(*, non_interactive: bool, config_path: Path | None, dry_run: bool) -> int:
    platform_name = detect_platform()
    service_mode = "system-service"
    print_author_info()
    if platform_name == "unsupported":
        print("Error: setup is supported only on Linux and Windows.")
        return 1

    if platform_name == "linux":
        systemd_ok, systemd_reason = check_systemd_user_available()
        if not systemd_ok:
            _print_bi(
                platform_name,
                "Предупреждение: systemd --user недоступен, используем fallback-local режим.",
                "Warning: systemd --user is unavailable, using fallback-local mode.",
            )
            print(_bi(platform_name, f"Причина: {systemd_reason}", f"Reason: {systemd_reason}"))
            service_mode = "fallback-local"
    if platform_name == "windows" and resolve_winsw_executable() is None and not dry_run:
        print("Error: WinSW is required on Windows. Set WINSW_PATH or provide tools/winsw/winsw.exe.")
        return 1

    openclaw_ok, openclaw_reason = check_openclaw_installed()
    if not openclaw_ok:
        _print_bi(platform_name, "Ошибка: openclaw не установлен.", "Error: openclaw is not installed.")
        print(_bi(platform_name, f"Причина: {openclaw_reason}", openclaw_reason))
        _print_bi(
            platform_name,
            "Установите openclaw и проверьте: openclaw --version",
            "Install openclaw and verify with: openclaw --version",
        )
        return 1

    config = prompt_install_config(
        non_interactive=non_interactive,
        config_path=config_path,
        platform_name=platform_name,
    )
    errors = validate_install_config(config)
    if errors:
        print("Config validation failed:")
        for issue in errors:
            print(f"- {issue}")
        return 1

    warnings = connectivity_warnings(config)
    if warnings:
        _print_bi(platform_name, "Предупреждения по подключению:", "Connectivity warnings:")
        for line in warnings:
            print(f"- {line}")

    print(render_secret_confirmation(config, platform_name=platform_name))

    env_content = render_env_local(config, target_os=platform_name)
    workdir = Path.cwd()
    env_path = workdir / ".env.local"
    if dry_run:
        _print_bi(
            platform_name,
            "Режим dry-run: файлы и сервисы не изменялись.",
            "Dry-run mode: no files or services were changed.",
        )
        _print_bi(
            platform_name,
            "Предпросмотр (.env.local с редактированием секретов):",
            "Preview (.env.local redacted):",
        )
        print(redact_env_preview(env_content))
        return 0

    vk_ok, vk_reason = verify_vk_access_token(config.vk_access_token)
    if not vk_ok:
        _print_bi(
            platform_name,
            "Ошибка: VK_ACCESS_TOKEN не прошел проверку preflight.",
            "Error: VK_ACCESS_TOKEN failed preflight validation.",
        )
        print(_bi(platform_name, f"Причина: {vk_reason}", f"Reason: {vk_reason}"))
        _print_bi(
            platform_name,
            "Проверьте токен и права в VK, затем запустите setup снова.",
            "Check VK token and permissions, then run setup again.",
        )
        return 1

    write_env_local(env_path, env_content)
    wrapper_path = workdir / "openclaw_agent_wrapper.sh"
    if platform_name == "linux" and wrapper_path.exists():
        try:
            wrapper_path.chmod(wrapper_path.stat().st_mode | 0o111)
            _print_bi(
                platform_name,
                f"Wrapper отмечен как executable: {wrapper_path}",
                f"Wrapper marked executable: {wrapper_path}",
            )
        except OSError as exc:
            _print_bi(
                platform_name,
                f"Предупреждение: не удалось выставить executable для wrapper: {exc}",
                f"Warning: failed to mark wrapper executable: {exc}",
            )

    if service_mode == "system-service":
        install_code = install_service_files(
            platform_name=platform_name,
            working_directory=workdir,
            env_path=env_path,
            cli_executable=resolve_cli_executable(),
        )
        if install_code != 0:
            print("Service installation failed.")
            return install_code
        _print_bi(platform_name, "Установка завершена.", "Setup completed.")
        print(f"- Config file: {env_path}")
        print(_bi(platform_name, f"- Режим сервиса: {service_mode}", f"- Service mode: {service_mode}"))

        start_code = manage_service("restart")
        if start_code != 0:
            _print_bi(
                platform_name,
                "Предупреждение: restart вернул ненулевой код, пробуем start.",
                "Warning: service restart returned non-zero status, trying start.",
            )
            start_code = manage_service("start")
        if start_code != 0:
            _print_bi(
                platform_name,
                "Предупреждение: запуск сервиса завершился с ненулевым статусом.",
                "Warning: service start returned non-zero status.",
            )
        status_code = manage_service("status")
        if status_code != 0:
            _print_bi(
                platform_name,
                "Предупреждение: проверка статуса сервиса вернула ненулевой код.",
                "Warning: service status returned non-zero status.",
            )
        else:
            _print_bi(
                platform_name,
                "Проверка статуса сервиса пройдена.",
                "Service status check passed.",
            )

        if not non_interactive:
            run_pairing_helper(config, platform_name=platform_name)
    else:
        _print_bi(platform_name, "Установка завершена.", "Setup completed.")
        print(f"- Config file: {env_path}")
        print(_bi(platform_name, f"- Режим сервиса: {service_mode}", f"- Service mode: {service_mode}"))
        _print_bi(
            platform_name,
            "Сервисы не установлены в systemd. Используйте локальный fallback-запуск ниже.",
            "Services were not installed in systemd. Use local fallback commands below.",
        )
        _print_bi(
            platform_name,
            "Важно: сначала загрузите .env.local (иначе worker завершится с VK API error 15: token required).",
            "Important: load .env.local first (otherwise worker may fail with VK API error 15: token required).",
        )
        _print_bi(platform_name, "Команды fallback-local:", "Fallback-local commands:")
        for line in render_local_fallback_commands(working_directory=workdir):
            print(f"  {line}")
        _print_bi(
            platform_name,
            "Проверка в VK после запуска: /status, затем /ask привет.",
            "After launching, validate in VK: /status, then /ask hello.",
        )

    _print_bi(platform_name, "Где взять токены позже:", "Where to find tokens later:")
    print(f"- .env.local: {env_path}")
    _print_bi(
        platform_name,
        "- Безопасная проверка: awk -F= '/^(ADMIN_API_TOKEN|VK_ACCESS_TOKEN)=/{print $1\": \" (length($2)>0?\"SET (\"length($2)\" chars)\":\"EMPTY\")}' .env.local",
        "- Safe check: awk -F= '/^(ADMIN_API_TOKEN|VK_ACCESS_TOKEN)=/{print $1\": \" (length($2)>0?\"SET (\"length($2)\" chars)\":\"EMPTY\")}' .env.local",
    )
    _print_bi(
        platform_name,
        "- Аварийно (покажет значение): grep '^ADMIN_API_TOKEN=' .env.local",
        "- Emergency (reveals value): grep '^ADMIN_API_TOKEN=' .env.local",
    )
    return 0


def run_install(*, non_interactive: bool, config_path: Path | None) -> int:
    print("Notice: 'install' is deprecated. Use 'setup' for new flows.")
    return run_setup(non_interactive=non_interactive, config_path=config_path, dry_run=False)

