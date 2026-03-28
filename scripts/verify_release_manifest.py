from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    reports_dir = root / ".verify_reports"
    summary_path = reports_dir / "release_summary.json"
    manifest_path = reports_dir / "release_manifest.json"
    manifest_markdown_path = reports_dir / "release_manifest.md"

    if not summary_path.exists():
        raise SystemExit(f"Missing release summary: {summary_path}")
    if not manifest_path.exists():
        raise SystemExit(f"Missing release manifest: {manifest_path}")
    if not manifest_markdown_path.exists():
        raise SystemExit(f"Missing release manifest markdown: {manifest_markdown_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("status") != summary.get("status"):
        raise SystemExit("Manifest status does not match release summary")
    if manifest.get("full_suite") != summary.get("full_suite"):
        raise SystemExit("Manifest full_suite does not match release summary")
    if manifest.get("remaining_external_gap") != summary.get("remaining_external_gap"):
        raise SystemExit("Manifest external gap does not match release summary")
    if manifest.get("dist_artifacts") != summary.get("artifacts"):
        raise SystemExit("Manifest dist_artifacts do not match release summary")

    handoff_bundle = manifest.get("handoff_bundle", {})
    if handoff_bundle.get("path") != summary.get("handoff_bundle_zip"):
        raise SystemExit("Manifest handoff bundle path does not match release summary")
    if handoff_bundle.get("sha256") != summary.get("handoff_bundle_sha256"):
        raise SystemExit("Manifest handoff bundle sha256 does not match release summary")
    if handoff_bundle.get("size_bytes") != summary.get("handoff_bundle_size_bytes"):
        raise SystemExit("Manifest handoff bundle size does not match release summary")

    markdown = manifest_markdown_path.read_text(encoding="utf-8")
    required_markdown_fragments = [
        "# Release Manifest",
        "## Distribution Artifacts",
        "## Handoff Bundle",
        "## Verification Steps",
    ]
    for fragment in required_markdown_fragments:
        if fragment not in markdown:
            raise SystemExit(f"Manifest markdown missing section: {fragment}")

    print(f"Verified release manifest: {manifest_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
