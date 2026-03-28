from __future__ import annotations

import json
import os
from pathlib import Path


def render_fallback(summary: dict) -> str:
    lines = [
        "# Release Verification Summary",
        "",
        f"- Status: {summary.get('status', 'unknown')}",
        f"- Full suite: {summary.get('full_suite', 'unknown')}",
        f"- Pip audit enabled: {summary.get('pip_audit_enabled', False)}",
        f"- Remaining external gap: {summary.get('remaining_external_gap', 'unknown')}",
        "",
        "## Steps",
    ]
    for step in summary.get("steps", []):
        line = f"- {step.get('name', 'unknown')}: {step.get('status', 'unknown')}"
        error = step.get("error")
        if error:
            line = f"{line} ({error})"
        lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    summary_path = root / ".verify_reports" / "release_summary.json"
    markdown_path = root / ".verify_reports" / "release_summary.md"
    github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")

    if not summary_path.exists():
        raise SystemExit(f"Missing summary file: {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    if markdown_path.exists():
        content = markdown_path.read_text(encoding="utf-8-sig")
    else:
        content = render_fallback(summary)

    if github_step_summary:
        Path(github_step_summary).write_text(content, encoding="utf-8")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
