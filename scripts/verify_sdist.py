from __future__ import annotations

from email.parser import Parser
from pathlib import Path
import tarfile


EXPECTED_FILES = {
    "README.md",
    "pyproject.toml",
    "src/vk_openclaw_service/main.py",
    "src/vk_openclaw_service/worker_main.py",
    "tests/unit/test_api_app.py",
}


def main() -> int:
    sdist_path = max(Path(".dist_verify").glob("*.tar.gz"))

    with tarfile.open(sdist_path, "r:gz") as archive:
        members = {member.name for member in archive.getmembers()}
        root_prefix = next(name.split("/", 1)[0] for name in members if name.endswith("/pyproject.toml") or name.endswith("pyproject.toml"))
        expected = {f"{root_prefix}/{path}" for path in EXPECTED_FILES}
        missing = sorted(expected - members)
        if missing:
            raise SystemExit(f"sdist missing expected files: {', '.join(missing)}")

        pkg_info_member = next(
            member for member in archive.getmembers() if member.name.endswith("/PKG-INFO")
        )
        pkg_info = archive.extractfile(pkg_info_member)
        if pkg_info is None:
            raise SystemExit("sdist PKG-INFO is unreadable")
        metadata = Parser().parsestr(pkg_info.read().decode("utf-8"))
        if metadata["Name"] != "vk-openclaw-service":
            raise SystemExit(f"unexpected sdist package name: {metadata['Name']}")
        if metadata["Version"] != "0.0.1":
            raise SystemExit(f"unexpected sdist version: {metadata['Version']}")

    print(f"Verified sdist: {sdist_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
