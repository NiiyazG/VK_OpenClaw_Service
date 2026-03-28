"""Structured logging helpers."""

from __future__ import annotations

import json
import logging


def get_worker_logger() -> logging.Logger:
    return logging.getLogger("vk_openclaw_service.worker")


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    logger.info(json.dumps({"event": event, **fields}, sort_keys=True))
