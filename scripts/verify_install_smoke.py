from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import zipfile
import subprocess


def main() -> int:
    root = Path.cwd()
    wheel_path = max((root / ".dist_verify").glob("*.whl"))
    install_root = root / ".install_verify"
    temp_root = root / ".build_tmp" / "install_smoke"

    shutil.rmtree(install_root, ignore_errors=True)
    shutil.rmtree(temp_root, ignore_errors=True)
    install_root.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["TMP"] = str(temp_root)
    env["TEMP"] = str(temp_root)

    with zipfile.ZipFile(wheel_path) as wheel:
        wheel.extractall(install_root)

    package_root = install_root / "vk_openclaw_service"
    if not package_root.exists():
        raise SystemExit("installed target is missing vk_openclaw_service")
    if not (package_root / "worker_main.py").exists():
        raise SystemExit("installed target is missing worker_main.py")

    dist_info_dirs = list(install_root.glob("*.dist-info"))
    if not dist_info_dirs:
        raise SystemExit("installed target is missing dist-info metadata")
    entry_points = dist_info_dirs[0] / "entry_points.txt"
    if not entry_points.exists():
        raise SystemExit("installed target is missing entry_points.txt")
    if "vk-openclaw-worker = vk_openclaw_service.worker_main:main" not in entry_points.read_text(encoding="utf-8"):
        raise SystemExit("installed target is missing vk-openclaw-worker entrypoint")

    import_env = env.copy()
    import_env["PYTHONPATH"] = str(install_root)
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import vk_openclaw_service, vk_openclaw_service.worker_main; print(vk_openclaw_service.__file__)",
        ],
        check=True,
        env=import_env,
    )

    print(f"Extracted wheel smoke check passed: {wheel_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
