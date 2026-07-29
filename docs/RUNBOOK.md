# Runbook — BioPlan

## Сервисы

| Что | Как |
|-----|-----|
| API | `systemctl status bioplan-api` |
| Рестарт API | `systemctl restart bioplan-api` |
| Логи | `journalctl -u bioplan-api -f` |
| nginx | `nginx -t && systemctl reload nginx` |
| Health | `curl -s http://127.0.0.1:8100/api/health` |

## Каталоги

- Код: `/var/CRM_test`
- БД: путь из `DATABASE_URL` (по умолчанию `/var/CRM_test/data/bioplan.db`)
- Статика: `/var/CRM_test/frontend/dist` (отдаёт FastAPI)
- env: `/var/CRM_test/.env`

## Смена LLM

1. Править `.env`: `LLM_PROVIDER`, ключи, модель.
2. `systemctl restart bioplan-api`
3. Проверить `"llm":"ok"` в `/api/health`.

## Очистка плана

```bash
cd /var/CRM_test && . .venv/bin/activate && PYTHONPATH=/var/CRM_test make seed
# или кнопка «Очистить план» в UI (пустой проект)
```

## TLS / DNS

A-запись `bio.2alexs.ru` → `186.246.30.20`.  
Сертификат Let's Encrypt: `/etc/letsencrypt/live/bio.2alexs.ru/` (автопродление через certbot timer).

Перевыпуск при необходимости:

```bash
certbot certonly --webroot -w /var/lib/letsencrypt -d bio.2alexs.ru \
  --account b9b7f688b6a806a1941007d73c6e4784
systemctl reload nginx
```

## Типичные сбои

| Симптом | Действие |
|---------|----------|
| Чат: ассистент недоступен | Нет ключа / `llm: degraded` — добавить ключ |
| 401 после логина | `COOKIE_SECURE=true` требует HTTPS |
| Пустой план | ожидаемо после `make seed` / «Очистить план»; импорт Excel или создание задач |
| nginx 404 на HTTPS без SNI | Открывать по имени хоста из сертификата |
