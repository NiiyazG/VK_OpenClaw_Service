from __future__ import annotations

import argparse
import importlib
from pathlib import Path
from typing import Sequence

from vk_openclaw_service import installer
from vk_openclaw_service.worker_main import main as worker_main


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vk-openclaw")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Interactive WSL installer")
    install_parser.add_argument("--non-interactive", action="store_true", help="Run install without prompts")
    install_parser.add_argument("--config", type=Path, default=None, help="Path to JSON config for install")

    subparsers.add_parser("start", help="Start systemd user services")
    subparsers.add_parser("stop", help="Stop systemd user services")
    subparsers.add_parser("status", help="Show systemd user service status")

    run_api_parser = subparsers.add_parser("run-api", help="Run API process")
    run_api_parser.add_argument("--host", default="127.0.0.1")
    run_api_parser.add_argument("--port", type=int, default=8000)

    run_worker_parser = subparsers.add_parser("run-worker", help="Run worker process")
    run_worker_parser.add_argument("--once", action="store_true")
    run_worker_parser.add_argument("--interval-seconds", type=float, default=None)
    run_worker_parser.add_argument("--retry-backoff-seconds", type=float, default=None)
    run_worker_parser.add_argument("--max-backoff-seconds", type=float, default=None)

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

    if args.command == "install":
        return installer.run_install(non_interactive=args.non_interactive, config_path=args.config)
    if args.command == "start":
        return installer.systemd_user("start")
    if args.command == "stop":
        return installer.systemd_user("stop")
    if args.command == "status":
        return installer.systemd_user_status()
    if args.command == "run-api":
        uvicorn = importlib.import_module("uvicorn")
        uvicorn.run("vk_openclaw_service.main:app", host=args.host, port=args.port)
        return 0
    if args.command == "run-worker":
        return _run_worker_from_args(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
