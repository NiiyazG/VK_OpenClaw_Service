# VK Setup Guide (RU + EN)

## RU: что вводить в setup wizard

Запуск мастера:
```bash
vk-openclaw setup
```

Подсказки мастера в Linux выводятся на двух языках: `RU / EN`.
Ввод секретов скрыт в терминале и это нормально.

Мастер попросит:
- `VK_ACCESS_TOKEN`
- `VK_ALLOWED_PEERS`
- `ADMIN_API_TOKEN`

После ввода мастер безопасно подтверждает:
```text
ADMIN_API_TOKEN: SET (64 chars)
VK_ACCESS_TOKEN: SET (123 chars)
```
`SET (N chars)` значит значение сохранено, но не показывается.

### 1. Как получить `VK_ACCESS_TOKEN`
1. Откройте VK Developer / VK ID настройки приложения или сообщества.
2. Создайте токен с правами на чтение и отправку сообщений.
3. Храните токен только локально (`.env.local`), не коммитьте в git.

Пример:
```env
VK_ACCESS_TOKEN=vk1.a.real_token_value
```

### 2. Как получить `VK_ALLOWED_PEERS` (peer_id)
Варианты:
- взять из worker логов после тестового сообщения;
- через VK API (`messages.getConversations`, `messages.getHistory`).

Пример:
```env
VK_ALLOWED_PEERS=123456789
```

### 3. Pairing после setup
После установки мастер предлагает pairing helper:
1. Генерирует pair-code через API.
2. Показывает команду для VK: `/pair <code>`.
3. Проверяет pair и рекомендует проверить `/status` и `/ask`.

Если helper пропущен:
- вручную вызовите `POST /api/v1/pairing/code`,
- отправьте `/pair <code>` в VK,
- подтвердите через `POST /api/v1/pairing/verify`.

### 4. Частые ошибки
1. `token required` или `Unauthorized`:
- токен пустой/невалидный, перевыпустите его в VK.

2. `/help` работает, но `/ask` не работает:
- peer не paired, завершите pairing flow.

3. Неверный `peer_id`:
- обновите `VK_ALLOWED_PEERS` и перезапустите setup.

## EN: what to provide to setup wizard

Run:
```bash
vk-openclaw setup
```

Required values:
- `VK_ACCESS_TOKEN`
- `VK_ALLOWED_PEERS`
- `ADMIN_API_TOKEN` (auto-generate is supported)

Recommended flow:
1. Generate VK token with messaging permissions.
2. Resolve `peer_id` from logs or VK API.
3. Complete guided pairing helper.
4. Confirm VK commands: `/status` then `/ask ...`.

## Security notes
- Never commit `.env`, `.env.local`, access tokens, passwords, DSN credentials, or private keys.
- If any token is exposed, rotate it immediately and invalidate old credentials.
