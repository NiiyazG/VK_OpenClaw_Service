from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(src: Path, dest: Path) -> dict[str, object]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return {
        "source": str(src),
        "path": str(dest),
        "size_bytes": dest.stat().st_size,
        "sha256": sha256_file(dest),
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]

    summary_path = root / ".verify_reports" / "release_summary.json"
    reports_dir = root / ".verify_reports"
    dist_dir = root / ".dist_verify"
    bundle_root = root / ".release_bundle"
    bundle_name = f"vk-openclaw-service-{version}-rc-handoff"
    bundle_dir = bundle_root / bundle_name
    zip_path = bundle_root / f"{bundle_name}.zip"

    if not summary_path.exists():
        raise SystemExit(f"Missing verification summary: {summary_path}")

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    if zip_path.exists():
        zip_path.unlink()

    (bundle_dir / "verify_reports").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "dist").mkdir(parents=True, exist_ok=True)

    included_files: list[dict[str, object]] = []

    for path in sorted(reports_dir.glob("*")):
        if path.is_file():
            included_files.append(
                copy_file(path, bundle_dir / "verify_reports" / path.name)
            )

    for path in sorted(dist_dir.glob("*")):
        if path.is_file():
            included_files.append(copy_file(path, bundle_dir / "dist" / path.name))

    for relative in [
        Path("README.md"),
        Path("CONTRIBUTING.md"),
        Path("pyproject.toml"),
        Path("docs/release_notes.md"),
        Path("docs/release_checklist.md"),
        Path("docs/verification_report.md"),
        Path("docs/operations_runbook.md"),
        Path("docs/wsl_onefile_install.md"),
    ]:
        src = root / relative
        included_files.append(copy_file(src, bundle_dir / relative))

    manifest = {
        "bundle_name": bundle_name,
        "bundle_dir": str(bundle_dir),
        "zip_path": str(zip_path),
        "version": version,
        "included_files": included_files,
    }
    manifest_path = bundle_dir / "bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    primary_files = [
        "- `verify_reports/release_summary.json`",
        "- `verify_reports/release_summary.md`",
        "- `verify_reports/distribution_checksums.txt`",
        f"- `dist/vk_openclaw_service-{version}-py3-none-any.whl`",
        f"- `dist/vk_openclaw_service-{version}.tar.gz`",
    ]

    if (dist_dir / "vk-openclaw").exists():
        primary_files.append("- `dist/vk-openclaw` (Linux one-file binary)")
    if (dist_dir / "vk-openclaw.sha256").exists():
        primary_files.append("- `dist/vk-openclaw.sha256`")
    if (dist_dir / "vk-openclaw-install-guide.md").exists():
        primary_files.append("- `dist/vk-openclaw-install-guide.md`")

    handoff_lines = [
        "# Release Handoff Bundle",
        "",
        f"- Bundle: `{bundle_name}`",
        f"- Version: `{version}`",
        f"- Manifest: `{manifest_path.name}`",
        "",
        "## Included Groups",
        "- `verify_reports/`: JSON summary, markdown summary, distribution checksums",
        "- `dist/`: wheel, source distribution, and optional Linux one-file artifacts",
        "- `docs/`: release notes, checklist, verification report, operations runbook, WSL one-file guide",
        "- root docs: `README.md`, `CONTRIBUTING.md`, `pyproject.toml`",
        "",
        "## Primary Files",
        *primary_files,
        "",
        "## Verification Status",
        "- Built from the latest local release gate output",
        "- Intended for RC handoff and offline review",
    ]
    handoff_path = bundle_dir / "RELEASE_HANDOFF.md"
    handoff_path.write_text(
        "\n".join(handoff_lines) + "\n",
        encoding="utf-8",
    )
    included_files.append(
        {
            "source": str(handoff_path),
            "path": str(handoff_path),
            "size_bytes": handoff_path.stat().st_size,
            "sha256": sha256_file(handoff_path),
        }
    )
    manifest["included_files"] = included_files
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    archive_base = bundle_root / bundle_name
    shutil.make_archive(
        str(archive_base),
        "zip",
        root_dir=bundle_root,
        base_dir=bundle_name,
    )

    print(bundle_dir)
    print(zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

