# VK Setup Guide (RU + EN)

## RU: что нужно получить в ВКонтакте

Для запуска сервиса вам нужны минимум:
- `VK_ACCESS_TOKEN`
- `VK_ALLOWED_PEERS`

### 1. Создайте приложение VK
1. Откройте https://vk.com/dev и авторизуйтесь.
2. Создайте standalone/server-side приложение.
3. Включите доступ к сообщениям сообщества/бота (если используете Community API flow).

### 2. Получите `VK_ACCESS_TOKEN`
1. Перейдите в настройки приложения/сообщества.
2. Сгенерируйте сервисный токен с правами чтения/отправки сообщений.
3. Сохраните токен только локально, в `.env` (не в git).

Пример:
```env
VK_ACCESS_TOKEN=vk1.a.real_token_value
```

### 3. Узнайте `peer_id`
Варианты:
- Написать тестовое сообщение и посмотреть peer_id через отладочный лог воркера.
- Получить peer_id через VK API (`messages.getConversations` / `messages.getHistory`).

Пример:
```env
VK_ALLOWED_PEERS=123456789
```

### 4. Заполните локальный `.env`
Скопируйте шаблон и заполните секреты:
```bash
cp .env.example .env
```

Минимально:
```env
ADMIN_API_TOKEN=your_admin_token
VK_ACCESS_TOKEN=your_vk_token
VK_ALLOWED_PEERS=123456789
OPENCLAW_COMMAND=./openclaw_agent_wrapper.sh
```

### 5. Проверьте конфиг
Запустите API и проверьте валидатор:
- `POST /api/v1/config/validate`

## EN: VK prerequisites

Required values:
- `VK_ACCESS_TOKEN`
- `VK_ALLOWED_PEERS`

Steps:
1. Create a VK app/community bot in VK developer settings.
2. Generate a token with messaging permissions.
3. Keep the real token only in local `.env` (never commit).
4. Resolve `peer_id` from logs or VK API conversation endpoints.
5. Validate runtime config through `POST /api/v1/config/validate`.

## Security notes
- Never commit `.env`, access tokens, passwords, DSN with credentials, or private keys.
- If a token was exposed, rotate it immediately and invalidate the old one.
