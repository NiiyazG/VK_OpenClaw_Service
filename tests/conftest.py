import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from _pytest import pathlib as pytest_pathlib
from _pytest import tmpdir as pytest_tmpdir

from vk_openclaw_service.core import settings as settings_module
from vk_openclaw_service.core.settings import RuntimeSettings


def pytest_configure():
    if os.environ.get("PYTEST_DISABLE_DEAD_SYMLINK_CLEANUP") != "1":
        return

    def _noop_cleanup_dead_symlinks(_root):
        return None

    pytest_pathlib.cleanup_dead_symlinks = _noop_cleanup_dead_symlinks
    pytest_tmpdir.cleanup_dead_symlinks = _noop_cleanup_dead_symlinks


@pytest.fixture
def tmp_path(tmp_path_factory):
    if os.environ.get("PYTEST_DISABLE_DEAD_SYMLINK_CLEANUP") != "1":
        yield tmp_path_factory.mktemp("pytest-local")
        return

    root = Path.cwd() / ".pytest_local_tmp"
    root.mkdir(exist_ok=True)
    path = root / f"pytest-local-{uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolated_runtime_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings_module,
        "_settings",
        RuntimeSettings(state_dir=str(tmp_path / "state"), persistence_mode="memory"),
    )


@pytest.fixture
def runtime_settings_factory(tmp_path):
    def factory(**kwargs):
        defaults = {
            "state_dir": str(tmp_path / "state"),
            "persistence_mode": "memory",
        }
        defaults.update(kwargs)
        return RuntimeSettings(**defaults)

    return factory
