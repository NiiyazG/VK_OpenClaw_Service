from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-path", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    reports_dir = args.output_dir or (root / ".verify_reports")
    summary_path = args.summary_path or (reports_dir / "release_summary.json")
    manifest_path = reports_dir / "release_manifest.json"
    manifest_markdown_path = reports_dir / "release_manifest.md"

    if not summary_path.exists():
        raise SystemExit(f"Missing verification summary: {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))

    release_manifest = {
        "generated_at_utc": summary["generated_at_utc"],
        "status": summary["status"],
        "full_suite": summary["full_suite"],
        "pip_audit_enabled": summary["pip_audit_enabled"],
        "remaining_external_gap": summary["remaining_external_gap"],
        "dist_artifacts": summary["artifacts"],
        "handoff_bundle": {
            "path": summary.get("handoff_bundle_zip", ""),
            "sha256": summary.get("handoff_bundle_sha256", ""),
            "size_bytes": summary.get("handoff_bundle_size_bytes", 0),
        },
        "verification_steps": summary["steps"],
    }
    manifest_path.write_text(json.dumps(release_manifest, indent=2), encoding="utf-8")

    lines = [
        "# Release Manifest",
        "",
        f"- Status: {release_manifest['status']}",
        f"- Full suite: {release_manifest['full_suite']}",
        f"- Pip audit enabled: {release_manifest['pip_audit_enabled']}",
        f"- Remaining external gap: {release_manifest['remaining_external_gap']}",
        "",
        "## Distribution Artifacts",
    ]
    for artifact in release_manifest["dist_artifacts"]:
        lines.append(
            f"- {artifact['name']}: sha256={artifact['sha256']}, size={artifact['size_bytes']} bytes"
        )
    lines.extend(
        [
            "",
            "## Handoff Bundle",
            f"- path: {release_manifest['handoff_bundle']['path']}",
            f"- sha256: {release_manifest['handoff_bundle']['sha256']}",
            f"- size: {release_manifest['handoff_bundle']['size_bytes']} bytes",
            "",
            "## Verification Steps",
        ]
    )
    for step in release_manifest["verification_steps"]:
        lines.append(f"- {step['name']}: {step['status']}")
    manifest_markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(manifest_path)
    print(manifest_markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
