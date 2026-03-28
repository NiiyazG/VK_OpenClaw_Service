# WSL One-File Install Guide

## Build (inside WSL Ubuntu 22.04/24.04)
```bash
python -m pip install .[build]
python scripts/build_onefile_linux.py
```

Artifacts are written to `.dist_verify/`:
- `vk-openclaw`
- `vk-openclaw.sha256`
- `vk-openclaw-install-guide.md`

## Install and Configure
```bash
chmod +x ./vk-openclaw
./vk-openclaw install
```

The installer will:
- check WSL/systemd/openclaw prerequisites
- ask for tokens and runtime parameters (RU prompts)
- write `.env.local` with `chmod 600`
- create user units:
  - `~/.config/systemd/user/vk-openclaw-api.service`
  - `~/.config/systemd/user/vk-openclaw-worker.service`

## Runtime control
```bash
./vk-openclaw start
./vk-openclaw status
./vk-openclaw stop
```

