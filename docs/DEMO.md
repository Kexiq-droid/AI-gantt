# Демо-ролик

Готовый ролик: [demo.gif](demo.gif) — основные действия с ИИ-ассистентом на плане проекта.

Пересъёмка (Playwright Chromium, ffmpeg, API на `:8100` с рабочим LLM):

```bash
cd /path/to/AI-gantt
. .venv/bin/activate
make build
# uvicorn / systemctl — чтобы :8100 отвечал
python scripts/record_demo.py   # пишет docs/demo.gif
```

## Сценарий

1. Вход `pm` / `pm12345`
2. **Сбросить демо** → план VAX-B
3. Чат: сдвиг доклиники, назначение CMC, создание задачи, «кто перегружен?»
4. «Отмени последнее» + UI undo + **Журнал ассистента**

Ролик встроен в [README.md](../README.md).
