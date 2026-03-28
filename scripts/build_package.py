from __future__ import annotations

import importlib
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4


class _SandboxTemporaryDirectory:
    def __init__(self, suffix: str | None = None, prefix: str | None = None, dir: str | None = None):
        self._root = Path(dir or tempfile.gettempdir())
        self._prefix = prefix or "tmp"
        self._suffix = suffix or ""
        self.name = str(self._root / f"{self._prefix}{uuid4().hex}{self._suffix}")

    def __enter__(self) -> str:
        Path(self.name).mkdir(parents=True, exist_ok=False)
        return self.name

    def __exit__(self, exc_type, exc, tb) -> bool:
        # Sandbox cleanup on Windows temp dirs is unreliable here; leaving the
        # short-lived build directory behind is preferable to failing the build.
        return False


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    build_root = root / ".build_tmp"
    dist_root = root / ".dist_verify"

    build_root.mkdir(parents=True, exist_ok=True)
    dist_root.mkdir(parents=True, exist_ok=True)
    for tmp_dir in dist_root.glob(".tmp-*"):
        shutil.rmtree(tmp_dir, ignore_errors=True)

    os.chdir(root)
    os.environ["TMP"] = str(build_root)
    os.environ["TEMP"] = str(build_root)
    tempfile.TemporaryDirectory = _SandboxTemporaryDirectory  # type: ignore[assignment]

    backend = importlib.import_module("setuptools.build_meta")
    wheel_name = backend.build_wheel(str(dist_root))
    for tmp_dir in dist_root.glob(".tmp-*"):
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"Built wheel: {dist_root / wheel_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
