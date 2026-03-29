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
- `ADMIN_API_TOKEN` (Enter for auto-generate)
- `VK_ACCESS_TOKEN`
- `VK_ALLOWED_PEERS`
- then applies defaults automatically:
  - `PERSISTENCE_MODE=file`
  - `OPENCLAW_COMMAND` resolved from local wrapper or `openclaw`

Advanced mode selection is still available via non-interactive config:
```bash
vk-openclaw setup --non-interactive --config install.json
```

Linux wizard notes:
- setup explanations are shown in RU/EN format (`RU / EN`)
- secret input is hidden on purpose (no echo while typing)
- if paste fails in hidden mode, switch secret input mode to `paste-visible`
- setup prints safe confirmation:
  - `ADMIN_API_TOKEN: SET (N chars), fingerprint: xxxxxxxxxxxx`
  - `VK_ACCESS_TOKEN: SET (N chars), fingerprint: xxxxxxxxxxxx`
- if `ADMIN_API_TOKEN` is auto-generated, installer shows it once and asks to save it

It writes local `.env.local`, installs service mode, starts service, and runs status check.

## Service commands
```bash
vk-openclaw start
vk-openclaw status
vk-openclaw stop
```

## Pairing helper (post-setup)
Interactive setup offers pairing helper:
- requests pair code from API
- tells user to run `/pair <code>` in VK
- waits until peer appears in `/api/v1/pairing/peers`
- suggests `/status` and `/ask`

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
