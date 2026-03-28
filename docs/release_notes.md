# Release Notes: vk-openclaw-service v0.0.1

## Date
2026-03-17

## Included in This Release State
- FastAPI admin/runtime surface with:
  - `GET /api/v1/status`
  - `GET /api/v1/health`
  - `POST /api/v1/pairing/code`
  - `POST /api/v1/pairing/verify`
  - `POST /api/v1/config/validate`
  - `GET /api/v1/audit/events`
  - `GET /api/v1/audit/summary`
  - `GET /api/v1/audit/worker-lease`
  - `POST /api/v1/audit/worker-lease/reset`
  - `GET /api/v1/audit/dead-letters`
  - dead-letter presets, saved-query CRUD, preview, and execution routes
  - dead-letter single/bulk/query acknowledgment routes
- Worker runtime and separate worker entrypoint
- Unified runtime CLI (k-openclaw) with install/start/stop/status/run-api/run-worker
- WSL one-file build script via PyInstaller (scripts/build_onefile_linux.py)
- PostgreSQL readiness flow with driver probe, session open, ping, and schema bootstrap
- PostgreSQL-backed repositories for pairing, checkpoints, audit events, dead letters, and saved dead-letter queries
- Redis-backed coordination for:
  - rate limiting
  - replay protection
  - retry queue storage
  - retry draining
  - worker lease coordination
- Delayed/backoff-aware retry scheduling with retry budget and dead-letter fallback
- Worker lease renewal, heartbeat checks, stale takeover handling, reset controls, and audit trail
- Dead-letter operator workflows with:
  - persisted priority
  - derived severity
  - time-window filters
  - named presets
  - persistence-backed saved queries
  - operator attribution
  - status/audit summaries

## Verification State
- Dynamic verification during the latest session: full `pytest` green via `powershell -ExecutionPolicy Bypass -File scripts/run_pytest_safe.ps1 -q`
- Static verification during the latest session: repeated `python -m compileall` passes on changed source and test files
- Packaging verification during the latest session: local wheel build green via `powershell -ExecutionPolicy Bypass -File scripts/build_package_safe.ps1`
- Source-distribution verification during the latest session: local sdist build green via `powershell -ExecutionPolicy Bypass -File scripts/build_sdist_safe.ps1`
- Artifact smoke verification during the latest session: `python scripts/verify_artifact.py` confirmed wheel metadata and the `vk-openclaw-worker` console entrypoint
- Source-distribution smoke verification during the latest session: `python scripts/verify_sdist.py` confirmed `pyproject`, `README`, runtime sources, and tests are present in the tarball
- Source-distribution rebuild smoke during the latest session: `python scripts/verify_sdist_rebuild.py` rebuilt a wheel from the extracted source tarball
- Install smoke verification during the latest session: `python scripts/verify_install_smoke.py` confirmed isolated wheel extract and import behavior
- Release handoff bundle generation during the latest session: `python scripts/build_release_bundle.py` assembled verification reports, distribution artifacts, release docs, and a bundle manifest into a zipped handoff package
- Release handoff bundle verification during the latest session: `python scripts/verify_release_bundle.py` confirmed the bundle manifest, checksums, and zipped contents
- Release manifest generation during the latest session: `python scripts/generate_release_manifest.py` assembled dist artifact metadata, handoff bundle metadata, and gate status into machine-readable and markdown handoff files
- Release manifest verification during the latest session: `python scripts/verify_release_manifest.py` confirmed the manifest stays aligned with the current release summary and markdown handoff view
- A combined release verification helper now exists at `scripts/verify_release.ps1`
- A CI workflow now exists at `.github/workflows/ci.yml` to mirror the local verification gate on GitHub Actions and upload verification/distribution/bundle artifacts
- A repo-local package build helper now exists at `scripts/build_package_safe.ps1`
- A dedicated contributor guide and release checklist now exist at `CONTRIBUTING.md` and `docs/release_checklist.md`
- An operator runbook now exists at `docs/operations_runbook.md`
- A repo-local helper now exists at `scripts/verify_static.ps1` for repeatable static verification passes
- Latest helper baseline in this environment: `ruff` PASS, `mypy` PASS, `bandit` PASS, `pip-audit` PASS, wheel build PASS, sdist build PASS, wheel metadata PASS, sdist metadata PASS, sdist rebuild PASS, install smoke PASS
- Latest confirmed full suite: `205 passed`
- Latest unified gate: `RUN_PIP_AUDIT=1 powershell -ExecutionPolicy Bypass -File scripts/verify_release.ps1 -q` PASS

## Known Gaps
- Database mode still intentionally degrades to fallback behavior when live PostgreSQL or Redis readiness fails

## Recommended Next Iteration
1. Decide whether any remaining observability metadata justifies durable storage, or freeze the surface and prepare a release candidate.
2. If the surface is frozen, publish the verified v0.0.1 release artifacts and handoff bundle.


