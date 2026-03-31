"""Local process launcher for API + worker."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess  # nosec B404
import sys
import time

from vk_openclaw_service.core.settings import RuntimeSettings
from vk_openclaw_service.health_check import wait_for_gateway


@dataclass(frozen=True)
class LaunchPaths:
    state_dir: Path
    api_pid: Path
    worker_pid: Path
    log_file: Path


def build_launch_paths(settings: RuntimeSettings) -> LaunchPaths:
    state_dir = Path(settings.state_dir)
    return LaunchPaths(
        state_dir=state_dir,
        api_pid=state_dir / "api.pid",
        worker_pid=state_dir / "worker.pid",
        log_file=state_dir / "vk-openclaw.log",
    )


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        pid = int(raw)
    except ValueError:
        return None
    return pid if pid > 0 else None


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _write_pid(path: Path, pid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid), encoding="utf-8")


def _remove_pid(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _stop_pid(path: Path) -> bool:
    pid = _read_pid(path)
    if pid is None:
        _remove_pid(path)
        return True
    if not _is_pid_alive(pid):
        _remove_pid(path)
        return True
    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        if not _is_pid_alive(pid):
            _remove_pid(path)
            return True
        time.sleep(0.2)
    return False


def status_all(settings: RuntimeSettings) -> dict[str, object]:
    paths = build_launch_paths(settings)
    api_pid = _read_pid(paths.api_pid)
    worker_pid = _read_pid(paths.worker_pid)
    api_alive = api_pid is not None and _is_pid_alive(api_pid)
    worker_alive = worker_pid is not None and _is_pid_alive(worker_pid)
    return {
        "api_pid": api_pid,
        "worker_pid": worker_pid,
        "api_running": api_alive,
        "worker_running": worker_alive,
        "log_file": str(paths.log_file),
    }


def start_all(
    settings: RuntimeSettings,
    *,
    wait_for_gateway_enabled: bool = False,
    gateway_url: str = "ws://127.0.0.1:18789",
) -> tuple[bool, str]:
    paths = build_launch_paths(settings)
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    _roll_log_if_needed(paths.log_file, max_bytes=10 * 1024 * 1024, backups=3)
    existing = status_all(settings)
    if existing["api_running"] or existing["worker_running"]:
        return False, "API or worker is already running"
    _remove_pid(paths.api_pid)
    _remove_pid(paths.worker_pid)

    if wait_for_gateway_enabled:
        gateway = wait_for_gateway(url=gateway_url, poll_sec=2.0, timeout_sec=60.0)
        if not gateway.ok:
            return False, gateway.message

    env = dict(os.environ)
    log_handle = paths.log_file.open("ab")
    try:
        api_proc = subprocess.Popen(  # nosec B603
            [sys.executable, "-m", "vk_openclaw_service.cli", "run-api", "--host", "127.0.0.1", "--port", "8000"],
            stdout=log_handle,
            stderr=log_handle,
            env=env,
        )
        worker_proc = subprocess.Popen(  # nosec B603
            [sys.executable, "-m", "vk_openclaw_service.cli", "run-worker", "--interval-seconds", "5"],
            stdout=log_handle,
            stderr=log_handle,
            env=env,
        )
    finally:
        log_handle.close()
    _write_pid(paths.api_pid, api_proc.pid)
    _write_pid(paths.worker_pid, worker_proc.pid)
    time.sleep(0.6)
    now = status_all(settings)
    if now["api_running"] and now["worker_running"]:
        return True, f"Started api={now['api_pid']} worker={now['worker_pid']}"
    return False, f"Start failed, inspect log: {paths.log_file}"


def stop_all(settings: RuntimeSettings) -> tuple[bool, str]:
    paths = build_launch_paths(settings)
    worker_ok = _stop_pid(paths.worker_pid)
    api_ok = _stop_pid(paths.api_pid)
    if worker_ok and api_ok:
        return True, "API and worker stopped"
    return False, "Failed to stop one or more processes"


def _roll_log_if_needed(path: Path, *, max_bytes: int, backups: int) -> None:
    if not path.exists():
        return
    try:
        if path.stat().st_size <= max_bytes:
            return
    except OSError:
        return
    for idx in range(backups, 0, -1):
        target = Path(f"{path}.{idx}")
        prev = Path(f"{path}.{idx - 1}") if idx > 1 else path
        if prev.exists():
            try:
                if target.exists():
                    target.unlink()
                prev.rename(target)
            except OSError:
                continue
