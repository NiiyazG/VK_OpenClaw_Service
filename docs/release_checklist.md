# Release Checklist

## Goal
Freeze and verify a release-candidate state for `vk-openclaw-service`.

## Required Gates
1. Run the combined local verification gate:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/verify_release.ps1 -q
   ```
2. Confirm the expected baseline:
   - `pytest`: `205 passed`
   - `compileall`: pass
   - `ruff`: pass
   - `mypy`: pass
   - `bandit`: pass
   - `scripts/build_package_safe.ps1`: pass
   - `scripts/build_sdist_safe.ps1`: pass
   - `python scripts/verify_artifact.py`: pass
   - `python scripts/verify_sdist.py`: pass
   - `python scripts/verify_sdist_rebuild.py`: pass
   - `python scripts/verify_install_smoke.py`: pass
   - `python scripts/verify_release_bundle.py`: pass
   - `python scripts/generate_release_manifest.py --summary-path .verify_reports/release_summary.json --output-dir .verify_reports`: pass
   - `python scripts/verify_release_manifest.py`: pass
   - final `release_summary.json` and `release_manifest.json` step lists match, including `release-manifest` and `release-manifest-artifact`
3. Confirm docs are aligned:
   - `README.md`
   - `docs/progress.md`
   - `docs/context_summary.md`
   - `docs/verification_report.md`
   - `docs/release_notes.md`
   - `docs/operations_runbook.md`
4. Capture the generated gate snapshot:
   - `.verify_reports/release_summary.json`
   - `.verify_reports/release_summary.md`
   - `.verify_reports/distribution_checksums.txt`
   - `.verify_reports/release_manifest.json`
   - `.verify_reports/release_manifest.md`
   - `.release_bundle/`
5. Preserve CI handoff artifacts when applicable:
   - `verification-reports`
   - `distribution-artifacts`
   - `release-handoff-bundle`

## Optional Gate
1. Re-run `RUN_PIP_AUDIT=1` verification only when you need to refresh the online dependency-audit evidence.
2. Attach the refreshed result to the release decision if you regenerate the gate snapshot.

## Runtime Spot Checks
1. `GET /api/v1/status`
2. `GET /api/v1/health`
3. `GET /api/v1/audit/summary`
4. `GET /api/v1/audit/dead-letters`
5. `vk-openclaw-worker --once`
6. If `FREE_TEXT_ASK_ENABLED=true`, verify free-text handling after pairing and slash-command priority.
7. If `OPENCLAW_COMMAND=./openclaw_agent_wrapper.sh`, confirm wrapper exists and is executable.
8. `vk-openclaw setup --dry-run` renders redacted preview (no secret leakage).
9. Linux one-command path works: `./install.sh`.
10. Windows one-command path works: `powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1`.
11. Windows service prerequisites are present (`winsw.exe` path or `WINSW_PATH`).

## Release Decision
Mark the release as ready only when:
- the combined verification gate is green
- API/admin surface matches the documented runtime surface
- no unresolved critical regressions remain
- any remaining gaps are explicitly externalized, if any still exist for the target environment
- if free-text mode is enabled, canary/rollback thresholds are documented and monitored


