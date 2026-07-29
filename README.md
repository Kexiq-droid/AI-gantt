# BioPlan

Приложение для **контроля проектов**: иерархический план-график (Gantt), статусы и исполнители, Excel и ассистент на естественном языке, который правит план через те же MCP-tools, что доступны из Cursor.

Стартует с демо-планом **VAX-B** (после `make seed` / «Сбросить демо»). Свой план — через импорт Excel или создание задач.

![BioPlan — контроль проектов через Gantt и чат-агента](docs/demo.gif)

Репозиторий: https://github.com/Kexiq-droid/AI-gantt

## Возможности

- Иерархический Gantt (фазы / задачи), zoom по дням и неделям, линия «Сегодня»
- Прогресс `%` на барах; у фаз — среднее по дочерним задачам
- Карточка задачи: название, описание, исполнитель, длительность, прогресс
- Чат-ассистент: сдвиги сроков, назначения, зависимости, создание задач, анализ загрузки
- Undo / Redo, очистка плана, журнал действий ассистента
- Импорт / экспорт Excel (колонки задания; `код`/`родитель` опциональны)

## Быстрый старт

```bash
git clone https://github.com/Kexiq-droid/AI-gantt.git
cd AI-gantt
cp .env.example .env
make backend-install
. .venv/bin/activate
make seed
make build
make up            # uvicorn :8100
```

Учётная запись после `make seed`:

| Логин | Пароль | Роль |
|-------|--------|------|
| `pm` | `pm12345` | editor |

После входа — сид-план вакцины **VAX-B**. Пример Excel: [examples/plan_vax_b_demo.xlsx](examples/plan_vax_b_demo.xlsx).

### Проверка за 3 минуты

1. Войти как `pm` → сид-Gantt VAX-B.
2. **Импорт Excel** → `examples/plan_vax_b_demo.xlsx` (или вложение в чат + «импортируй»).
3. В чат: `Сдвинь всю доклинику на 10 дней и назначь Иванова на все задачи фазы CMC`.
4. Summary + подсветка изменённых баров.
5. **← Отменить** при необходимости, **Экспорт Excel**.

Демо-ролик (сценарий): [docs/DEMO.md](docs/DEMO.md).

## Архитектура

```
React SPA  --HTTPS-->  FastAPI (auth, plans, excel, chat, jobs)
                          |-- domain: validate + apply_plan_patch (транзакция)
                          |-- chat: undo/redo/import — быстрые rules;
                          |         иначе LLM: snapshot → plan_commands → apply (≤3 ops);
                          |         без LLM — fallback на rules
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

Web-чат и Cursor используют **одну** MCP tool surface (`backend/app/services/mcp_runtime.py`): чат — in-process, IDE — stdio.

```json
{
  "mcpServers": {
    "bioplan": {
      "command": "/path/to/AI-gantt/.venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/AI-gantt",
      "env": {
        "PYTHONPATH": "/path/to/AI-gantt",
        "DATABASE_URL": "sqlite:////path/to/AI-gantt/data/bioplan.db",
        "BIOPLAN_MCP_USER": "pm"
      }
    }
  }
}
```

**Tools:** `get_plan_snapshot`, `validate_plan`, `apply_plan_patch` (max 3 ops, `dry_run`), `undo_plan`, `list_overloaded_assignees`  
**Resource:** `plan://current`  
**Prompt:** `golden_shift_preclinical`  

Excel import остаётся в web-чате (не в MCP), по ТЗ.

## Makefile

- `make up` — build frontend + uvicorn :8100
- `make seed` — пользователь `pm` + демо-план VAX-B
- `make test` — pytest
- `make build` — сборка SPA в `frontend/dist`

## Деплой

- systemd: `bioplan-api.service`
- nginx → `127.0.0.1:8100`

Подробности: [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Инженерные решения

См. [docs/DECISIONS.md](docs/DECISIONS.md): свой Gantt; LLM + fallback; SQLite + in-process jobs; graceful degradation; журнал ассистента; reset-seed (очистка плана).

## Golden prompts

(удобно прогонять после импорта `examples/plan_vax_b_demo.xlsx`)

1. Сдвинь всю доклинику на 10 дней
2. Назначь Иванова на все задачи фазы CMC
3. Добавь задачу «Резервный анализ антигена» в доклинику на 5 дней после T2.3
4. Сделай предшественником для T3.2 задачу T2.4
5. Отмени последнее
6. Кто перегружен по числу задач?
7. Уточни описания всех задач регуляторики: добавь префикс [REG]
8. Поставь T2.1 на 60%
9. Сдвинь коммерческое производство на 14 дней
10. Назначь Васильеву на все задачи регистрации

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
- Пример Excel: [examples/plan_vax_b_demo.xlsx](examples/plan_vax_b_demo.xlsx)
