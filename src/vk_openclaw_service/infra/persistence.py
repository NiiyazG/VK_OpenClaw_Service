"""Persistence selection and repository factories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vk_openclaw_service.core.settings import RuntimeSettings
from vk_openclaw_service.infra.postgres import (
    build_postgres_adapter,
    ensure_postgres_schema,
    probe_postgres_driver,
)
from vk_openclaw_service.infra.redis_adapter import build_redis_adapter, probe_redis_driver
from vk_openclaw_service.infra.repositories.postgres import (
    PostgresAuditRepository,
    PostgresCheckpointRepository,
    PostgresDeadLetterRepository,
    PostgresPairingRepository,
    PostgresSavedDeadLetterQueryRepository,
)
from vk_openclaw_service.infra.repositories.audit import FileAuditRepository, InMemoryAuditRepository
from vk_openclaw_service.infra.repositories.checkpoints import FileCheckpointRepository, InMemoryCheckpointRepository
from vk_openclaw_service.infra.repositories.dead_letters import FileDeadLetterRepository, InMemoryDeadLetterRepository
from vk_openclaw_service.infra.repositories.pairing import FilePairingRepository, InMemoryPairingRepository
from vk_openclaw_service.infra.repositories.saved_queries import (
    FileSavedDeadLetterQueryRepository,
    InMemorySavedDeadLetterQueryRepository,
)


@dataclass(frozen=True)
class StorageState:
    mode: str
    ready: bool
    reason: str | None
    fallback_mode: str | None = None


@dataclass(frozen=True)
class RepositoryBundle:
    pairing_repository: object
    checkpoint_repository: object
    audit_repository: object
    dead_letter_repository: object
    saved_query_repository: object
    storage: StorageState


def build_repository_bundle(settings: RuntimeSettings) -> RepositoryBundle:
    if settings.persistence_mode == "memory":
        return RepositoryBundle(
            pairing_repository=InMemoryPairingRepository(),
            checkpoint_repository=InMemoryCheckpointRepository(),
            audit_repository=InMemoryAuditRepository(),
            dead_letter_repository=InMemoryDeadLetterRepository(),
            saved_query_repository=InMemorySavedDeadLetterQueryRepository(),
            storage=StorageState(mode="memory", ready=True, reason=None),
        )

    if settings.persistence_mode == "database":
        if settings.database_dsn and settings.redis_dsn:
            postgres_state = probe_postgres_driver()
            redis_state = probe_redis_driver()
            state_dir = Path(settings.state_dir)
            if not postgres_state.available or not redis_state.available:
                reasons = [
                    state.reason
                    for state in (postgres_state, redis_state)
                    if state.reason is not None
                ]
                return RepositoryBundle(
                    pairing_repository=FilePairingRepository(state_dir / "pairing.json"),
                    checkpoint_repository=FileCheckpointRepository(state_dir / "checkpoints.json"),
                    audit_repository=FileAuditRepository(state_dir / "audit.json"),
                    dead_letter_repository=FileDeadLetterRepository(state_dir / "dead_letters.json"),
                    saved_query_repository=FileSavedDeadLetterQueryRepository(state_dir / "saved_queries.json"),
                    storage=StorageState(
                        mode="database",
                        ready=False,
                        reason="+".join(reasons),
                        fallback_mode="file",
                    ),
                )
            postgres_adapter = build_postgres_adapter(settings.database_dsn)
            build_redis_adapter(settings.redis_dsn)
            try:
                postgres_session = postgres_adapter.open_session()
            except Exception:
                return RepositoryBundle(
                    pairing_repository=FilePairingRepository(state_dir / "pairing.json"),
                    checkpoint_repository=FileCheckpointRepository(state_dir / "checkpoints.json"),
                    audit_repository=FileAuditRepository(state_dir / "audit.json"),
                    dead_letter_repository=FileDeadLetterRepository(state_dir / "dead_letters.json"),
                    saved_query_repository=FileSavedDeadLetterQueryRepository(state_dir / "saved_queries.json"),
                    storage=StorageState(
                        mode="database",
                        ready=False,
                        reason="database_connection_failed",
                        fallback_mode="file",
                    ),
                )
            try:
                if not postgres_session.ping():
                    raise RuntimeError("database_ping_failed")
            except Exception:
                return RepositoryBundle(
                    pairing_repository=FilePairingRepository(state_dir / "pairing.json"),
                    checkpoint_repository=FileCheckpointRepository(state_dir / "checkpoints.json"),
                    audit_repository=FileAuditRepository(state_dir / "audit.json"),
                    dead_letter_repository=FileDeadLetterRepository(state_dir / "dead_letters.json"),
                    saved_query_repository=FileSavedDeadLetterQueryRepository(state_dir / "saved_queries.json"),
                    storage=StorageState(
                        mode="database",
                        ready=False,
                        reason="database_ping_failed",
                        fallback_mode="file",
                    ),
                )
            try:
                ensure_postgres_schema(postgres_session)
            except Exception:
                return RepositoryBundle(
                    pairing_repository=FilePairingRepository(state_dir / "pairing.json"),
                    checkpoint_repository=FileCheckpointRepository(state_dir / "checkpoints.json"),
                    audit_repository=FileAuditRepository(state_dir / "audit.json"),
                    dead_letter_repository=FileDeadLetterRepository(state_dir / "dead_letters.json"),
                    saved_query_repository=FileSavedDeadLetterQueryRepository(state_dir / "saved_queries.json"),
                    storage=StorageState(
                        mode="database",
                        ready=False,
                        reason="database_schema_bootstrap_failed",
                        fallback_mode="file",
                    ),
                )
            return RepositoryBundle(
                pairing_repository=PostgresPairingRepository(postgres_session),
                checkpoint_repository=PostgresCheckpointRepository(postgres_session),
                audit_repository=PostgresAuditRepository(postgres_session),
                dead_letter_repository=PostgresDeadLetterRepository(postgres_session),
                saved_query_repository=PostgresSavedDeadLetterQueryRepository(postgres_session),
                storage=StorageState(
                    mode="database",
                    ready=True,
                    reason=None,
                ),
            )
        state_dir = Path(settings.state_dir)
        return RepositoryBundle(
            pairing_repository=FilePairingRepository(state_dir / "pairing.json"),
            checkpoint_repository=FileCheckpointRepository(state_dir / "checkpoints.json"),
            audit_repository=FileAuditRepository(state_dir / "audit.json"),
            dead_letter_repository=FileDeadLetterRepository(state_dir / "dead_letters.json"),
            saved_query_repository=FileSavedDeadLetterQueryRepository(state_dir / "saved_queries.json"),
            storage=StorageState(
                mode="database",
                ready=False,
                reason="missing_database_or_redis_dsn",
                fallback_mode="file",
            ),
        )

    state_dir = Path(settings.state_dir)
    return RepositoryBundle(
        pairing_repository=FilePairingRepository(state_dir / "pairing.json"),
        checkpoint_repository=FileCheckpointRepository(state_dir / "checkpoints.json"),
        audit_repository=FileAuditRepository(state_dir / "audit.json"),
        dead_letter_repository=FileDeadLetterRepository(state_dir / "dead_letters.json"),
        saved_query_repository=FileSavedDeadLetterQueryRepository(state_dir / "saved_queries.json"),
        storage=StorageState(mode="file", ready=True, reason=None),
    )
