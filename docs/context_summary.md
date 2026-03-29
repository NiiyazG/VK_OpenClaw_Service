# Context Summary
## Previous Stage Summary
The runtime now has explicit persistence modes, PostgreSQL-backed durable storage with live readiness bootstrap, and Redis-backed runtime roles for rate limiting, replay protection, retry queue storage, retry draining, and short-lived worker lease coordination. Retry queue payloads carry `attempt` and `available_at`, replay happens only after the computed backoff window, and retryable messages now stop re-enqueueing once the configured attempt budget is exhausted. Dead-lettered messages are persisted through a dedicated repository/store, now carry an explicit persisted `priority` field in addition to derived `severity`, remain readable through an admin API endpoint with server-side filters including creation-time and acknowledged-time windows plus named presets, and support persistence-backed saved queries that can be listed, stored, previewed, executed, and deleted. Saved-query persistence now spans memory, file, and PostgreSQL-ready database mode instead of falling back to file once the database path is live. Dead-letter workflows also support single-record, bulk-by-id, and bulk-by-query acknowledgment with operator attribution, while `status` now exposes unresolved dead-letter counts broken down by both priority and reason plus the current saved-query count. The audit surface now also includes a compact summary endpoint with event-type counts, recent event types, saved-query names, dead-letter totals, unresolved dead-letter priority/reason breakdowns, and worker-lease takeover/reset counts. Worker lease ownership is renewed between drain and poll, heartbeat-checked between peers during polling, exposed through identity metadata including `owner_id`, `acquired_at`, and `refreshed_at`, eligible for takeover once the last observed heartbeat is older than the configured lease TTL, reports the last handoff through `previous_owner_id`, `takeover_at`, and `takeover_count`, emits a dedicated `worker_lease_taken_over` audit event on stale handoff, now attributes that automatic handoff as `requested_by=worker:<worker_id>` with `trigger=automatic_stale_takeover`, is inspectable through a dedicated read-only admin endpoint, can now be reset only when stale through a guarded admin control that appends `worker_lease_reset`, and mutating admin actions now persist optional operator identity from `X-Operator-Id`.

## Current Stage
Senior Developer completed cross-platform installer execution in 777NC mode.

## Current Goal
Ship one-click/one-command installation UX for Linux and Windows with guided VK onboarding.

## Latest Implementation Delta
- CLI entrypoint now uses `vk-openclaw setup` as the primary installer command, with `install` retained as alias.
- Installer was refactored into cross-platform setup orchestration with:
  - Linux service backend (`systemd --user`)
  - Windows service backend (WinSW wrapper)
  - `--dry-run` redacted config preview
  - guided VK config prompts and post-setup pairing helper
- Added bootstrap scripts:
  - `install.sh` (Linux one-command setup)
  - `scripts/setup_windows.ps1` (Windows one-command setup)
- Added Windows one-file build helper:
  - `scripts/build_onefile_windows.py`
- Updated docs and release bundle inclusion list for Linux/Windows setup assets.

## Latest Verification Signal
- Full unit suite is green in this environment: `227 passed`.
- Installer-focused tests are green with added coverage for setup aliasing, service backend dispatch, dry-run redaction, Linux write/install flow, and Windows WinSW prerequisite handling.
