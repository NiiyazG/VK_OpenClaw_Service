from __future__ import annotations

import hashlib
import json
import tomllib
import zipfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]

    bundle_name = f"vk-openclaw-service-{version}-rc-handoff"
    bundle_dir = root / ".release_bundle" / bundle_name
    zip_path = root / ".release_bundle" / f"{bundle_name}.zip"
    manifest_path = bundle_dir / "bundle_manifest.json"

    if not bundle_dir.exists():
        raise SystemExit(f"Missing bundle directory: {bundle_dir}")
    if not zip_path.exists():
        raise SystemExit(f"Missing bundle zip: {zip_path}")
    if not manifest_path.exists():
        raise SystemExit(f"Missing bundle manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("bundle_name") != bundle_name:
        raise SystemExit("Bundle manifest name mismatch")

    included_files = manifest.get("included_files", [])
    if not included_files:
        raise SystemExit("Bundle manifest has no included files")

    required_relatives = {
        "verify_reports/release_summary.json",
        "verify_reports/release_summary.md",
        "verify_reports/distribution_checksums.txt",
        "RELEASE_HANDOFF.md",
        f"dist/vk_openclaw_service-{version}.tar.gz",
        f"dist/vk_openclaw_service-{version}-py3-none-any.whl",
        "README.md",
        "CONTRIBUTING.md",
        "pyproject.toml",
        "docs/release_notes.md",
        "docs/release_checklist.md",
        "docs/verification_report.md",
        "docs/operations_runbook.md",
    }

    manifest_relatives: set[str] = set()
    for item in included_files:
        path = Path(item["path"])
        rel = path.relative_to(bundle_dir).as_posix()
        manifest_relatives.add(rel)
        if not path.exists():
            raise SystemExit(f"Manifest file missing on disk: {path}")
        actual_hash = sha256_file(path)
        if actual_hash != item["sha256"]:
            raise SystemExit(f"Checksum mismatch for {path}")
        if path.stat().st_size != item["size_bytes"]:
            raise SystemExit(f"Size mismatch for {path}")

    missing_required = sorted(required_relatives - manifest_relatives)
    if missing_required:
        raise SystemExit(f"Bundle missing required files: {missing_required}")

    with zipfile.ZipFile(zip_path) as archive:
        zip_names = {name for name in archive.namelist() if not name.endswith("/")}
    required_zip_names = {f"{bundle_name}/{rel}" for rel in manifest_relatives}
    missing_zip = sorted(required_zip_names - zip_names)
    if missing_zip:
        raise SystemExit(f"Zip missing manifest-declared files: {missing_zip}")

    print(f"Verified release bundle: {zip_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
