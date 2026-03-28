# vk-openclaw-service

VK Messenger to OpenClaw service being built through a role-driven workflow.

## Project Variables
- PROJECT_NAME: vk-openclaw-service
- TECH_STACK: python,fastapi,postgresql,redis
- VERSION: 0.0.1
- START_DATE: 2026-03-16

## Current Runtime Surface
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
- `GET /api/v1/audit/dead-letters/presets`
- `GET /api/v1/audit/dead-letters/saved`
- `GET /api/v1/audit/dead-letters/saved/{name}`
- `PUT /api/v1/audit/dead-letters/saved/{name}`
- `DELETE /api/v1/audit/dead-letters/saved/{name}`
- `GET /api/v1/audit/dead-letters/saved/{name}/items`
- `POST /api/v1/audit/dead-letters/saved/{name}/ack`
- `POST /api/v1/audit/dead-letters/ack-bulk`
- `POST /api/v1/audit/dead-letters/ack-query`
- `POST /api/v1/audit/dead-letters/{id}/ack`

## Current Implementation Status
- Architecture, review, and verification artifacts are present under `docs/`
- API/application skeleton is implemented and verified
- Domain logic, repositories, worker service, and container wiring are implemented
- File-backed state is enabled for pairing, checkpoints, and audit events via `STATE_DIR`
- Persistence mode selection is implemented with `file`, `memory`, and preflighted `database` modes
- `database` mode now probes PostgreSQL and Redis driver availability before adapter selection
- PostgreSQL-backed repository classes for pairing, checkpoints, and audit events are implemented and unit-tested against an adapter protocol
- `database` mode now switches to PostgreSQL-backed repositories when a session factory is available
- PostgreSQL readiness now includes `connect + ping + schema bootstrap`
- Redis-backed runtime rate limiting is implemented for costly OpenClaw command paths with safe in-memory fallback
- Redis-backed anti-replay protection is implemented for incoming `(peer_id, message_id)` processing with safe in-memory fallback
- Redis-backed retry queue support is implemented for `delivery_retry_required` worker outcomes with safe in-memory fallback
- Retry draining is integrated into the worker loop, so queued retry payloads are replayed before each normal polling pass
- Retry queue scheduling is delayed/backoff-aware via `attempt` and `available_at` payload fields
- Worker loop coordination now supports a short-lived lease so concurrent workers can skip duplicate drain/poll cycles
- Worker loop renews the lease between retry draining and polling so ownership stays explicit through the whole cycle
- VK polling now supports heartbeat-style lease checks between peers so a worker can stop mid-cycle if ownership is lost
- Worker lease snapshots now expose owner identity plus `acquired_at` and `refreshed_at` observability metadata
- Stale worker leases can now be explicitly taken over once the last observed heartbeat is older than the lease TTL
- Lease snapshots now also report `previous_owner_id`, `takeover_at`, and `takeover_count` so operator-facing status shows the last ownership handoff
- Stale-lease handoffs now append a dedicated `worker_lease_taken_over` audit event so ownership changes are visible in the audit feed
- Admin users can now inspect the live worker lease snapshot through a dedicated read-only audit endpoint
- Admin users can now inspect a compact audit summary with event/dead-letter/saved-query counts, saved-query names, recent event types, and unresolved dead-letter priority/reason breakdown through a dedicated read-only endpoint
- Admin users can now reset only stale worker leases through a guarded endpoint; successful resets append `worker_lease_reset` to the audit feed
- Mutating admin actions now accept optional `X-Operator-Id`; audit events for dead-letter ack and worker lease reset persist the operator identifier
- Dead-letter admin workflow now supports bulk acknowledgment with partial success reporting (`acknowledged`, `not_found`, `count`)
- Dead-letter read API now supports server-side filters by `acknowledged`, `reason`, and `peer_id`, and bulk ack can now target filtered matches via query payload
- Dead-letter filtering now also supports `created_after` and `created_before` so operators can target time windows
- Dead-letter filtering now also supports `acknowledged_after` and `acknowledged_before` for acknowledged-item time windows
- Dead-letter query presets are now exposed as named operator shortcuts and can be used in list and bulk-by-query flows
- Dead-letter read/query responses now derive `severity` (`normal`/`high`/`critical`) and support filtering/presets by severity
- Saved dead-letter queries are now persistence-backed and can be listed, stored, deleted, previewed, and executed through admin API routes
- Dead-letter records now persist an explicit `priority` field and admin query/saved-query flows can filter on it directly
- `database` mode now also switches saved dead-letter queries onto a PostgreSQL-backed repository once the external session is ready
- Automatic stale worker takeovers now record `requested_by=worker:<worker_id>` and `trigger=automatic_stale_takeover` in the audit feed
- Retryable message handling now has a configurable retry budget before dead-lettering and checkpoint commit
- Dead-letter persistence is now tracked in a dedicated repository/store in addition to audit events
- Dead-letter records can now be acknowledged through the admin API so status/health only reflect unresolved entries
- VK polling runtime and worker entrypoint are implemented
- Worker loop has structured JSON logging and configurable retry/backoff settings
- PostgreSQL and Redis integrations are implemented with readiness probes and safe fallback paths, and the current full-suite verification baseline is `205 passed`

## Environment
Supported runtime variables are listed in [.env.example](/c:/Users/User/Downloads/vk-openclaw-service/.env.example):
- `ADMIN_API_TOKEN`
- `VK_ACCESS_TOKEN`
- `VK_ALLOWED_PEERS`
- `PERSISTENCE_MODE`
- `DATABASE_DSN`
- `REDIS_DSN`
- `VK_MODE`
- `FREE_TEXT_ASK_ENABLED`
- `PAIR_CODE_TTL_SEC`
- `VK_RATE_LIMIT_PER_MIN`
- `VK_MAX_ATTACHMENTS`
- `VK_MAX_FILE_MB`
- `OPENCLAW_COMMAND`
- `OPENCLAW_TIMEOUT_SEC`
- `STATE_DIR`
- `WORKER_INTERVAL_SEC`
- `WORKER_RETRY_BACKOFF_SEC`
- `WORKER_MAX_BACKOFF_SEC`
- `WORKER_LEASE_TTL_SEC`
- `WORKER_LEASE_KEY`
- `RETRY_QUEUE_MAX_ATTEMPTS`
- `RETRY_QUEUE_BASE_BACKOFF_SEC`
- `RETRY_QUEUE_MAX_BACKOFF_SEC`
- `REPLAY_TTL_SEC`
- `RETRY_QUEUE_KEY`

Current recommended runtime command integration:
- `OPENCLAW_COMMAND=./openclaw_agent_wrapper.sh`
- `openclaw_agent_wrapper.sh` calls `openclaw agent --local --agent main --message "<text>"`
- in WSL, ensure executable bit: `chmod +x ./openclaw_agent_wrapper.sh`

## Local Development
Install dependencies:

```bash
python -m pip install -e .
```

Install the local verification toolchain when needed:

```bash
python -m pip install ruff mypy bandit pip-audit pytest
```

Build a local wheel artifact in a sandbox-safe temp layout:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_package_safe.ps1
```

Run unit tests:

```bash
pytest tests/unit
```

Run the full suite with an explicit writable pytest temp directory when needed:

```bash
pytest --basetemp=.pytest_tmp
```

There is also a repo-local helper for sandboxed Windows runs:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_pytest_safe.ps1 -q
```

It uses a unique `--basetemp` on every run, disables `cacheprovider`, and enables the repo-local sandbox compatibility shim in `tests/conftest.py`.

For a release-candidate style static pass without relying on full `pytest`, use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_static.ps1
```

It runs `compileall`, `ruff`, `mypy`, and `bandit` by default.
Set `RUN_PIP_AUDIT=1` to include the online dependency audit step when the environment has outbound access to `pypi.org`.

For a single release-style gate that runs both full `pytest` and static verification, use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_release.ps1 -q
```

That gate now verifies:
- full `pytest`
- `compileall`, `ruff`, `mypy`, `bandit`
- sandbox-safe wheel build via `scripts/build_package_safe.ps1`
- sandbox-safe source distribution build via `scripts/build_sdist_safe.ps1`
- wheel metadata and console entrypoint via `scripts/verify_artifact.py`
- source distribution contents via `scripts/verify_sdist.py`
- source distribution rebuild smoke via `scripts/verify_sdist_rebuild.py`
- wheel extract/import smoke via `scripts/verify_install_smoke.py`
- release handoff bundle creation via `scripts/build_release_bundle.py`
- release handoff bundle verification via `scripts/verify_release_bundle.py`
- release manifest verification via `scripts/verify_release_manifest.py`
- optional `pip-audit` when `RUN_PIP_AUDIT=1`

Each run also writes:
- machine-readable gate output to `.verify_reports/release_summary.json`
- human-readable handoff output to `.verify_reports/release_summary.md`
- artifact SHA-256 manifest to `.verify_reports/distribution_checksums.txt`
- release manifest to `.verify_reports/release_manifest.json`
- release manifest markdown to `.verify_reports/release_manifest.md`
- release handoff bundle under `.release_bundle/`

The summary now also records the handoff bundle zip path, size, and SHA-256 checksum.

A matching CI workflow is also present at `.github/workflows/ci.yml`.
CI now runs the same `scripts/verify_release.ps1` gate with `RUN_PIP_AUDIT=1`, publishes the markdown summary into the GitHub job summary, uploads `.verify_reports/*` as `verification-reports`, uploads the built `.dist_verify/*` artifacts as `distribution-artifacts`, and uploads `.release_bundle/*` as `release-handoff-bundle`.
Contributor guidance is in [CONTRIBUTING.md](/c:/Users/User/Downloads/vk-openclaw-service/CONTRIBUTING.md), the release checklist is in [docs/release_checklist.md](/c:/Users/User/Downloads/vk-openclaw-service/docs/release_checklist.md), and the operator runbook is in [docs/operations_runbook.md](/c:/Users/User/Downloads/vk-openclaw-service/docs/operations_runbook.md).

Validate runtime config via API:

`POST /api/v1/config/validate` now checks:
- required auth/OpenClaw fields
- `persistence_mode`
- `database_dsn` and `redis_dsn` when `persistence_mode=database`
- `free_text_ask_enabled` type when present (must be boolean)
- worker loop timing values
- worker lease timing values
- retry queue attempt budget
- retry queue backoff timing values

Run the API skeleton:

```bash
uvicorn vk_openclaw_service.main:app --reload
```

Run one VK worker polling cycle:

```bash
vk-openclaw-worker --once
```

Run the VK worker continuously:

```bash
vk-openclaw-worker --interval-seconds 5
```

Set a known-good local model profile (WSL example):

Unified WSL runtime CLI (new):

```bash
vk-openclaw install
vk-openclaw start
vk-openclaw status
vk-openclaw stop
```

Build Linux one-file binary (inside WSL Ubuntu):

```bash
python -m pip install .[build]
python scripts/build_onefile_linux.py
```

See `docs/wsl_onefile_install.md` for the full flow.

```bash
openclaw models set ollama/deepseek-v3.1:671b-cloud
```

The worker emits structured JSON log records for startup, successful polling iterations, retryable failures, fatal failures, and loop completion.
Queued delivery retries are drained before each polling pass, and retry payloads are only replayed after their computed backoff delay has elapsed.
When a worker lease cannot be acquired, the loop emits a skip event and does not drain or poll in that iteration.
If a worker loses its lease after draining and before polling, the loop skips the poll step and releases ownership cleanly.
If a worker loses its lease during multi-peer polling, the runtime stops before the next peer instead of finishing the full poll cycle under stale ownership.
Retryable messages are dead-lettered once `RETRY_QUEUE_MAX_ATTEMPTS` is exhausted instead of being re-enqueued indefinitely.
Retry queue backoff defaults to `5s` base / `60s` max and can be overridden with `RETRY_QUEUE_BASE_BACKOFF_SEC` and `RETRY_QUEUE_MAX_BACKOFF_SEC`.
Dead-lettered messages are persisted in dedicated runtime storage alongside their audit trail.
Dead-letter admin list/query/saved-query flows can filter by both derived `severity` and persisted `priority`.
When `FREE_TEXT_ASK_ENABLED=true`, non-slash text from paired peers is treated as `/ask`; slash commands keep priority and unknown slash commands remain blocked.
Recommended rollout is canary-first with rollback to `FREE_TEXT_ASK_ENABLED=false` if `message_processing_failed` exceeds `5%` in 15 minutes, OpenClaw timeouts exceed `2%` in 15 minutes, or retry/send failures exceed `3%` in 15 minutes.

`GET /api/v1/status` and `GET /api/v1/health` now expose storage mode and degraded fallback state when `database` mode is requested but external adapters are not ready yet.
If `DATABASE_DSN` and `REDIS_DSN` are present, degraded reasons now distinguish missing drivers, connection failures, ping failures, and schema bootstrap failures. Successful PostgreSQL session wiring moves repository storage off the file fallback path.
`GET /api/v1/status` now includes a dead-letter summary with unresolved priority and reason breakdown, saved-query count, and worker lease ownership/handoff metadata, and `GET /api/v1/health` degrades when unresolved dead-letter records are present or a stale worker lease is detected. When dead letters are present, the health payload now includes the dominant unresolved reason. Acknowledged dead letters remain queryable, but no longer count against the unresolved summary.

## Workflow
1. System Architect
2. Tech Lead Reviewer
3. Senior Developer (TDD)
4. QA / Security Bot
5. Release Manager

## Verification Snapshot
- Latest confirmed full suite: `205 passed` via `powershell -ExecutionPolicy Bypass -File scripts/run_pytest_safe.ps1 -q`
- Current session verification: full `pytest` green, `scripts/verify_static.ps1` confirming `compileall`, `ruff`, `mypy`, and `bandit`, `scripts/build_package_safe.ps1` producing a local wheel artifact, `scripts/build_sdist_safe.ps1` producing a local source distribution, `scripts/verify_artifact.py` validating wheel metadata and entrypoints, `scripts/verify_sdist.py` validating source-distribution contents, `scripts/verify_sdist_rebuild.py` rebuilding a wheel from the source tarball, and `scripts/verify_install_smoke.py` confirming isolated wheel extract/import behavior
- Optional online security step: run `RUN_PIP_AUDIT=1 powershell -ExecutionPolicy Bypass -File scripts/verify_static.ps1` in a network-enabled environment


## Public Open-Source Preparation

For a safe public clone without secrets, follow:
- `docs/public_repo_open.md`

Key rule: keep real credentials only in local `.env`; commit only `.env.example` placeholders.

## VK Credentials Guide

Detailed step-by-step VK setup (token, peer_id, permissions):
- `docs/vk_setup.md`

## Author

- Гарипов Нияз Варисович
- garipovn@yandex.ru

## Installation (Linux and Windows)

Step-by-step install commands for required libraries and runtime setup:
- `docs/install.md`

VK token and peer data setup:
- `docs/vk_setup.md`
