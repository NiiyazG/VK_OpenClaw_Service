"""Structured logging helpers."""

from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from vk_openclaw_service.core.settings import RuntimeSettings, get_settings


def configure_logging(settings: RuntimeSettings | None = None) -> logging.Logger:
    runtime = settings or get_settings()
    logger = logging.getLogger("vk_openclaw_service.worker")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        stream = logging.StreamHandler()
        stream.setLevel(logging.INFO)
        logger.addHandler(stream)
    if _is_systemd_runtime():
        return logger
    log_path = Path(runtime.state_dir) / "vk-openclaw.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    has_file_handler = any(
        isinstance(handler, RotatingFileHandler) and getattr(handler, "baseFilename", "") == str(log_path.resolve())
        for handler in logger.handlers
    )
    if not has_file_handler:
        file_handler = RotatingFileHandler(
            filename=log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)
    return logger


def _is_systemd_runtime() -> bool:
    return bool(os.environ.get("INVOCATION_ID") or os.environ.get("JOURNAL_STREAM"))


def get_worker_logger() -> logging.Logger:
    return configure_logging()


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    logger.info(json.dumps({"event": event, **fields}, sort_keys=True))
