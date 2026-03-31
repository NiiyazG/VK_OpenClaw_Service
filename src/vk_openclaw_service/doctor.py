"""Diagnostic command implementation."""

from __future__ import annotations

from vk_openclaw_service.core.settings import get_settings
from vk_openclaw_service.health_check import (
    CheckResult,
    check_env_local_exists,
    check_gateway_reachable,
    check_pairing_coverage,
    check_port_available,
    check_python_version,
    check_vk_token,
)


def run_doctor() -> int:
    settings = get_settings(reload=True)
    checks: list[CheckResult] = [
        check_env_local_exists(),
        check_python_version(3, 12),
        check_port_available(8000, "127.0.0.1"),
        check_gateway_reachable("ws://127.0.0.1:18789"),
        check_vk_token(settings.vk_access_token),
        check_pairing_coverage(settings),
    ]
    failed = False
    print("vk-openclaw doctor")
    for item in checks:
        status = "OK" if item.ok else "FAIL"
        print(f"- [{status}] {item.name}: {item.message}")
        if not item.ok:
            failed = True
            _print_fix_hint(item.name)
    return 1 if failed else 0


def _print_fix_hint(name: str) -> None:
    hints = {
        "env.local": "Fix: run `vk-openclaw setup` and ensure .env.local is in project root.",
        "python_version": "Fix: install Python 3.12+ and recreate virtualenv.",
        "port": "Fix: stop process on port 8000 or change API port for local run.",
        "gateway": "Fix: start OpenClaw gateway on ws://127.0.0.1:18789.",
        "vk_token": "Fix: set a valid VK_ACCESS_TOKEN in .env.local.",
        "pairing": "Fix: complete pairing flow for all VK_ALLOWED_PEERS.",
    }
    hint = hints.get(name)
    if hint:
        print(f"  {hint}")

