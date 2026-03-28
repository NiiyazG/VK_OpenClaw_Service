from vk_openclaw_service.services.worker_lease import (
    InMemoryWorkerLeaseStore,
    WorkerLease,
    WorkerLeaseRecord,
)
from vk_openclaw_service.infra.repositories.audit import InMemoryAuditRepository


def test_worker_lease_runs_callback_when_acquired() -> None:
    lease = WorkerLease(store=InMemoryWorkerLeaseStore(), owner_id="worker-a", key="worker", ttl_seconds=15)

    acquired, result = lease.run(lambda: 7)

    assert acquired is True
    assert result == 7


def test_worker_lease_refreshes_owned_claim() -> None:
    ticks = iter([100.0, 105.0])
    lease = WorkerLease(
        store=InMemoryWorkerLeaseStore(now=lambda: next(ticks)),
        owner_id="worker-a",
        key="worker",
        ttl_seconds=15,
    )

    token = lease.acquire()

    assert token is not None
    assert lease.refresh(token) is True
    assert lease.snapshot()["owner_id"] == "worker-a"
    assert lease.snapshot()["held_by_self"] is True
    assert lease.snapshot()["acquired_at"] == 100.0
    assert lease.snapshot()["refreshed_at"] == 105.0
    assert lease.snapshot()["previous_owner_id"] is None
    assert lease.snapshot()["takeover_at"] is None
    assert lease.snapshot()["takeover_count"] == 0
    lease.release(token)


def test_worker_lease_skips_callback_when_already_claimed() -> None:
    store = InMemoryWorkerLeaseStore(
        claims={"worker": WorkerLeaseRecord(token="other-token", owner_id="worker-b")}
    )
    lease = WorkerLease(store=store, owner_id="worker-a", key="worker", ttl_seconds=15)

    called = False

    def callback() -> int:
        nonlocal called
        called = True
        return 7

    acquired, result = lease.run(callback)

    assert acquired is False
    assert result is None
    assert called is False
    assert lease.snapshot()["owner_id"] == "worker-b"
    assert lease.snapshot()["held_by_self"] is False


def test_worker_lease_takes_over_stale_claim() -> None:
    ticks = iter([120.0, 120.0, 120.0])
    store = InMemoryWorkerLeaseStore(
        claims={
            "worker": WorkerLeaseRecord(
                token="other-token",
                owner_id="worker-b",
                acquired_at=100.0,
                refreshed_at=100.0,
            )
        },
        now=lambda: next(ticks),
    )
    lease = WorkerLease(
        store=store,
        owner_id="worker-a",
        key="worker",
        ttl_seconds=15,
        now=lambda: 120.0,
    )

    token = lease.acquire()

    assert token is not None
    assert lease.snapshot()["owner_id"] == "worker-a"
    assert lease.snapshot()["held_by_self"] is True
    assert lease.snapshot()["stale"] is False
    assert lease.snapshot()["previous_owner_id"] == "worker-b"
    assert lease.snapshot()["takeover_at"] == 120.0
    assert lease.snapshot()["takeover_count"] == 1


def test_worker_lease_appends_audit_event_on_stale_takeover() -> None:
    audit_repository = InMemoryAuditRepository()
    store = InMemoryWorkerLeaseStore(
        claims={
            "worker": WorkerLeaseRecord(
                token="other-token",
                owner_id="worker-b",
                acquired_at=100.0,
                refreshed_at=100.0,
            )
        },
        now=lambda: 120.0,
    )
    lease = WorkerLease(
        store=store,
        audit_repository=audit_repository,
        owner_id="worker-a",
        key="worker",
        ttl_seconds=15,
        now=lambda: 120.0,
    )

    token = lease.acquire()

    assert token is not None
    assert audit_repository.events[-1]["event_type"] == "worker_lease_taken_over"
    assert audit_repository.events[-1]["details"] == {
        "lease_key": "worker",
        "previous_owner_id": "worker-b",
        "owner_id": "worker-a",
        "requested_by": "worker:worker-a",
        "trigger": "automatic_stale_takeover",
        "stale_for_seconds": 20.0,
        "ttl_seconds": 15,
    }


def test_worker_lease_does_not_append_audit_event_without_stale_handoff() -> None:
    audit_repository = InMemoryAuditRepository()
    lease = WorkerLease(
        store=InMemoryWorkerLeaseStore(now=lambda: 100.0),
        audit_repository=audit_repository,
        owner_id="worker-a",
        key="worker",
        ttl_seconds=15,
        now=lambda: 100.0,
    )

    token = lease.acquire()

    assert token is not None
    assert audit_repository.events[-1]["event_type"] != "worker_lease_taken_over"


def test_worker_lease_can_reset_only_stale_claims() -> None:
    audit_repository = InMemoryAuditRepository()
    store = InMemoryWorkerLeaseStore(
        claims={
            "worker": WorkerLeaseRecord(
                token="other-token",
                owner_id="worker-b",
                acquired_at=100.0,
                refreshed_at=100.0,
            )
        },
        now=lambda: 120.0,
    )
    lease = WorkerLease(
        store=store,
        audit_repository=audit_repository,
        owner_id="worker-a",
        key="worker",
        ttl_seconds=15,
        now=lambda: 120.0,
    )

    released = lease.reset_if_stale()

    assert released == {
        "lease_key": "worker",
        "owner_id": "worker-b",
        "acquired_at": 100.0,
        "refreshed_at": 100.0,
        "previous_owner_id": None,
        "takeover_at": None,
        "takeover_count": 0,
        "ttl_seconds": 15,
    }
    assert lease.snapshot()["held"] is False
    assert audit_repository.events[-1]["event_type"] == "worker_lease_reset"


def test_worker_lease_reset_returns_none_for_active_claim() -> None:
    store = InMemoryWorkerLeaseStore(
        claims={
            "worker": WorkerLeaseRecord(
                token="other-token",
                owner_id="worker-b",
                acquired_at=100.0,
                refreshed_at=110.0,
            )
        },
        now=lambda: 120.0,
    )
    lease = WorkerLease(
        store=store,
        audit_repository=InMemoryAuditRepository(),
        owner_id="worker-a",
        key="worker",
        ttl_seconds=15,
        now=lambda: 120.0,
    )

    assert lease.reset_if_stale() is None
