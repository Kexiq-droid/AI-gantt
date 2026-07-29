# Demo recording checklist

Готовый ролик: [demo.gif](demo.gif) (~56 с, 960×600) — основные действия **с агентом**.

Пересъёмка автоматически (нужны Playwright Chromium, ffmpeg, поднятый API на `:8100` с рабочим LLM):

```bash
cd /var/CRM_test
. .venv/bin/activate
make build
systemctl restart bioplan-api   # или make up
python scripts/record_demo.py   # пишет docs/demo.gif
```

Вручную: OBS / Peek / Chrome DevTools Recorder (~3 мин).

## Сценарий ролика (агент)

1. Login `pm` / `pm12345`
2. **Сбросить демо** → чистый сид VAX-B на Gantt
3. Чат: `Сдвинь всю доклинику на 10 дней` (массовый shift фазы)
4. Чат: `Назначь Иванова на все задачи фазы CMC` (массовый reassign)
5. Чат: `Добавь задачу «Резервный анализ антигена» в доклинику на 5 дней после T2.3` (create + deps)
6. Чат: `Кто перегружен по числу задач?` (read-only анализ)
7. Чат: `Отмени последнее` (undo через агента)
8. **← Отменить** (UI undo) + краткий **Журнал ассистента**

Файл: `docs/demo.gif` — встроен в README репозитория.
