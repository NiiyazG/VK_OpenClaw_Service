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
- CLI installer flow for WSL (`vk-openclaw install`).

## Quick Start / Быстрый старт
Detailed platform commands are in `docs/install.md`.

Linux (bash):
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
cp .env.example .env
uvicorn vk_openclaw_service.main:app --reload
```

Windows (PowerShell):
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
Copy-Item .env.example .env
uvicorn vk_openclaw_service.main:app --reload
```

Run worker / Запуск воркера:
```bash
vk-openclaw-worker --once
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

## Author & License / Автор и лицензия
- Author: Гарипов Нияз Варисович
- Email: garipovn@yandex.ru
- License: MIT (`LICENSE`)
