# Demo recording checklist

Готовый ролик: [demo.gif](demo.gif) (~56 с, 960×600) — основные действия **с агентом** на примере плана из Excel.

Пересъёмка автоматически (нужны Playwright Chromium, ffmpeg, поднятый API на `:8100` с рабочим LLM):

```bash
cd /var/CRM_test
. .venv/bin/activate
make build
systemctl restart bioplan-api   # или make up
python scripts/record_demo.py   # пишет docs/demo.gif
```

## Сценарий ролика (агент)

1. Login `pm` / `pm12345`
2. **Очистить план** → пустой проект
3. **Импорт Excel** → `examples/plan_vax_b_demo.xlsx`
4. Чат: `Сдвинь всю доклинику на 10 дней`
5. Чат: `Назначь Иванова на все задачи фазы CMC`
6. Чат: `Добавь задачу «Резервный анализ антигена» в доклинику на 5 дней после T2.3`
7. Чат: `Кто перегружен по числу задач?`
8. Чат: `Отмени последнее` + UI undo + **Журнал ассистента**

Файл: `docs/demo.gif` — встроен в README репозитория.
