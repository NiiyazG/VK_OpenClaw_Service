# Windows One-Click Install Guide

## Build (PowerShell on Windows 11/10)
```powershell
python -m pip install .[build]
python scripts/build_onefile_windows.py
```

Artifacts are written to `.dist_verify/`:
- `vk-openclaw-setup.exe`
- `vk-openclaw-setup.exe.sha256`
- `setup_windows.ps1`

## One-Click / One-Command Setup
One-click:
```powershell
.\.dist_verify\vk-openclaw-setup.exe setup
```

One-command bootstrap:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
```

The setup wizard will:
- request `VK_ACCESS_TOKEN`, `VK_ALLOWED_PEERS`, and `ADMIN_API_TOKEN`
- explain where to obtain VK values
- save local `.env.local`
- register and start service mode via WinSW

## Runtime control
```powershell
vk-openclaw start
vk-openclaw status
vk-openclaw stop
```

## WinSW prerequisite
Provide `winsw.exe` in one of these locations before running setup:
- `tools/winsw/winsw.exe`
- `scripts/winsw.exe`
- repository root `winsw.exe`

Or set explicit path:
```powershell
$env:WINSW_PATH="C:\path\to\winsw.exe"
```
