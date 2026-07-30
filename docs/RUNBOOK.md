# Runbook — BioPlan (Ubuntu-сервер)

Локальный запуск на Windows / Linux без systemd — в [README.md](../README.md). Ниже — эксплуатация стенда на Ubuntu.

## Сервисы

| Что | Как |
|-----|-----|
| API | `systemctl status bioplan-api` |
| Рестарт API | `systemctl restart bioplan-api` |
| Логи | `journalctl -u bioplan-api -f` |
| nginx | `nginx -t && systemctl reload nginx` |
| Health | `curl -s http://127.0.0.1:8100/api/health` |

Ожидаемый health: `{"status":"ok","db":"ok","llm":"ok"}` (при настроенном ключе).

## Каталоги (пример стенда)

- Код: каталог клона (на стенде часто `/var/CRM_test`)
- БД: по умолчанию `<repo>/data/bioplan.db` (или `DATABASE_URL` из `.env`)
- Статика: `<repo>/frontend/dist` (отдаёт FastAPI)
- env: `<repo>/.env`

## Смена LLM

1. В `.env`: `LLM_PROVIDER=deepseek` (или `timeweb` / `openai`) и ключ.
2. `systemctl restart bioplan-api` (или перезапуск uvicorn).
3. Проверить `"llm":"ok"` в `/api/health`.

Для задач ассистента достаточно **DeepSeek V4 Flash**.

## Сброс демо-плана

```bash
cd /path/to/AI-gantt && . .venv/bin/activate && make seed
# или в UI: «Сбросить демо»
```

Восстанавливает пользователя `pm` и план VAX-B, очищает чат/журнал.

## TLS / DNS (публичный стенд)

Если есть домен (пример: `bio.2alexs.ru`):

- A-запись → IP сервера
- сертификат Let's Encrypt + nginx → `127.0.0.1:8100`
- в `.env`: `COOKIE_SECURE=true`, `CORS_ORIGINS=https://ваш.домен`

## Типичные сбои

| Симптом | Действие |
|---------|----------|
| Чат: ассистент недоступен | Нет ключа / `llm: degraded` — добавить `DEEPSEEK_API_KEY` (или Timeweb) |
| 401 после логина по HTTP | `COOKIE_SECURE=true` на HTTP — поставьте `false` локально |
| Пустой / «чужой» план | `make seed` или «Сбросить демо» |
| nginx 404 на HTTPS | открывать по имени из сертификата (SNI) |
