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
    build_dir = root / ".build_tmp" / "pyinstaller"
    out_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    if platform.system() != "Linux":
        print("Skipping one-file build: Linux required (run inside WSL Ubuntu).")
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
            "vk-openclaw",
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

    binary_path = out_dir / "vk-openclaw"
    if not binary_path.exists():
        raise SystemExit(f"Expected binary not found: {binary_path}")

    checksum = sha256_file(binary_path)
    checksum_path = out_dir / "vk-openclaw.sha256"
    checksum_path.write_text(f"{checksum}  vk-openclaw\n", encoding="utf-8")

    guide_src = root / "docs" / "wsl_onefile_install.md"
    guide_dest = out_dir / "vk-openclaw-install-guide.md"
    if guide_src.exists():
        shutil.copy2(guide_src, guide_dest)

    print(binary_path)
    print(checksum_path)
    if guide_dest.exists():
        print(guide_dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

