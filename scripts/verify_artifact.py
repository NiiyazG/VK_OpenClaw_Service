from __future__ import annotations

from email.parser import Parser
from pathlib import Path
import zipfile


EXPECTED_FILES = {
    "vk_openclaw_service/main.py",
    "vk_openclaw_service/worker_main.py",
    "vk_openclaw_service/api/routes/system.py",
}


def main() -> int:
    dist_dir = Path(".dist_verify")
    wheel_path = max(dist_dir.glob("*.whl"))

    with zipfile.ZipFile(wheel_path) as wheel:
        members = set(wheel.namelist())
        missing = sorted(EXPECTED_FILES - members)
        if missing:
            raise SystemExit(f"wheel missing expected files: {', '.join(missing)}")

        dist_info_prefix = next(
            name.rsplit("/", 1)[0]
            for name in members
            if name.endswith(".dist-info/METADATA")
        )

        metadata = Parser().parsestr(
            wheel.read(f"{dist_info_prefix}/METADATA").decode("utf-8")
        )
        if metadata["Name"] != "vk-openclaw-service":
            raise SystemExit(f"unexpected package name: {metadata['Name']}")
        if metadata["Version"] != "0.0.1":
            raise SystemExit(f"unexpected package version: {metadata['Version']}")
        if metadata["Requires-Python"] != ">=3.12":
            raise SystemExit(
                f"unexpected Requires-Python: {metadata['Requires-Python']}"
            )

        entry_points = wheel.read(f"{dist_info_prefix}/entry_points.txt").decode("utf-8")
        expected_entrypoint = "vk-openclaw-worker = vk_openclaw_service.worker_main:main"
        if expected_entrypoint not in entry_points:
            raise SystemExit("wheel entry_points.txt is missing vk-openclaw-worker")

    print(f"Verified wheel: {wheel_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
