"""Worker entrypoint for VK polling runtime."""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable, Sequence
from typing import Protocol

from vk_openclaw_service.bootstrap.container import build_container
from vk_openclaw_service.core.settings import get_settings
from vk_openclaw_service.core.logging import get_worker_logger, log_event
from vk_openclaw_service.health_check import check_vk_token
from vk_openclaw_service.infra.vk.transport import VkDeliveryOutcome, classify_vk_send_failure
from vk_openclaw_service.services.vk_runtime import LeaseLostError


class RuntimeService(Protocol):
    def poll_once(self, heartbeat: Callable[[], bool] | None = None) -> int: ...


class RetryDrainer(Protocol):
    def drain_once(self, *, limit: int = 50) -> int: ...


class WorkerLease(Protocol):
    def acquire(self) -> str | None: ...
    def refresh(self, token: str) -> bool: ...
    def release(self, token: str) -> None: ...


def run_worker_loop(
    runtime_service: RuntimeService,
    *,
    retry_drainer: RetryDrainer | None = None,
    worker_lease: WorkerLease | None = None,
    iterations: int | None = None,
    interval_seconds: float = 5.0,
    retry_backoff_seconds: float = 1.0,
    max_backoff_seconds: float = 30.0,
    sleeper: Callable[[float], None] = time.sleep,
    failure_classifier: Callable[[Exception], VkDeliveryOutcome] = classify_vk_send_failure,
    logger: logging.Logger | None = None,
) -> int:
    worker_logger = logger or get_worker_logger()
    processed_total = 0
    iteration = 0
    current_backoff = retry_backoff_seconds
    log_event(
        worker_logger,
        "worker_loop_started",
        interval_seconds=interval_seconds,
        iterations=iterations,
        retry_backoff_seconds=retry_backoff_seconds,
        max_backoff_seconds=max_backoff_seconds,
    )
    while iterations is None or iteration < iterations:
        try:
            lease_token = worker_lease.acquire() if worker_lease is not None else None
            if worker_lease is not None and lease_token is None:
                iteration += 1
                log_event(
                    worker_logger,
                    "worker_poll_skipped_lease_not_acquired",
                    iteration=iteration,
                )
                if iterations is not None and iteration >= iterations:
                    break
                sleeper(interval_seconds)
                continue
            try:
                drained = retry_drainer.drain_once() if retry_drainer is not None else 0
                if worker_lease is not None and lease_token is not None and not worker_lease.refresh(lease_token):
                    iteration += 1
                    log_event(
                        worker_logger,
                        "worker_poll_skipped_lease_lost",
                        iteration=iteration,
                        drained=drained,
                    )
                    if iterations is not None and iteration >= iterations:
                        break
                    sleeper(interval_seconds)
                    continue
                heartbeat = None
                if worker_lease is not None and lease_token is not None:
                    def heartbeat() -> bool:
                        return worker_lease.refresh(lease_token)
                try:
                    processed = runtime_service.poll_once(heartbeat=heartbeat)
                except LeaseLostError:
                    iteration += 1
                    log_event(
                        worker_logger,
                        "worker_poll_skipped_lease_lost",
                        iteration=iteration,
                        drained=drained,
                    )
                    if iterations is not None and iteration >= iterations:
                        break
                    sleeper(interval_seconds)
                    continue
            finally:
                if worker_lease is not None and lease_token is not None:
                    worker_lease.release(lease_token)
            processed_total += drained + processed
            iteration += 1
            current_backoff = retry_backoff_seconds
            log_event(
                worker_logger,
                "worker_poll_succeeded",
                iteration=iteration,
                drained=drained,
                processed=processed,
                processed_total=processed_total,
            )
            if iterations is not None and iteration >= iterations:
                break
            sleeper(interval_seconds)
        except Exception as exc:
            outcome = failure_classifier(exc)
            if outcome is not VkDeliveryOutcome.RETRY:
                log_event(
                    worker_logger,
                    "worker_poll_failed",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                raise
            log_event(
                worker_logger,
                "worker_poll_retryable_failure",
                error=str(exc),
                error_type=type(exc).__name__,
                backoff_seconds=current_backoff,
            )
            sleeper(current_backoff)
            current_backoff = min(current_backoff * 2, max_backoff_seconds)
    log_event(
        worker_logger,
        "worker_loop_completed",
        iterations_completed=iteration,
        processed_total=processed_total,
    )
    return processed_total


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vk-openclaw-worker")
    parser.add_argument("--once", action="store_true", help="Run a single polling iteration and exit.")
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=None,
        help="Delay between polling iterations when running continuously.",
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=None,
        help="Initial delay before retrying a retryable polling failure.",
    )
    parser.add_argument(
        "--max-backoff-seconds",
        type=float,
        default=None,
        help="Maximum delay between retry attempts after consecutive retryable failures.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO)
    settings = get_settings(reload=True)
    preflight = check_vk_token(settings.vk_access_token)
    if not preflight.ok:
        raise SystemExit(f"Worker preflight failed: {preflight.message}")
    container = build_container(settings)
    interval_seconds = args.interval_seconds or container.settings.worker_interval_sec
    retry_backoff_seconds = args.retry_backoff_seconds or container.settings.worker_retry_backoff_sec
    max_backoff_seconds = args.max_backoff_seconds or container.settings.worker_max_backoff_sec
    run_worker_loop(
        container.vk_runtime_service,
        retry_drainer=container.retry_drainer,
        worker_lease=container.worker_lease,
        iterations=1 if args.once else None,
        interval_seconds=interval_seconds,
        retry_backoff_seconds=retry_backoff_seconds,
        max_backoff_seconds=max_backoff_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
