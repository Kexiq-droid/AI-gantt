# BioPlan

AI-native Gantt для R&D-планирования (тестовое задание: React + FastAPI + MCP + LLM).

**Демо:** https://bio.2alexs.ru  
**Репозиторий:** https://github.com/Kexiq-droid/AI-gantt

Интерактивный иерархический Gantt с сидированным фарм-планом, импортом/экспортом Excel и чат-ассистентом, который правит план на естественном языке. Те же tools доступны через MCP (Cursor).

Демо-ролик: [docs/demo.gif](docs/demo.gif) (~31 с) — логин → сид-Gantt → импорт Excel → правка через чат → отмена → экспорт → журнал. Чеклист: [docs/DEMO.md](docs/DEMO.md).

## Быстрый старт

```bash
cd /var/CRM_test   # или клон репозитория
cp .env.example .env
make backend-install
. .venv/bin/activate
make seed
make build
make up            # или: systemctl start bioplan-api
```

Демо-пользователи:

| Логин | Пароль |
|-------|--------|
| `pm` | `pm12345` |
| `viewer` | `viewer123` |

### Проверка за 3 минуты (wow-path)

1. Открыть https://bio.2alexs.ru → войти как `pm` → виден сид-Gantt BIO-X.
2. **Импорт Excel** → `examples/plan_biokad_demo.xlsx` (или прикрепить файл в чат и написать «импортируй»).
3. В чат: `Сдвинь всю доклинику на 10 дней и назначь Иванова на все задачи фазы CMC`.
4. Summary + подсветка изменённых баров на диаграмме.
5. **← Отменить** при необходимости.
6. **Экспорт Excel**.

## Что умеет

- Иерархический Gantt (фазы / задачи), zoom по дням и неделям, линия «Сегодня».
- Прогресс `%` на барах (заливка + отставание относительно «сегодня»); у фаз — среднее по детям.
- Модалка задачи: название, описание, исполнитель, длительность, прогресс.
- Чат-ассистент: сдвиги, длительности, зависимости, новые задачи, переназначение, импорт Excel из вложения.
- Undo / Redo, сброс демо-плана, журнал ассистента.
- Excel: колонки задания (`задача`, `описание`, `исполнитель`, `длительность`, `предшественники`) + код, даты, родитель, `% выполнения`.

## Архитектура

```
React SPA  --HTTPS-->  FastAPI (auth, plans, excel, chat, jobs)
                          |-- domain: validate + apply_plan_patch (транзакция)
                          |-- agent loop (Timeweb / DeepSeek / OpenAI) → те же tools
                          `-- SQLite

mcp_server/  (stdio MCP)  — те же tools для Cursor
```

Инварианты плана: уникальные коды; валидный parent без циклов; FS без циклов; duration > 0 у листьев; apply только после validate, атомарно.

## LLM

- По умолчанию: **Timeweb Cloud AI** (`LLM_PROVIDER=timeweb`) — OpenAI-compatible endpoint.
- Запасные: `deepseek`, `openai`.
- Без ключа приложение **работает** (Gantt / Excel / undo); чат сообщает, что ассистент недоступен.

Пример `.env` для Timeweb:

```
LLM_PROVIDER=timeweb
TIMEWEB_API_KEY=...
TIMEWEB_BASE_URL=https://agent.timeweb.cloud/api/v1/cloud-ai/agents/<AGENT_ID>/v1
TIMEWEB_MODEL=deepseek/deepseek-v4-flash
```

После смены `.env`: `systemctl restart bioplan-api`.

## MCP из Cursor

```json
{
  "mcpServers": {
    "bioplan": {
      "command": "/path/to/AI-gantt/.venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/AI-gantt",
      "env": {
        "PYTHONPATH": "/path/to/AI-gantt",
        "BIOPLAN_MCP_USER": "pm"
      }
    }
  }
}
```

Tools: `get_plan_snapshot`, `validate_plan`, `apply_plan_patch` (и связанные операции патча / импорта).

## Makefile

- `make up` — build frontend + uvicorn :8100
- `make seed` — пользователи + фарм-план
- `make test` — pytest
- `make build` — сборка SPA в `frontend/dist`

## Деплой

- URL: **https://bio.2alexs.ru**
- systemd: `bioplan-api.service`
- nginx → `127.0.0.1:8100`

Подробности: [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Инженерные решения

См. [docs/DECISIONS.md](docs/DECISIONS.md): свой Gantt; LLM + fallback; SQLite + in-process jobs; graceful degradation; журнал ассистента; reset-seed.

## Golden prompts

1. Сдвинь всю доклинику на 10 дней
2. Назначь Иванова на все задачи фазы CMC
3. Добавь задачу «Резервный анализ образцов» в доклинику на 5 дней после T2.3
4. Сделай предшественником для T3.1 задачу T2.4
5. Отмени последнее
6. Кто перегружен по числу задач?
7. Уточни описания всех задач регуляторики: добавь префикс [REG]
8. Поставь T2.1 на 60%

## Как использовались AI-ассистенты

- **Cursor** — каркас FastAPI/React, сид данных, UI Gantt/чата, Excel I/O, агентский loop, MCP-сервер, деплой и документация.
- Архитектура, срезы P0/P1, контракт tools, инварианты и критерии демо зафиксированы в `TECHNICAL_SPEC.md` до/параллельно с кодом.
- Качество агента: журнал (`/api/agent/*`), pytest (validate/excel), прогон golden prompts на стенде с живым ключом.
- UI-копирайт и мелкий UX (модалка, прогресс, линия «сегодня») итеративно правились с ассистентом по фидбеку на стенде.

## Документы

- [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md)
- [ROADMAP_TO_PRODUCTION.md](ROADMAP_TO_PRODUCTION.md)
- [docs/DECISIONS.md](docs/DECISIONS.md)
- [docs/RUNBOOK.md](docs/RUNBOOK.md)
- [docs/DEMO.md](docs/DEMO.md)
- Пример Excel: [examples/plan_biokad_demo.xlsx](examples/plan_biokad_demo.xlsx)
