from __future__ import annotations

import hashlib
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / ".dist_verify"
    build_dir = root / ".build_tmp" / "pyinstaller_windows"
    out_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    if platform.system() != "Windows":
        print("Skipping one-file build: Windows required.")
        return 0

    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise SystemExit("PyInstaller is not installed. Install with: python -m pip install .[build]") from exc

    entry_script = root / "scripts" / "vk_openclaw_entry.py"
    if not entry_script.exists():
        raise SystemExit(f"Missing entry script: {entry_script}")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--name",
            "vk-openclaw-setup",
            "--distpath",
            str(out_dir),
            "--workpath",
            str(build_dir / "work"),
            "--specpath",
            str(build_dir / "spec"),
            "--paths",
            str(root / "src"),
            str(entry_script),
        ],
        check=True,
        cwd=root,
    )

    binary_path = out_dir / "vk-openclaw-setup.exe"
    if not binary_path.exists():
        raise SystemExit(f"Expected binary not found: {binary_path}")

    checksum = sha256_file(binary_path)
    checksum_path = out_dir / "vk-openclaw-setup.exe.sha256"
    checksum_path.write_text(f"{checksum}  vk-openclaw-setup.exe\n", encoding="utf-8")

    win_setup_script = root / "scripts" / "setup_windows.ps1"
    win_setup_dest = out_dir / "setup_windows.ps1"
    if win_setup_script.exists():
        shutil.copy2(win_setup_script, win_setup_dest)

    print(binary_path)
    print(checksum_path)
    if win_setup_dest.exists():
        print(win_setup_dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
