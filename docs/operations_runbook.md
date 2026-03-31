# Operations Runbook

## Service Modes

`vk-openclaw-service` supports two runtime modes:
- `system-service` (systemd user units)
- `fallback-local` (local subprocesses with PID files and log in `./state`)

Fallback-local is the default for WSL2 when `systemd --user` is not available.

## Process Management

Unified local process commands:

```bash
vk-openclaw run-all --wait-for-gateway
vk-openclaw stop-all
vk-openclaw status
```

State artifacts:
- `state/api.pid`
- `state/worker.pid`
- `state/vk-openclaw.log`
- `state/pairing.json`

Autostart helper:

```bash
./scripts/autostart.sh start
./scripts/autostart.sh stop
./scripts/autostart.sh status
./scripts/autostart.sh restart
```

## Diagnostics

Run strict diagnostics:

```bash
vk-openclaw doctor
```

The command fails (`exit code 1`) if any critical check fails:
- `.env.local` missing
- Python < 3.12
- gateway not reachable
- invalid VK token
- port 8000 busy
- missing pairing for one of `VK_ALLOWED_PEERS`

## Pairing Operations

Pairing state is persistent in `state/pairing.json`.

Expected behavior:
- once peer is paired, restart does not require re-pairing;
- `doctor` validates that all allowed peers are paired.

Check paired peers via API:

```bash
curl -s -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  http://127.0.0.1:8000/api/v1/pairing/peers
```

## Incident Checklist

1. Run `vk-openclaw doctor`.
2. Check `state/vk-openclaw.log`.
3. Verify `VK_ALLOWED_PEERS` and token in `.env.local`.
4. Verify OpenClaw gateway is running (`127.0.0.1:18789`).
5. Restart local runtime with `stop-all` + `run-all --wait-for-gateway`.
