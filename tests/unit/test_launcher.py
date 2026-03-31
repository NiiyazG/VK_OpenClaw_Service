from __future__ import annotations

from pathlib import Path

from vk_openclaw_service.core.settings import RuntimeSettings
from vk_openclaw_service import launcher


def test_build_launch_paths_uses_state_dir() -> None:
    settings = RuntimeSettings(state_dir="./state-custom")
    paths = launcher.build_launch_paths(settings)
    assert paths.api_pid == Path("./state-custom/api.pid")
    assert paths.worker_pid == Path("./state-custom/worker.pid")
    assert paths.log_file == Path("./state-custom/vk-openclaw.log")


def test_start_all_waits_for_gateway_when_requested(monkeypatch, tmp_path: Path) -> None:
    settings = RuntimeSettings(state_dir=str(tmp_path / "state"), vk_access_token="token")
    monkeypatch.setattr(launcher, "wait_for_gateway", lambda **kwargs: type("R", (), {"ok": True, "message": "ok"})())

    class DummyProc:
        def __init__(self, pid: int) -> None:
            self.pid = pid

    pids = iter([111, 222])
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: DummyProc(next(pids)))
    call = {"count": 0}

    def fake_status(_settings):
        call["count"] += 1
        if call["count"] == 1:
            return {"api_running": False, "worker_running": False}
        return {
            "api_running": True,
            "worker_running": True,
            "api_pid": 111,
            "worker_pid": 222,
            "log_file": str(tmp_path / "state" / "vk-openclaw.log"),
        }

    monkeypatch.setattr(
        launcher,
        "status_all",
        fake_status,
    )
    ok, message = launcher.start_all(settings, wait_for_gateway_enabled=True)
    assert ok is True
    assert "Started" in message


def test_stop_all_handles_missing_pid_files(tmp_path: Path) -> None:
    settings = RuntimeSettings(state_dir=str(tmp_path / "state"), vk_access_token="token")
    ok, _ = launcher.stop_all(settings)
    assert ok is True
