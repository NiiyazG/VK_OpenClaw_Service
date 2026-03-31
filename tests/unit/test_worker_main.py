import json
from vk_openclaw_service.core.settings import RuntimeSettings
from unittest.mock import patch

from vk_openclaw_service.worker_main import main, run_worker_loop


class FakeRuntimeService:
    def __init__(self, results: list[int | Exception]) -> None:
        self.results = results
        self.calls = 0

    def poll_once(self, heartbeat=None) -> int:
        if heartbeat is not None:
            heartbeat()
        result = self.results[self.calls]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return result


class FakeRetryDrainer:
    def __init__(self, results: list[int]) -> None:
        self.results = results
        self.calls = 0

    def drain_once(self, *, limit: int = 50) -> int:
        del limit
        result = self.results[self.calls]
        self.calls += 1
        return result


class FakeWorkerLease:
    def __init__(self, acquisitions: list[bool], refreshes: list[bool] | None = None) -> None:
        self.acquisitions = acquisitions
        self.refreshes = refreshes or [True for _ in acquisitions]
        self.acquire_calls = 0
        self.refresh_calls = 0
        self.release_calls = 0

    def acquire(self) -> str | None:
        acquired = self.acquisitions[self.acquire_calls]
        self.acquire_calls += 1
        if not acquired:
            return None
        return f"token-{self.acquire_calls}"

    def refresh(self, token: str) -> bool:
        del token
        result = self.refreshes[self.refresh_calls]
        self.refresh_calls += 1
        return result

    def release(self, token: str) -> None:
        del token
        self.release_calls += 1


class FakeLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)


def test_run_worker_loop_processes_single_iteration_without_sleep() -> None:
    runtime_service = FakeRuntimeService([2])
    retry_drainer = FakeRetryDrainer([1])
    sleep_calls: list[float] = []
    logger = FakeLogger()

    processed = run_worker_loop(
        runtime_service,
        retry_drainer=retry_drainer,
        iterations=1,
        interval_seconds=5.0,
        sleeper=sleep_calls.append,
        logger=logger,
    )

    assert processed == 3
    assert runtime_service.calls == 1
    assert retry_drainer.calls == 1
    assert sleep_calls == []
    events = [json.loads(message)["event"] for message in logger.messages]
    assert events == ["worker_loop_started", "worker_poll_succeeded", "worker_loop_completed"]


def test_run_worker_loop_sleeps_between_iterations() -> None:
    runtime_service = FakeRuntimeService([1, 3])
    retry_drainer = FakeRetryDrainer([0, 0])
    sleep_calls: list[float] = []

    processed = run_worker_loop(
        runtime_service,
        retry_drainer=retry_drainer,
        iterations=2,
        interval_seconds=2.5,
        sleeper=sleep_calls.append,
    )

    assert processed == 4
    assert runtime_service.calls == 2
    assert sleep_calls == [2.5]


def test_run_worker_loop_skips_iteration_when_lease_not_acquired() -> None:
    runtime_service = FakeRuntimeService([3])
    retry_drainer = FakeRetryDrainer([1])
    worker_lease = FakeWorkerLease([False])
    sleep_calls: list[float] = []
    logger = FakeLogger()

    processed = run_worker_loop(
        runtime_service,
        retry_drainer=retry_drainer,
        worker_lease=worker_lease,
        iterations=1,
        interval_seconds=2.5,
        sleeper=sleep_calls.append,
        logger=logger,
    )

    assert processed == 0
    assert runtime_service.calls == 0
    assert retry_drainer.calls == 0
    assert sleep_calls == []
    events = [json.loads(message)["event"] for message in logger.messages]
    assert events == ["worker_loop_started", "worker_poll_skipped_lease_not_acquired", "worker_loop_completed"]


def test_run_worker_loop_skips_poll_when_lease_is_lost_after_drain() -> None:
    runtime_service = FakeRuntimeService([3])
    retry_drainer = FakeRetryDrainer([1])
    worker_lease = FakeWorkerLease([True], refreshes=[False])
    sleep_calls: list[float] = []
    logger = FakeLogger()

    processed = run_worker_loop(
        runtime_service,
        retry_drainer=retry_drainer,
        worker_lease=worker_lease,
        iterations=1,
        interval_seconds=2.5,
        sleeper=sleep_calls.append,
        logger=logger,
    )

    assert processed == 0
    assert runtime_service.calls == 0
    assert retry_drainer.calls == 1
    assert worker_lease.refresh_calls == 1
    assert worker_lease.release_calls == 1
    assert sleep_calls == []
    events = [json.loads(message)["event"] for message in logger.messages]
    assert events == ["worker_loop_started", "worker_poll_skipped_lease_lost", "worker_loop_completed"]


def test_run_worker_loop_retries_with_backoff_on_retryable_failure() -> None:
    runtime_service = FakeRuntimeService([TimeoutError("timed out"), 3])
    retry_drainer = FakeRetryDrainer([0, 0])
    sleep_calls: list[float] = []
    logger = FakeLogger()

    processed = run_worker_loop(
        runtime_service,
        retry_drainer=retry_drainer,
        iterations=1,
        interval_seconds=5.0,
        retry_backoff_seconds=1.0,
        max_backoff_seconds=8.0,
        sleeper=sleep_calls.append,
        logger=logger,
    )

    assert processed == 3
    assert runtime_service.calls == 2
    assert sleep_calls == [1.0]
    events = [json.loads(message)["event"] for message in logger.messages]
    assert "worker_poll_retryable_failure" in events


def test_run_worker_loop_raises_on_non_retryable_failure() -> None:
    runtime_service = FakeRuntimeService([ValueError("bad payload")])
    retry_drainer = FakeRetryDrainer([0])
    logger = FakeLogger()

    try:
        run_worker_loop(runtime_service, retry_drainer=retry_drainer, iterations=1, logger=logger)
    except ValueError as exc:
        assert str(exc) == "bad payload"
    else:
        raise AssertionError("expected ValueError")
    events = [json.loads(message)["event"] for message in logger.messages]
    assert events[-1] == "worker_poll_failed"


def test_main_runs_single_iteration_with_once_flag() -> None:
    fake_runtime = FakeRuntimeService([4])
    fake_retry_drainer = FakeRetryDrainer([0])
    fake_worker_lease = FakeWorkerLease([True], refreshes=[True, True])

    with patch("vk_openclaw_service.worker_main.build_container") as build_container_mock:
        build_container_mock.return_value.vk_runtime_service = fake_runtime
        build_container_mock.return_value.retry_drainer = fake_retry_drainer
        build_container_mock.return_value.worker_lease = fake_worker_lease
        build_container_mock.return_value.settings = RuntimeSettings()
        with patch("vk_openclaw_service.worker_main.check_vk_token") as preflight_mock:
            preflight_mock.return_value.ok = True
            preflight_mock.return_value.message = ""
            exit_code = main(["--once", "--interval-seconds", "7"])

    assert exit_code == 0
    assert fake_runtime.calls == 1
    assert fake_retry_drainer.calls == 1
    assert fake_worker_lease.acquire_calls == 1
    assert fake_worker_lease.refresh_calls == 2


def test_main_uses_runtime_settings_for_worker_loop_defaults(runtime_settings_factory) -> None:
    fake_runtime = FakeRuntimeService([4])
    fake_retry_drainer = FakeRetryDrainer([0])
    fake_worker_lease = FakeWorkerLease([True])
    settings = runtime_settings_factory(
        worker_interval_sec=7.5,
        worker_retry_backoff_sec=1.5,
        worker_max_backoff_sec=25.0,
    )

    with patch("vk_openclaw_service.worker_main.build_container") as build_container_mock:
        build_container_mock.return_value.vk_runtime_service = fake_runtime
        build_container_mock.return_value.retry_drainer = fake_retry_drainer
        build_container_mock.return_value.worker_lease = fake_worker_lease
        build_container_mock.return_value.settings = settings
        with patch("vk_openclaw_service.worker_main.check_vk_token") as preflight_mock:
            preflight_mock.return_value.ok = True
            preflight_mock.return_value.message = ""
            with patch("vk_openclaw_service.worker_main.run_worker_loop", return_value=4) as run_worker_loop_mock:
                exit_code = main(["--once"])

    assert exit_code == 0
    run_worker_loop_mock.assert_called_once_with(
        fake_runtime,
        retry_drainer=fake_retry_drainer,
        worker_lease=fake_worker_lease,
        iterations=1,
        interval_seconds=7.5,
        retry_backoff_seconds=1.5,
        max_backoff_seconds=25.0,
    )


def test_main_fails_when_vk_token_preflight_fails() -> None:
    with patch("vk_openclaw_service.worker_main.check_vk_token") as preflight_mock:
        preflight_mock.return_value.ok = False
        preflight_mock.return_value.message = "bad token"
        try:
            main(["--once"])
        except SystemExit as exc:
            assert "Worker preflight failed" in str(exc)
        else:
            raise AssertionError("expected SystemExit")
