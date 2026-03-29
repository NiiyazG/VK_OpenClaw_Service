# vk-openclaw-service

## What is it / Что это
`vk-openclaw-service` is an open-source bridge between VK Messenger and OpenClaw.
The service receives VK messages, runs OpenClaw commands, sends results back to VK, and exposes admin API endpoints for health and audit.

`vk-openclaw-service` - это open-source мост между VK Messenger и OpenClaw.
Сервис принимает сообщения из VK, запускает команды OpenClaw, отправляет ответ обратно в VK и предоставляет admin API для статуса и аудита.

## Features / Возможности
- VK polling worker with controlled retries and backoff.
- Pairing and allowlist flow for safer peer access.
- Config validation endpoint before runtime rollout.
- Audit and dead-letter endpoints for operations visibility.
- Optional PostgreSQL + Redis runtime mode.
- Cross-platform setup wizard (`vk-openclaw setup`) for Linux and Windows.

## Quick Start / Быстрый старт
Detailed platform commands are in `docs/install.md`.

Clone repository / Клонировать репозиторий:
```bash
git clone https://github.com/NiiyazG/VK_OpenClaw_Service.git
cd VK_OpenClaw_Service
ls pyproject.toml
```

Linux one-command setup:
```bash
chmod +x ./install.sh
./install.sh
```

Interactive setup now auto-selects:
- `PERSISTENCE_MODE=file`
- `OPENCLAW_COMMAND` from local wrapper or `openclaw`

Use custom values only through non-interactive config:
```bash
vk-openclaw setup --non-interactive --config install.json
```

Windows one-command setup (PowerShell):
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
```

Service control / Управление сервисом:
```bash
vk-openclaw start
vk-openclaw status
vk-openclaw stop
```
## Configuration / Конфигурация
Required runtime variables (minimum):
- `ADMIN_API_TOKEN`
- `VK_ACCESS_TOKEN`
- `VK_ALLOWED_PEERS`
- `OPENCLAW_COMMAND`

Use placeholders from `.env.example` and keep real values only in local `.env` / `.env.local`.

## VK Setup / Настройка VK
Step-by-step token and `peer_id` setup:
- `docs/vk_setup.md`

Pairing flow (VK-first):
1. Setup helper requests a code via admin API.
2. You send `/pair <code>` in the target VK chat.
3. Worker verifies the code from the VK message and replies:
   - `Pairing successful.`
   - `Invalid or expired pairing code.`
4. Setup helper confirms that the peer appears in paired peers.

If VK does not respond:
- verify `VK_ALLOWED_PEERS` contains the real `peer_id`,
- check `vk-openclaw status`,
- rerun setup and pairing helper.

## Security / Безопасность
Never commit:
- `.env` files
- tokens and passwords
- DSN values with credentials
- private keys

Public repository safety checklist:
- `docs/public_repo_open.md`

## Documentation map / Карта документации
- Architecture: `docs/architecture.md`
- Operations runbook: `docs/operations_runbook.md`
- Contributor guide: `CONTRIBUTING.md`
- Installation guide: `docs/install.md`
- Windows one-file guide: `docs/windows_onefile_install.md`

## Author & License / Автор и лицензия
- Author: Гарипов Нияз Варисович
- Email: garipovn@yandex.ru
- License: MIT (`LICENSE`)
