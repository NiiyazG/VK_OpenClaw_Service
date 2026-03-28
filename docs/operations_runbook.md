# Operations Runbook

## Scope
This runbook covers the current operator-facing control plane for:
- status and health inspection
- audit summary inspection
- dead-letter review and acknowledgment
- worker lease inspection and stale-lease recovery

## Authentication
All admin endpoints require:

```text
Authorization: Bearer <ADMIN_API_TOKEN>
```

Optional operator attribution for mutating actions:

```text
X-Operator-Id: <operator-or-system-id>
```

## Primary Inspection Endpoints
Use these first when checking runtime state:

1. `GET /api/v1/status`
2. `GET /api/v1/health`
3. `GET /api/v1/audit/summary`
4. `GET /api/v1/audit/worker-lease`
5. `GET /api/v1/audit/dead-letters`

## Standard Workflow
1. Check `GET /api/v1/health`.
2. If health is degraded, inspect `GET /api/v1/status`.
3. If dead letters are present, inspect `GET /api/v1/audit/dead-letters` or `GET /api/v1/audit/summary`.
4. If worker ownership looks stale or contested, inspect `GET /api/v1/audit/worker-lease`.
5. Use targeted acknowledgment or stale-lease reset only after the underlying issue is understood.

## Free-Text Ask Rollout
`FREE_TEXT_ASK_ENABLED` controls whether non-slash text from paired peers is routed to OpenClaw.

Recommended sequence:
1. Keep `FREE_TEXT_ASK_ENABLED=false` in baseline release.
2. Enable on a canary instance or limited peer set.
3. Observe audit and failure ratios for at least 24 hours.
4. Enable globally only if canary is stable.

Rollback triggers (15-minute window):
- `message_processing_failed` > `5%`
- OpenClaw timeout failures > `2%`
- retry/send failures > `3%`

Rollback action:
- immediately set `FREE_TEXT_ASK_ENABLED=false`
- restart worker processes
- preserve audit events for failure analysis

## Current WSL Runtime Profile
Recommended values and checks for the current local deployment profile:
- `OPENCLAW_COMMAND=./openclaw_agent_wrapper.sh`
- `FREE_TEXT_ASK_ENABLED=true` (after successful canary)
- default model profile set to `ollama/deepseek-v3.1:671b-cloud`

Quick validation:
```text
chmod +x ~/projects/vk-openclaw-service/openclaw_agent_wrapper.sh
ls -l ~/projects/vk-openclaw-service/openclaw_agent_wrapper.sh
openclaw models
```

API/worker restart (tmux):
```text
tmux kill-session -t vkapi 2>/dev/null; fuser -k 8000/tcp 2>/dev/null; tmux new-session -d -s vkapi "cd ~/projects/vk-openclaw-service && source .venv/bin/activate && set -a && source .env.local && set +a && mkdir -p \"$STATE_DIR\" && python -m uvicorn vk_openclaw_service.main:app --host 127.0.0.1 --port 8000"
tmux kill-session -t vkworker 2>/dev/null; tmux new-session -d -s vkworker "cd ~/projects/vk-openclaw-service && source .venv/bin/activate && set -a && source .env.local && set +a && vk-openclaw-worker --interval-seconds 5"
```

## Dead-Letter Workflows
### List unresolved dead letters
```text
GET /api/v1/audit/dead-letters?preset=unresolved
```

### List critical dead letters
```text
GET /api/v1/audit/dead-letters?preset=critical
```

### Filter by reason or peer
```text
GET /api/v1/audit/dead-letters?reason=retry_budget_exhausted&peer_id=42
```

### Acknowledge a single dead letter
```text
POST /api/v1/audit/dead-letters/{id}/ack
```

### Acknowledge several known records
```text
POST /api/v1/audit/dead-letters/ack-bulk
```

Body:
```json
{
  "dead_letter_ids": ["dlq-1", "dlq-2"]
}
```

### Acknowledge by query
```text
POST /api/v1/audit/dead-letters/ack-query
```

Example:
```json
{
  "preset": "critical",
  "limit": 50
}
```

### Saved-query workflow
1. Create or update a saved query with:
   `PUT /api/v1/audit/dead-letters/saved/{name}`
2. Preview matches with:
   `GET /api/v1/audit/dead-letters/saved/{name}/items`
3. Execute acknowledgment with:
   `POST /api/v1/audit/dead-letters/saved/{name}/ack`

## Worker Lease Workflows
### Inspect current lease state
```text
GET /api/v1/audit/worker-lease
```

Important fields:
- `owner_id`
- `held`
- `held_by_self`
- `stale`
- `acquired_at`
- `refreshed_at`
- `previous_owner_id`
- `takeover_at`
- `takeover_count`

### Reset only a stale lease
```text
POST /api/v1/audit/worker-lease/reset
```

Expected behavior:
- success only when the current lease is stale
- returns `409 worker_lease_not_stale_or_missing` when the lease is active or absent
- appends `worker_lease_reset` to the audit feed

## Audit Summary Usage
`GET /api/v1/audit/summary` is the compact operator dashboard.

Use it for:
- event counts by type
- recent event types
- unresolved dead-letter totals
- unresolved dead-letter breakdown by `priority`
- unresolved dead-letter breakdown by `reason`
- saved-query count and names
- worker lease snapshot plus takeover/reset counts

## Decision Rules
### When to acknowledge dead letters
- after the underlying delivery or processing issue is understood
- after confirming the record no longer needs to drive `health=degraded`
- after preserving enough audit context for follow-up

### When to reset a stale worker lease
- only if `stale=true`
- only if the previous owner is known to be gone or unhealthy
- only after checking the audit feed for recent takeover/reset churn

### When not to intervene manually
- do not reset an active lease just to move ownership
- do not bulk-ack unresolved dead letters without filtering by reason, severity, or time window
- do not treat `acknowledged` dead letters as deleted records; they remain part of the audit trail

## Current Verified Baseline
- Full suite: `205 passed`
- Local combined gate: `powershell -ExecutionPolicy Bypass -File scripts/verify_release.ps1 -q`
- Gate handoff files: `.verify_reports/release_summary.json`, `.verify_reports/release_summary.md`, `.verify_reports/distribution_checksums.txt`
- Release manifest files: `.verify_reports/release_manifest.json`, `.verify_reports/release_manifest.md`
- Release handoff bundle: `.release_bundle/`
- CI handoff artifacts: `verification-reports`, `distribution-artifacts`, `release-handoff-bundle`
- Package artifact check: `powershell -ExecutionPolicy Bypass -File scripts/build_package_safe.ps1`
- Source distribution check: `powershell -ExecutionPolicy Bypass -File scripts/build_sdist_safe.ps1`
- Artifact smoke check: `python scripts/verify_artifact.py`
- Source distribution smoke check: `python scripts/verify_sdist.py`
- Source distribution rebuild smoke: `python scripts/verify_sdist_rebuild.py`
- Install smoke check: `python scripts/verify_install_smoke.py`
- Release handoff bundle verification: `python scripts/verify_release_bundle.py`
- Release manifest verification: `python scripts/verify_release_manifest.py`
- Release manifest sync source: `python scripts/generate_release_manifest.py --summary-path .verify_reports/release_summary.json --output-dir .verify_reports`
- Release-summary parity: `.verify_reports/release_summary.json` and `.verify_reports/release_manifest.json` now record the same final verification steps, including `release-manifest` and `release-manifest-artifact`
- Remaining external gap: none after a successful `RUN_PIP_AUDIT=1` release verification pass
