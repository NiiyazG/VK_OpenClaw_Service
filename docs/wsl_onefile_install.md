# WSL One-File Install Guide

## Build in WSL

```bash
python -m pip install .[build]
python scripts/build_onefile_linux.py
```

Artifacts are generated in `.dist_verify/`.

## Install

```bash
chmod +x ./vk-openclaw
./vk-openclaw setup
```

Setup writes `.env.local` and detects service mode (`system-service` or `fallback-local`).

## Runtime Commands

```bash
./vk-openclaw run-all --wait-for-gateway
./vk-openclaw stop-all
./vk-openclaw doctor
```

## WSL2 Autostart

### Option A: `autostart.sh` + cron

```bash
chmod +x scripts/autostart.sh
crontab -e
```

Add:

```cron
@reboot cd /path/to/VK_OpenClaw_Service && ./scripts/autostart.sh start
```

### Option B: `/etc/wsl.conf` boot command

```ini
[boot]
command=/bin/bash -lc 'cd /path/to/VK_OpenClaw_Service && ./scripts/autostart.sh start'
```

Apply config:

```powershell
wsl --shutdown
```

## Diagnostics

```bash
./vk-openclaw doctor
tail -n 200 state/vk-openclaw.log
```

If `doctor` fails:
- check `.env.local` values (`VK_ACCESS_TOKEN`, `VK_ALLOWED_PEERS`);
- ensure gateway is reachable on `127.0.0.1:18789`;
- ensure port `8000` is free.
