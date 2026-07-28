# Demo recording checklist

Готовый ролик: [demo.gif](demo.gif) (~31 с, 960×600, сценарий ниже).

Пересъёмка автоматически (нужны Playwright Chromium, ffmpeg, поднятый API на `:8100` с рабочим LLM):

```bash
cd /var/CRM_test
. .venv/bin/activate
make build
systemctl restart bioplan-api   # или make up
python scripts/record_demo.py   # пишет docs/demo.gif
```

Вручную: OBS / Peek / Chrome DevTools Recorder (~3 мин).

## Сценарий ролика

1. Login `pm` / `pm12345`
2. Показать сид-Gantt (линия «Сегодня», прогресс на барах)
3. **Импорт Excel** → `examples/plan_biokad_demo.xlsx`
4. Чат: `Сдвинь всю доклинику на 10 дней и назначь Иванова на все задачи фазы CMC`
5. Ответ ассистента + подсветка изменённых баров
6. **← Отменить**
7. **Экспорт Excel**
8. Краткий взгляд в **Журнал ассистента**

Файл: `docs/demo.gif` — ссылка в README. Живое демо: https://bio.2alexs.ru
