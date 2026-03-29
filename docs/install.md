# Installation Guide (Linux + Windows)

## Goal
User should start setup with one command or one click, then follow guided prompts for VK data.

## Required software
- Python 3.12+
- pip
- Git
- OpenClaw CLI (`openclaw --version`)

## One-command setup (Linux)
```bash
git clone <your-public-repo-url>
cd vk-openclaw-service
chmod +x ./install.sh
./install.sh
```

Alternative manual:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
vk-openclaw setup
```

## One-command setup (Windows PowerShell)
```powershell
git clone <your-public-repo-url>
cd vk-openclaw-service
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
```

Alternative manual:
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
vk-openclaw setup
```

## Guided setup behavior
`vk-openclaw setup` asks for:
- `VK_ACCESS_TOKEN` (visible paste input)
- `VK_ALLOWED_PEERS`
- then applies defaults automatically:
  - `ADMIN_API_TOKEN` auto-generated and shown once
  - `PERSISTENCE_MODE=file`
  - `OPENCLAW_COMMAND` resolved from local wrapper or `openclaw`
  - `FREE_TEXT_ASK_ENABLED=true`

Advanced mode selection is still available via non-interactive config:
```bash
vk-openclaw setup --non-interactive --config install.json
```

Linux wizard notes:
- setup explanations are shown in RU/EN format (`RU / EN`)
- setup prints safe confirmation:
  - `ADMIN_API_TOKEN: SET (N chars), fingerprint: xxxxxxxxxxxx`
  - `VK_ACCESS_TOKEN: SET (N chars), fingerprint: xxxxxxxxxxxx`
- installer validates `VK_ACCESS_TOKEN` via VK API preflight before service start
- if `openclaw_agent_wrapper.sh` exists, installer marks it executable automatically

It writes local `.env.local` in all modes.
- If `systemd --user` is available: installs system service, restarts service (fallback: start), and runs status check.
- If `systemd --user` is unavailable: switches to `fallback-local` automatically and prints local launch commands.

VK token source:
1. Create/open VK community.
2. `Manage -> Advanced -> API access`.
3. `Create key`.
4. Use key value as `VK_ACCESS_TOKEN`.

Peer id source:
- DM: user id.
- Group chat: `peer_id`.

## Service commands
```bash
source .venv/bin/activate
vk-openclaw start
vk-openclaw status
vk-openclaw stop
```

## Pairing helper (post-setup)
Interactive setup offers pairing helper:
- requests pair code from API
- if `VK_ALLOWED_PEERS` has multiple values, asks `PAIRING_PEER_ID`
- tells user to run `/pair <code>` in VK
- waits until peer appears in `/api/v1/pairing/peers`
- suggests `/status` and `/ask`
- uses `http://127.0.0.1:8000` by default; override with `VK_OPENCLAW_API_BASE_URL`

## Fallback run mode (without systemd --user)
If `systemctl --user` fails with `Failed to connect to bus`, run:
```bash
cd ~/VK_OpenClaw_Service
source .venv/bin/activate
set -a && source .env.local && set +a
nohup ./.venv/bin/vk-openclaw run-api --host 127.0.0.1 --port 8000 >/tmp/vk_api.log 2>&1 &
nohup ./.venv/bin/vk-openclaw run-worker --interval-seconds 5 >/tmp/vk_worker.log 2>&1 &
tail -n 50 /tmp/vk_worker.log
```
Important: load `.env.local` before manual worker start. Otherwise worker may fail with `VK API error 15: token required`.

## Troubleshooting
1. Invalid VK token:
- rotate token in VK settings and run `vk-openclaw setup` again.

2. Wrong `peer_id`:
- resolve peer via VK API/logs, update `VK_ALLOWED_PEERS`, rerun setup.

3. Linux service issue:
- ensure `systemd --user` is available and active.

4. Windows service issue:
- provide `winsw.exe` (`tools/winsw/winsw.exe`) or set `WINSW_PATH`.

5. DNS/network issue:
- retry after network recovery; database checks are warnings unless mode requires connectivity.

6. WSL DNS flaps (`Temporary failure in name resolution`):
- pin DNS:
```bash
sudo bash -c 'printf "[network]\ngenerateResolvConf = false\n" > /etc/wsl.conf && rm -f /etc/resolv.conf && printf "nameserver 1.1.1.1\nnameserver 8.8.8.8\n" > /etc/resolv.conf && chmod 644 /etc/resolv.conf'
```
- then run `wsl --shutdown` from Windows PowerShell.
