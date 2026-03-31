from __future__ import annotations

from vk_openclaw_service import doctor
from vk_openclaw_service.core.settings import RuntimeSettings


def test_doctor_returns_non_zero_on_failures(monkeypatch) -> None:
    monkeypatch.setattr(doctor, "get_settings", lambda reload: RuntimeSettings(vk_access_token=""))
    monkeypatch.setattr(
        doctor,
        "check_env_local_exists",
        lambda: doctor.CheckResult(name="env.local", ok=False, message="missing"),
    )
    monkeypatch.setattr(
        doctor,
        "check_python_version",
        lambda *args: doctor.CheckResult(name="python_version", ok=True, message="ok"),
    )
    monkeypatch.setattr(
        doctor,
        "check_port_available",
        lambda *args: doctor.CheckResult(name="port", ok=True, message="ok"),
    )
    monkeypatch.setattr(
        doctor,
        "check_gateway_reachable",
        lambda *args: doctor.CheckResult(name="gateway", ok=True, message="ok"),
    )
    monkeypatch.setattr(
        doctor,
        "check_vk_token",
        lambda *args: doctor.CheckResult(name="vk_token", ok=False, message="bad"),
    )
    monkeypatch.setattr(
        doctor,
        "check_pairing_coverage",
        lambda *args: doctor.CheckResult(name="pairing", ok=True, message="ok"),
    )
    assert doctor.run_doctor() == 1
