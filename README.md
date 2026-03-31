# VK OpenClaw Service

HEAD
`vk-openclaw-service` is a bridge between VK Messenger and OpenClaw.
It polls VK messages, runs OpenClaw commands, and sends responses back to VK.

## What is it / Что это
VK мессенджер + OpenClaw.

Ещё один канал для OpenClaw в преддверии 1 апреля.

VK - Сообщество - Управление - Работа с API - Ключ - Парринг с OpenClaw - VK мессенджер.

`vk-openclaw-service` is an open-source bridge between VK Messenger and OpenClaw.
The service receives VK messages, runs OpenClaw commands, sends results back to VK, and exposes admin API endpoints for health and audit.
dd0be9e122e7444ba8b3a9b60a7e7089403e0abf

`vk-openclaw-service` - это мост между VK Messenger и OpenClaw.
Сервис опрашивает VK, запускает команды OpenClaw и отправляет ответы обратно в чат.

## Quick Start / Быстрый старт

```bash
git clone https://github.com/NiiyazG/VK_OpenClaw_Service.git
cd VK_OpenClaw_Service
python -m pip install -e .
cp .env.example .env.local
```

Fill `.env.local` with real values, then run:

```bash
vk-openclaw run-all --wait-for-gateway
vk-openclaw doctor
```

Stop all local processes:

```bash
vk-openclaw stop-all
```

## Commands / Команды

Main commands:
- `vk-openclaw setup`
- `vk-openclaw install` (alias)
- `vk-openclaw start`
- `vk-openclaw stop`
- `vk-openclaw status`
- `vk-openclaw run-api`
- `vk-openclaw run-worker`
- `vk-openclaw run-all [--wait-for-gateway]`
- `vk-openclaw stop-all`
- `vk-openclaw doctor`

Runtime files:
- `state/api.pid`
- `state/worker.pid`
- `state/vk-openclaw.log`

## VK_ALLOWED_PEERS: what it is / что это

- For direct messages: use user id.
- For group chats: use `peer_id` format (`2000000000 + chat_id`).

- Для личных сообщений: укажите id пользователя.
- Для бесед: укажите `peer_id` (`2000000000 + chat_id`).

Visual example:

![VK_ALLOWED_PEERS example](pic/Снимок%20экрана%202026-03-31%20095254.png)

## Autostart / Автозапуск

### 1. systemd (Linux with systemd)

Use setup and service commands:

```bash
vk-openclaw setup
vk-openclaw start
vk-openclaw status
```

### 2. `autostart.sh` + cron `@reboot` (WSL2/Linux without systemd)

```bash
chmod +x scripts/autostart.sh
./scripts/autostart.sh start
./scripts/autostart.sh status
```

Cron:

```bash
crontab -e
# add:
@reboot cd /path/to/VK_OpenClaw_Service && ./scripts/autostart.sh start
```

Optional WSL boot:

`/etc/wsl.conf`
```ini
[boot]
command=/bin/bash -lc 'cd /path/to/VK_OpenClaw_Service && ./scripts/autostart.sh start'
```

### 3. Windows Task Scheduler

- Action: start `wsl.exe`
- Arguments: `-d <YourDistro> --cd /path/to/VK_OpenClaw_Service ./scripts/autostart.sh start`
- Trigger: `At startup` or `At log on`

## Diagnostics / Диагностика

Run:

```bash
vk-openclaw doctor
```

`doctor` checks:
- `.env.local` exists
- Python version is at least 3.12
- port `127.0.0.1:8000` is free
- OpenClaw gateway is reachable (`ws://127.0.0.1:18789`)
- VK token works (`users.get`)
- all `VK_ALLOWED_PEERS` are already paired

## Troubleshooting

### `VK API error 15: token required`
- Ensure `.env.local` exists and `VK_ACCESS_TOKEN` is set.
- Run `vk-openclaw doctor`.

### Worker does not process messages / Worker не обрабатывает сообщения
- Verify `VK_ALLOWED_PEERS` is correct for your chat.
- Check `state/vk-openclaw.log` for ignored peer ids.

### `Gateway not reachable`
- Start OpenClaw gateway first.
- Retry with `vk-openclaw run-all --wait-for-gateway`.

## Docs

- [Operations runbook](docs/operations_runbook.md)
- [WSL one-file install](docs/wsl_onefile_install.md)
- [Windows one-file install](docs/windows_onefile_install.md)
- [VK setup](docs/vk_setup.md)
