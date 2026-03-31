"""Health and preflight checks for local runtime."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import socket
import sys
from typing import Callable

from vk_openclaw_service.core.settings import RuntimeSettings
from vk_openclaw_service.infra.vk.client_http import VkApiClient


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str


def env_file_path(project_root: Path | None = None) -> Path:
    root = project_root or Path.cwd()
    return root / ".env.local"


def check_env_local_exists(project_root: Path | None = None) -> CheckResult:
    env_path = env_file_path(project_root)
    if env_path.exists():
        return CheckResult("env.local", True, f"Found: {env_path}")
    return CheckResult("env.local", False, f"Missing file: {env_path}")


def check_python_version(min_major: int = 3, min_minor: int = 12) -> CheckResult:
    version = sys.version_info
    ok = (version.major, version.minor) >= (min_major, min_minor)
    current = f"{version.major}.{version.minor}.{version.micro}"
    required = f"{min_major}.{min_minor}+"
    return CheckResult("python_version", ok, f"Current: {current}; required: {required}")


def _parse_gateway_endpoint(url: str) -> tuple[str, int]:
    raw = url.strip()
    if raw.startswith("ws://"):
        raw = raw[5:]
    if raw.startswith("wss://"):
        raw = raw[6:]
    host_port = raw.split("/", 1)[0]
    if ":" in host_port:
        host, port_raw = host_port.rsplit(":", 1)
        return host or "127.0.0.1", int(port_raw)
    return host_port or "127.0.0.1", 80


def check_gateway_reachable(url: str = "ws://127.0.0.1:18789", timeout_sec: float = 2.0) -> CheckResult:
    host, port = _parse_gateway_endpoint(url)
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return CheckResult("gateway", True, f"Reachable: {url}")
    except OSError as exc:
        return CheckResult("gateway", False, f"Unreachable: {url} ({exc})")


def wait_for_gateway(
    url: str = "ws://127.0.0.1:18789",
    *,
    poll_sec: float = 2.0,
    timeout_sec: float = 60.0,
    sleeper: Callable[[float], None] | None = None,
) -> CheckResult:
    import time

    sleep_fn = sleeper or time.sleep
    deadline = time.monotonic() + timeout_sec
    last = check_gateway_reachable(url=url)
    while not last.ok and time.monotonic() < deadline:
        sleep_fn(poll_sec)
        last = check_gateway_reachable(url=url)
    if last.ok:
        return last
    return CheckResult("gateway_wait", False, f"Timeout after {int(timeout_sec)}s waiting for {url}")


def check_port_available(port: int = 8000, host: str = "127.0.0.1") -> CheckResult:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        return CheckResult("port", True, f"Port {host}:{port} is free")
    except OSError as exc:
        return CheckResult("port", False, f"Port {host}:{port} is busy ({exc})")
    finally:
        sock.close()


def check_vk_token(token: str) -> CheckResult:
    if not token.strip():
        return CheckResult("vk_token", False, "VK_ACCESS_TOKEN is empty")
    client = VkApiClient(token=token)
    try:
        response = client.call("users.get", {})
    except Exception as exc:
        return CheckResult("vk_token", False, f"VK token preflight failed: {exc}")
    if isinstance(response, list) and response:
        return CheckResult("vk_token", True, "VK token is valid (users.get)")
    return CheckResult("vk_token", False, "VK token preflight returned empty users.get response")


def check_pairing_coverage(settings: RuntimeSettings) -> CheckResult:
    pairing_path = Path(settings.state_dir) / "pairing.json"
    if not pairing_path.exists():
        return CheckResult("pairing", False, f"Pairing file missing: {pairing_path}")
    try:
        payload = json.loads(pairing_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return CheckResult("pairing", False, f"Failed to read pairing file: {exc}")
    paired_raw = payload.get("paired_peers", [])
    paired: set[int] = set()
    if isinstance(paired_raw, list):
        for item in paired_raw:
            if isinstance(item, int):
                paired.add(item)
    missing = sorted(set(settings.allowed_peers) - paired)
    if missing:
        return CheckResult("pairing", False, f"Missing paired peers: {missing}")
    return CheckResult("pairing", True, "All allowed peers are paired")
