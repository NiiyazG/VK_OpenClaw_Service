# Architecture: vk-openclaw-service

## 1. Overview
- Goal: provide a secure production-ready bridge between VK Messenger and OpenClaw, replacing the previous Telegram-based interaction path.
- Core functions:
  - receive VK messages and supported attachments
  - enforce allowlist, pairing, rate limiting, and optional app-layer encryption
  - execute requests against local OpenClaw through a controlled adapter
  - return results, diagnostics, and audit data through VK and internal service APIs
- Non-functional requirements:
  - no message loss during backlog processing
  - no hardcoded secrets
  - structured logs and audit trail
  - safe retry and timeout handling for VK and OpenClaw failures
  - test-driven implementation for critical modules
  - clean cutover from the old Telegram workflow to the new VK-only runtime

## 2. Technology Stack
| Component | Technology | Version | Why |
|-----------|------------|---------|-----|
| Language | Python | 3.12 | predictable backend runtime and strong ecosystem |
| Web API | FastAPI | 0.115.x | typed API contracts and operational simplicity |
| Validation | Pydantic Settings | 2.x | environment-driven config without hardcoding |
| DB | PostgreSQL | 16 | durable state, audit events, runtime offsets |
| Cache/Queue | Redis | 7 | rate limiting, nonce cache, worker coordination |
| ORM/Migrations | SQLAlchemy + Alembic | 2.x / 1.13.x | explicit schema evolution |
| Testing | pytest | 8.x | TDD and integration coverage |
| Quality/Security | ruff, mypy, bandit, pip-audit, gitleaks | current stable | automated verification gates |

## 3. Project Structure
```text
src/
|-- api/
|   |-- routes/
|   |-- schemas/
|   `-- deps/
|-- core/
|   |-- config.py
|   |-- security.py
|   `-- logging.py
|-- domain/
|   |-- pairing.py
|   |-- messages.py
|   |-- attachments.py
|   `-- openclaw.py
|-- infra/
|   |-- db/
|   |-- cache/
|   `-- vk/
|-- workers/
|   `-- polling.py
|-- services/
|   |-- pairing_service.py
|   |-- message_service.py
|   `-- audit_service.py
`-- main.py

tests/
|-- unit/
|-- integration/
`-- e2e/
```

## 4. Module Decomposition
| Module | Responsibility | Estimated Size | Priority |
|--------|----------------|----------------|----------|
| Config/Security | settings, secret loading, admin auth, encryption policy | <= 200 LOC per file | P0 |
| Pairing | one-time pair codes, peer binding, expiry rules | <= 200 LOC per file | P0 |
| VK Transport | polling, send API, retries, timeout mapping | <= 200 LOC per file | P0 |
| Message Processing | command parsing, policy checks, backlog-safe orchestration | <= 200 LOC per file | P0 |
| Attachments | MIME validation, download policy, temp lifecycle | <= 200 LOC per file | P0 |
| OpenClaw Adapter | controlled subprocess execution and timeout handling | <= 200 LOC per file | P0 |
| API/Admin | status, health, config validation, audit endpoints | <= 200 LOC per file | P1 |
| Observability | structured logs, audit events, metrics hooks | <= 200 LOC per file | P1 |
| Rollout | cutover procedure, verification checklist, rollback decision points | <= 200 LOC per file | P1 |

Dependencies:
- `api` depends on `services`, `core`, `infra`
- `workers` depend on `services`, `infra`, `domain`
- `services` coordinate `domain` rules with `infra` adapters
- `domain` is transport-agnostic and does not depend on `api`

## 5. API Contracts
Authentication policy for internal admin endpoints:
- `POST /api/v1/pairing/code`, `GET /api/v1/status`, `GET /api/v1/health`, `POST /api/v1/config/validate`, and `GET /api/v1/audit/events` require `Authorization: Bearer <ADMIN_API_TOKEN>`.
- `ADMIN_API_TOKEN` is loaded only from environment or secret storage; it is never persisted in logs or DB in plaintext.
- Rotation policy for v1: deploy new token, reload service, validate privileged access, invalidate previous token immediately after verification.
- `POST /api/v1/pairing/verify` is intentionally unauthenticated at the admin layer because it is user-facing but still constrained by allowlist, one-time code validation, and expiry rules.

### POST /api/v1/pairing/code
- Purpose: create a one-time pairing code for an allowed peer.
- Request: `{ "peer_id": int }`
- Response: `{ "code": str, "expires_at": str }`
- Errors: `400`, `401`, `403`, `409`

### POST /api/v1/pairing/verify
- Purpose: bind a peer to the service after code validation.
- Request: `{ "peer_id": int, "code": str }`
- Response: `{ "status": "paired" }`
- Errors: `400`, `403`, `410`

### GET /api/v1/status
- Purpose: return mode, worker state, configured limits, paired peers count.
- Response: `{ "mode": str, "worker": { "state": "idle|polling|degraded", "lag_messages": int, "last_success_at": str | null }, "paired_peers": int, "limits": { "rate_per_min": int, "max_attachments": int, "max_file_mb": int }, "checkpoint": { "peer_id": int | null, "last_committed_message_id": int | null } }`
- Errors: `401`, `503`

### GET /api/v1/health
- Purpose: health/readiness probe for API, DB, Redis, VK adapter, OpenClaw adapter.
- Response: `{ "status": "ok|degraded|failed", "checks": [{ "component": str, "status": "ok|degraded|failed", "reason": str | null }] }`
- Errors: `401`, `503`

### POST /api/v1/config/validate
- Purpose: validate runtime configuration before deployment or reload.
- Request: `{ "source": "env|payload", "settings": object | null }`
- Response: `{ "valid": bool, "issues": [{ "field": str, "message": str }] }`
- Errors: `400`, `401`

### GET /api/v1/audit/events
- Purpose: read audit events for operations and failures.
- Query: `from`, `to`, `peer_id`, `event_type`, `limit`, `cursor`
- Response: `{ "items": [{ "id": str, "ts": str, "event_type": str, "peer_id": int | null, "status": str, "details": object }], "next_cursor": str | null }`
- Errors: `401`, `403`

## 6. Data and State
- PostgreSQL stores:
  - `paired_peers(peer_id, paired_at, mode, status)`
  - `pairing_codes(peer_id, code_hash, expires_at, consumed_at)`
  - `message_checkpoints(peer_id, last_committed_message_id, last_seen_message_id, status, updated_at)`
  - `audit_events(id, ts, event_type, peer_id, status, details_json)`
  - `admin_token_metadata(token_fingerprint, rotated_at, active)` if token rotation metadata is enabled
  - `config_snapshots(id, created_at, payload_json)` if configuration history is enabled
- Redis stores:
  - rate-limit windows
  - replay-protection nonces
  - short-lived worker locks
- Temp filesystem stores:
  - downloaded attachments within TTL-controlled directory only

Initial migration set:
- `0001_initial_core_tables`: paired peers, pairing codes, message checkpoints, audit events
- `0002_admin_token_metadata`: optional token fingerprint metadata
- `0003_config_snapshots`: optional config snapshot support

Checkpoint model:
- one checkpoint row per `peer_id`
- `last_seen_message_id` tracks the highest message observed from VK
- `last_committed_message_id` tracks the highest message fully processed and safe to skip on restart
- `status` is one of `idle`, `processing`, `degraded`
- worker advances `last_committed_message_id` only after reply delivery or explicit dead-lettering succeeds
- if processing fails before commit, the message remains eligible for retry on the next poll cycle
- dead-lettered messages create an audit event with stable failure reason and still advance commit only after the dead-letter write succeeds

## 7. Runtime Flow
1. VK worker polls history with backlog-safe pagination until the stored checkpoint is reached.
2. Incoming message is validated against peer allowlist.
3. Payload is decrypted if encryption mode requires or allows it.
4. Pairing and rate-limit policy are enforced.
5. Attachments are downloaded only for supported commands and validated by MIME and size.
6. OpenClaw adapter executes the request with timeout and sanitized error mapping.
7. Reply is sent back to VK, optionally encrypted.
8. Offset advances only after the message is fully handled or explicitly dead-lettered.
9. Audit and operational logs are written for every significant step.

Failure semantics:
- `VK read failure`: do not move checkpoint; mark worker degraded; retry with backoff.
- `attachment validation failure`: write audit event, send refusal if possible, then commit the message.
- `OpenClaw timeout or command failure`: send sanitized failure reply if possible, then commit the message as handled failure.
- `reply send failure`: do not commit; retry on next cycle to preserve at-least-once delivery.
- repeated hard failures beyond retry budget: write dead-letter record, then commit after dead-letter persistence.

## 8. Risks and Mitigations
| Risk | Probability | Mitigation |
|------|-------------|------------|
| VK backlog message loss | High | cursor advances only after paginated processing; integration tests for >10 messages |
| Attachment MIME spoofing | Medium | validate server metadata plus file extension policy and enforce allowlist |
| Network instability | High | retry/backoff, timeout mapping, worker isolation, health degradation state |
| Secret leakage | Medium | env-only secrets, no logging of raw payloads, gitleaks in QA gate |
| OpenClaw hang | Medium | hard timeout, kill-and-report policy, audit event, worker recovery |
| Unauthorized admin access | Medium | `Bearer ADMIN_API_TOKEN`, fingerprint-based rotation metadata, authz on internal APIs |

## 9. Testing Strategy
- Unit tests for pairing, command parsing, encryption, attachment policy, retry logic.
- Integration tests for VK polling backlog, OpenClaw execution flow, DB/Redis-backed state.
- Negative tests for invalid pair codes, replayed ciphertext, oversized files, unsupported MIME, VK timeouts.
- QA gate requires full green test suite and >=80% coverage on critical domains.

Mandatory operational signals:
- polling lag in messages and seconds
- failed VK send count
- VK read retry count
- rejected attachment count by reason
- OpenClaw timeout count
- dead-letter count
- current worker degradation reason

## 10. Deployment and Rollout
- Migration strategy: clean cutover to the new VK-only service; no parallel runtime with the old Telegram workflow.
- Pre-cutover steps:
  - deploy DB migrations
  - provision `ADMIN_API_TOKEN`, `VK_ACCESS_TOKEN`, encryption secret, and OpenClaw runtime settings
  - pre-create allowlist and generate fresh pairing codes
  - run config validation and health checks
- Cutover steps:
  - stop the old Telegram-based workflow
  - start `vk-openclaw-service` API and worker
  - validate `status`, `health`, pairing, and a controlled test message
  - confirm checkpoint creation and audit event flow
- Rollback rule:
  - if health remains degraded or controlled message verification fails, stop the new service, preserve DB state for analysis, and do not reopen the old Telegram workflow until secrets and checkpoints are reviewed
- Behavior parity validation:
  - `/help`, `/status`, `/pair`, `/ask`, attachment refusal, encrypted payload rejection, and timeout handling must match agreed v1 behavior before release

## 11. Readiness Checklist
- [x] Core modules identified
- [x] API contracts defined
- [x] Error handling included in architecture
- [x] Logging and monitoring included
- [x] Rate limiting included
- [x] DB migration plan included
- [x] Security constraints documented
- [ ] Human approval after architecture review
