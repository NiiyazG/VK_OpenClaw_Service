from __future__ import annotations

from logging.handlers import RotatingFileHandler

from vk_openclaw_service.core.logging import configure_logging
from vk_openclaw_service.core.settings import RuntimeSettings


def test_configure_logging_adds_rotating_file_handler(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("INVOCATION_ID", raising=False)
    monkeypatch.delenv("JOURNAL_STREAM", raising=False)
    settings = RuntimeSettings(state_dir=str(tmp_path / "state"), vk_access_token="token")
    logger = configure_logging(settings)
    assert any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers)
