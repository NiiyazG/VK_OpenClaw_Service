from __future__ import annotations

import importlib
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
from uuid import uuid4


class _SandboxTemporaryDirectory:
    def __init__(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
    ) -> None:
        self._root = Path(dir or tempfile.gettempdir())
        self._prefix = prefix or "tmp"
        self._suffix = suffix or ""
        self.name = str(self._root / f"{self._prefix}{uuid4().hex}{self._suffix}")

    def __enter__(self) -> str:
        Path(self.name).mkdir(parents=True, exist_ok=False)
        return self.name

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def main() -> int:
    root = Path.cwd()
    sdist_path = max((root / ".dist_verify").glob("*.tar.gz"))
    verify_root = root / ".sdist_verify_runs" / uuid4().hex
    extract_root = verify_root / "src"
    rebuild_dist = verify_root / "dist"
    temp_root = root / ".build_tmp" / "sdist_rebuild"

    shutil.rmtree(temp_root, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)
    rebuild_dist.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    with tarfile.open(sdist_path, "r:gz") as archive:
        for member in archive.getmembers():
            target = extract_root / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise SystemExit(f"unable to read sdist member: {member.name}")
            with source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)

    project_root = next(path for path in extract_root.iterdir() if path.is_dir())

    os.environ["TMP"] = str(temp_root)
    os.environ["TEMP"] = str(temp_root)
    tempfile.TemporaryDirectory = _SandboxTemporaryDirectory  # type: ignore[assignment]

    previous_cwd = Path.cwd()
    os.chdir(project_root)
    try:
        backend = importlib.import_module("setuptools.build_meta")
        wheel_name = backend.build_wheel(str(rebuild_dist))
    finally:
        os.chdir(previous_cwd)

    wheel_path = rebuild_dist / wheel_name
    if not wheel_path.exists():
        raise SystemExit(f"rebuilt wheel missing: {wheel_path}")

    print(f"Rebuilt wheel from sdist: {wheel_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
