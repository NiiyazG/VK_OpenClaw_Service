# AI Handoff (2026-03-29)

## Проект
Работали с репозиторием: `NiiyazG/VK_OpenClaw_Service` (не путать с `vk-openclaw-service`).
Локально использовалась рабочая копия в WSL: `~/VK_OpenClaw_Service`.

## Что уже сделано
1. Исправили запуск воркера:
   - `vk-openclaw-worker` теперь запускается из `.venv`.
2. Починили токен:
   - `VK_ACCESS_TOKEN` был пустой, заполнили.
3. Проверили доступ к VK API:
   - ошибка `token required` ушла.
4. Нашли правильный `peer_id` через VK API:
   - `1067587895`.
5. Обновили allowlist:
   - `VK_ALLOWED_PEERS=1067587895`.
6. Воркер начал обрабатывать сообщения:
   - в логах `processed > 0`.
7. Pairing code сгенерирован через API:
   - код `7NUXZARD` (на момент работы).
8. Статус по state-файлам:
   - `state/checkpoints.json`: `last_committed_message_id` дошел до `159`.
   - `state/audit.json`: много `message_processed`, есть `action: "pair"`.
   - `state/pairing.json`: `paired_peers` пустой, `consumed_at: null` (pairing не завершен).

## Текущая проблема
В VK `/help` работает, но `/ask ...` не работает, потому что peer еще не считается paired.

## Что делать дальше (первым делом)
1. Проверить pairing напрямую API:
   - `POST /api/v1/pairing/verify` с `peer_id=1067587895` и актуальным code.
2. Если verify неуспешен:
   - сгенерировать новый code (`POST /api/v1/pairing/code` с Bearer `$ADMIN_API_TOKEN`),
   - отправить в VK: `/pair <NEW_CODE>`.
3. Проверить `state/pairing.json`:
   - `paired_peers` должен содержать `1067587895`,
   - `consumed_at` должен стать не `null`.
4. После этого проверить в VK:
   - `/status`
   - `/ask привет`

## Важные замечания
- Иногда в WSL всплывал DNS сбой:
  - `Temporary failure in name resolution`.
- API и worker должны быть запущены с одинаковым `.env`:
  - `set -a; source .env; set +a`.
