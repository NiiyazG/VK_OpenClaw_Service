from __future__ import annotations

import argparse
import importlib
from pathlib import Path
from typing import Sequence

from vk_openclaw_service.core.settings import get_settings
from vk_openclaw_service.doctor import run_doctor
from vk_openclaw_service import installer
from vk_openclaw_service.launcher import start_all, status_all, stop_all
from vk_openclaw_service.worker_main import main as worker_main


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vk-openclaw")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser("setup", help="Cross-platform guided installer")
    setup_parser.add_argument("--non-interactive", action="store_true", help="Run setup without prompts")
    setup_parser.add_argument("--config", type=Path, default=None, help="Path to JSON config for setup")
    setup_parser.add_argument("--dry-run", action="store_true", help="Validate and preview setup without writes")
    # Backward-compatible alias for earlier releases.
    install_parser = subparsers.add_parser("install", help="Alias for setup")
    install_parser.add_argument("--non-interactive", action="store_true", help="Run setup without prompts")
    install_parser.add_argument("--config", type=Path, default=None, help="Path to JSON config for setup")
    install_parser.add_argument("--dry-run", action="store_true", help="Validate and preview setup without writes")

    subparsers.add_parser("start", help="Start systemd user services")
    subparsers.add_parser("stop", help="Stop systemd user services")
    subparsers.add_parser("status", help="Show service status")

    run_api_parser = subparsers.add_parser("run-api", help="Run API process")
    run_api_parser.add_argument("--host", default="127.0.0.1")
    run_api_parser.add_argument("--port", type=int, default=8000)

    run_worker_parser = subparsers.add_parser("run-worker", help="Run worker process")
    run_worker_parser.add_argument("--once", action="store_true")
    run_worker_parser.add_argument("--interval-seconds", type=float, default=None)
    run_worker_parser.add_argument("--retry-backoff-seconds", type=float, default=None)
    run_worker_parser.add_argument("--max-backoff-seconds", type=float, default=None)
    run_all_parser = subparsers.add_parser("run-all", help="Run API + worker")
    run_all_parser.add_argument("--wait-for-gateway", action="store_true")
    subparsers.add_parser("stop-all", help="Stop API + worker from PID files")
    subparsers.add_parser("doctor", help="Run environment diagnostics")

    return parser


def _run_worker_from_args(args: argparse.Namespace) -> int:
    argv: list[str] = []
    if args.once:
        argv.append("--once")
    if args.interval_seconds is not None:
        argv.extend(["--interval-seconds", str(args.interval_seconds)])
    if args.retry_backoff_seconds is not None:
        argv.extend(["--retry-backoff-seconds", str(args.retry_backoff_seconds)])
    if args.max_backoff_seconds is not None:
        argv.extend(["--max-backoff-seconds", str(args.max_backoff_seconds)])
    return worker_main(argv)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command in {"setup", "install"}:
        return installer.run_setup(
            non_interactive=args.non_interactive,
            config_path=args.config,
            dry_run=args.dry_run,
        )
    if args.command == "start":
        return installer.manage_service("start")
    if args.command == "stop":
        return installer.manage_service("stop")
    if args.command == "status":
        return installer.manage_service("status")
    if args.command == "run-api":
        uvicorn = importlib.import_module("uvicorn")
        uvicorn.run("vk_openclaw_service.main:app", host=args.host, port=args.port)
        return 0
    if args.command == "run-worker":
        return _run_worker_from_args(args)
    if args.command == "run-all":
        settings = get_settings(reload=True)
        ok, message = start_all(settings, wait_for_gateway_enabled=bool(args.wait_for_gateway))
        print(message)
        if ok:
            current = status_all(settings)
            print(f"log: {current['log_file']}")
            return 0
        return 1
    if args.command == "stop-all":
        settings = get_settings(reload=True)
        ok, message = stop_all(settings)
        print(message)
        return 0 if ok else 1
    if args.command == "doctor":
        return run_doctor()

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
