# VK Setup Guide (RU + EN)

## RU: что вводить в setup wizard

Запуск мастера:
```bash
vk-openclaw setup
```

В Linux мастер печатает подсказки в формате `RU / EN`.

Интерактивный setup запрашивает:
- `VK_ACCESS_TOKEN` (открытый copy/paste ввод),
- `VK_ALLOWED_PEERS`.

И автоматически задает:
- `ADMIN_API_TOKEN` (генерируется и показывается один раз),
- `PERSISTENCE_MODE=file`,
- `OPENCLAW_COMMAND` (wrapper/local default),
- `FREE_TEXT_ASK_ENABLED=true`.

### 1. Как получить `VK_ACCESS_TOKEN`
1. Создайте или откройте сообщество VK.
2. Перейдите: `Управление -> Дополнительно -> Работа с API`.
3. Нажмите `Создать ключ`.
4. Полученный ключ используйте как `VK_ACCESS_TOKEN`.
5. Храните токен только локально в `.env.local`.

Пример:
```env
VK_ACCESS_TOKEN=vk1.a.real_token_value
```

### 2. Как получить `VK_ALLOWED_PEERS`
- Для ЛС укажите ID пользователя.
- Для беседы укажите `peer_id`.

Пример:
```env
VK_ALLOWED_PEERS=123456789
```

### 3. Pairing после setup
1. Setup helper запрашивает pair code.
2. Если в `VK_ALLOWED_PEERS` несколько peer_id, helper просит `PAIRING_PEER_ID`.
3. Отправьте в VK: `/pair <code>`.
4. Helper проверяет, что peer появился в `GET /api/v1/pairing/peers`.
5. После pairing проверьте `/status`, затем `/ask привет`.

### 4. Частые проблемы
1. `token required` / `Access denied`:
- проверьте `VK_ACCESS_TOKEN` и права ключа.

2. `/ask` не отвечает:
- проверьте, что peer paired;
- проверьте worker логи.

3. `Temporary failure in name resolution`:
- нестабильный DNS (часто WSL);
- примените DNS fix из `README.md` / `docs/install.md`.

4. `Failed to connect to bus`:
- `systemd --user` недоступен в текущей сессии;
- используйте fallback запуск из `docs/install.md`.

## EN: setup values and flow

Run:
```bash
vk-openclaw setup
```

Interactive setup asks for:
- `VK_ACCESS_TOKEN` (visible paste input),
- `VK_ALLOWED_PEERS`.

Setup auto-configures:
- `ADMIN_API_TOKEN` (auto-generated),
- `PERSISTENCE_MODE=file`,
- `OPENCLAW_COMMAND` (wrapper/local default),
- `FREE_TEXT_ASK_ENABLED=true`.

Recommended flow:
1. Create VK community API key:
   `Manage -> Advanced -> API access -> Create key`.
2. Set correct peer id (DM user id or chat peer_id).
3. Complete pairing helper.
4. Validate in VK: `/status`, then `/ask hello`.

Pairing is VK-first:
- worker verifies `/pair <code>` from VK,
- helper confirms pairing using `GET /api/v1/pairing/peers`.

Security notes:
- never commit `.env` / `.env.local`,
- rotate token immediately if exposed.
