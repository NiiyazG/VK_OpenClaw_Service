"""Application container."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vk_openclaw_service.core.settings import RuntimeSettings, get_settings
from vk_openclaw_service.domain.openclaw import run_openclaw_command
from vk_openclaw_service.infra.persistence import StorageState, build_repository_bundle
from vk_openclaw_service.infra.redis_adapter import build_redis_adapter, probe_redis_driver
from vk_openclaw_service.services.rate_limit import FixedWindowRateLimiter, InMemoryCounterStore
from vk_openclaw_service.services.replay_guard import InMemoryReplayStore, ReplayGuard
from vk_openclaw_service.services.retry_drainer import RetryDrainer
from vk_openclaw_service.services.worker_lease import InMemoryWorkerLeaseStore, WorkerLease
from vk_openclaw_service.services.retry_queue import InMemoryRetryQueueStore, RetryQueue
from vk_openclaw_service.infra.vk.client_http import VkApiClient
from vk_openclaw_service.infra.vk.transport import VkDeliveryOutcome
from vk_openclaw_service.services.pairing_service import PairingService
from vk_openclaw_service.services.vk_runtime import VkRuntimeService
from vk_openclaw_service.services.worker_service import WorkerService


@dataclass
class AppContainer:
    settings: RuntimeSettings
    storage: StorageState
    vk_client: VkApiClient
    pairing_repository: Any
    checkpoint_repository: Any
    audit_repository: Any
    dead_letter_repository: Any
    saved_query_repository: Any
    pairing_service: PairingService
    worker_service: WorkerService
    worker_lease: WorkerLease
    retry_drainer: RetryDrainer
    vk_runtime_service: VkRuntimeService


def build_container(settings: RuntimeSettings | None = None) -> AppContainer:
    runtime_settings = settings or get_settings()
    vk_client = VkApiClient(token=runtime_settings.vk_access_token)
    repositories = build_repository_bundle(runtime_settings)
    rate_limiter = _build_rate_limiter(runtime_settings)
    replay_guard = _build_replay_guard(runtime_settings)
    retry_queue = _build_retry_queue(runtime_settings)
    worker_lease = _build_worker_lease(runtime_settings, repositories.audit_repository)
    pairing_repository: Any = repositories.pairing_repository
    checkpoint_repository: Any = repositories.checkpoint_repository
    audit_repository: Any = repositories.audit_repository
    dead_letter_repository: Any = repositories.dead_letter_repository
    saved_query_repository: Any = repositories.saved_query_repository
    pairing_service = PairingService(
        repository=pairing_repository,
        audit_repository=audit_repository,
        allowed_peers=set(runtime_settings.allowed_peers),
        ttl_seconds=runtime_settings.pair_code_ttl_sec,
    )
    worker_service = WorkerService(
        checkpoint_repository=checkpoint_repository,
        delivery_classifier=lambda exc: (
            VkDeliveryOutcome.RETRY if isinstance(exc, TimeoutError) else VkDeliveryOutcome.REJECT
        ),
        openclaw_runner=lambda prompt: run_openclaw_command(
            runtime_settings.openclaw_command,
            prompt,
            timeout_seconds=runtime_settings.openclaw_timeout_sec,
        ),
        reply_sender=lambda peer_id, text: vk_client.send_text(peer_id, text),
        audit_repository=audit_repository,
        dead_letter_repository=dead_letter_repository,
        rate_limiter=rate_limiter,
        replay_guard=replay_guard,
        retry_queue=retry_queue,
        retry_queue_max_attempts=runtime_settings.retry_queue_max_attempts,
        free_text_ask_enabled=runtime_settings.free_text_ask_enabled,
    )
    vk_runtime_service = VkRuntimeService(
        vk_client=vk_client,
        checkpoint_repository=checkpoint_repository,
        pairing_repository=pairing_repository,
        worker_service=worker_service,
        status_payload_factory=lambda: {"mode": runtime_settings.vk_mode},
        allowed_peers=set(runtime_settings.allowed_peers),
    )
    retry_drainer = RetryDrainer(
        retry_queue=retry_queue,
        checkpoint_repository=checkpoint_repository,
        worker_service=worker_service,
        status_payload_factory=lambda: {"mode": runtime_settings.vk_mode},
    )
    return AppContainer(
        settings=runtime_settings,
        storage=repositories.storage,
        vk_client=vk_client,
        pairing_repository=pairing_repository,
        checkpoint_repository=checkpoint_repository,
        audit_repository=audit_repository,
        dead_letter_repository=dead_letter_repository,
        saved_query_repository=saved_query_repository,
        pairing_service=pairing_service,
        worker_service=worker_service,
        worker_lease=worker_lease,
        retry_drainer=retry_drainer,
        vk_runtime_service=vk_runtime_service,
    )


def _build_rate_limiter(settings: RuntimeSettings) -> FixedWindowRateLimiter:
    if settings.redis_dsn and probe_redis_driver().available:
        try:
            redis_session = build_redis_adapter(settings.redis_dsn).open_session()
            return FixedWindowRateLimiter(store=redis_session, limit=settings.rate_per_min)
        except Exception:
            return FixedWindowRateLimiter(store=InMemoryCounterStore(), limit=settings.rate_per_min)
    return FixedWindowRateLimiter(store=InMemoryCounterStore(), limit=settings.rate_per_min)


def _build_replay_guard(settings: RuntimeSettings) -> ReplayGuard:
    if settings.redis_dsn and probe_redis_driver().available:
        try:
            redis_session = build_redis_adapter(settings.redis_dsn).open_session()
            return ReplayGuard(store=redis_session, ttl_seconds=settings.replay_ttl_sec)
        except Exception:
            return ReplayGuard(store=InMemoryReplayStore(), ttl_seconds=settings.replay_ttl_sec)
    return ReplayGuard(store=InMemoryReplayStore(), ttl_seconds=settings.replay_ttl_sec)


def _build_retry_queue(settings: RuntimeSettings) -> RetryQueue:
    if settings.redis_dsn and probe_redis_driver().available:
        try:
            redis_session = build_redis_adapter(settings.redis_dsn).open_session()
            return RetryQueue(
                store=redis_session,
                key=settings.retry_queue_key,
                base_backoff_seconds=settings.retry_queue_base_backoff_sec,
                max_backoff_seconds=settings.retry_queue_max_backoff_sec,
            )
        except Exception:
            return RetryQueue(
                store=InMemoryRetryQueueStore(),
                key=settings.retry_queue_key,
                base_backoff_seconds=settings.retry_queue_base_backoff_sec,
                max_backoff_seconds=settings.retry_queue_max_backoff_sec,
            )
    return RetryQueue(
        store=InMemoryRetryQueueStore(),
        key=settings.retry_queue_key,
        base_backoff_seconds=settings.retry_queue_base_backoff_sec,
        max_backoff_seconds=settings.retry_queue_max_backoff_sec,
    )


def _build_worker_lease(settings: RuntimeSettings, audit_repository: Any = None) -> WorkerLease:
    if settings.redis_dsn and probe_redis_driver().available:
        try:
            redis_session = build_redis_adapter(settings.redis_dsn).open_session()
            return WorkerLease(
                store=redis_session,
                audit_repository=audit_repository,
                owner_id=settings.worker_id,
                key=settings.worker_lease_key,
                ttl_seconds=settings.worker_lease_ttl_sec,
            )
        except Exception:
            return WorkerLease(
                store=InMemoryWorkerLeaseStore(),
                audit_repository=audit_repository,
                owner_id=settings.worker_id,
                key=settings.worker_lease_key,
                ttl_seconds=settings.worker_lease_ttl_sec,
            )
    return WorkerLease(
        store=InMemoryWorkerLeaseStore(),
        audit_repository=audit_repository,
        owner_id=settings.worker_id,
        key=settings.worker_lease_key,
        ttl_seconds=settings.worker_lease_ttl_sec,
    )
