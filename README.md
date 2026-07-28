# BioPlan

AI-native Gantt для R&D-планирования (тестовое задание под стек React + FastAPI + MCP + LLM).

**EN:** BioPlan is an interactive hierarchical Gantt with seeded pharma R&D data, Excel import/export, and a chat agent that edits the plan via MCP-compatible tools. Deploy target: `https://bio.2alexs.ru`.

Демо-ролик (черновик-раскадровка): [docs/demo.gif](docs/demo.gif) — замените на запись реального UI по [docs/DEMO.md](docs/DEMO.md).

## Быстрый старт

```bash
cd /var/CRM_test
cp .env.example .env   # при необходимости
make backend-install   # один раз
. .venv/bin/activate
make seed
make build
make up                # или: systemctl start bioplan-api
```

Демо-пользователи:

| Логин | Пароль |
|-------|--------|
| `pm` | `pm12345` |
| `viewer` | `viewer123` |

Проверка за 3 минуты (wow-path):

1. Открыть приложение → войти как `pm` → виден сид-Gantt BIO-X.
2. Загрузить `examples/plan_biokad_demo.xlsx`.
3. В чат: `Сдвинь всю доклинику на 10 дней и назначь Иванова на все задачи фазы CMC`.
4. Summary + подсветка баров.
5. Undo.
6. Excel ↓.

## Архитектура

```
React SPA  --HTTPS-->  FastAPI (auth, plans, excel, chat, jobs)
                          |-- domain: validate + apply_plan_patch (транзакция)
                          |-- agent loop (DeepSeek / OpenAI) вызывает те же tools
                          `-- SQLite

mcp_server/  (stdio MCP)  — те же tools для Cursor
```

Инварианты плана: уникальные коды; валидный parent без циклов; FS без циклов; duration > 0 у листьев; apply только после validate, атомарно.

## LLM

- По умолчанию: **Timeweb Cloud AI** (`LLM_PROVIDER=timeweb`) — OpenAI-compatible endpoint агента.
- Запасные: `deepseek`, `openai`.
- Без ключа приложение **работает** (Gantt/Excel/undo); чат сообщает, что ассистент недоступен.

Пример `.env` для Timeweb:

```
LLM_PROVIDER=timeweb
TIMEWEB_API_KEY=...          # ключ доступа агента из панели Timeweb
TIMEWEB_BASE_URL=https://agent.timeweb.cloud/api/v1/cloud-ai/agents/<AGENT_ID>/v1
TIMEWEB_MODEL=deepseek/deepseek-v4-flash
```

После смены `.env`: `systemctl restart bioplan-api`.

## MCP из Cursor

```json
{
  "mcpServers": {
    "bioplan": {
      "command": "/var/CRM_test/.venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "/var/CRM_test",
      "env": {
        "PYTHONPATH": "/var/CRM_test",
        "BIOPLAN_MCP_USER": "pm"
      }
    }
  }
}
```

Tools: `get_plan_snapshot`, `validate_plan`, `apply_plan_patch`.

## Makefile

- `make up` — build frontend + uvicorn :8100  
- `make seed` — пользователи + фарм-план  
- `make test` — pytest  

## Деплой (этот VPS)

- systemd: `bioplan-api.service`
- nginx: `bio.2alexs.ru` → `127.0.0.1:8100`
- **DNS:** нужна A-запись `bio.2alexs.ru` → IP сервера (сейчас у регистратора NXDOMAIN). После появления DNS:

```bash
certbot certonly --webroot -w /var/lib/letsencrypt -d bio.2alexs.ru \
  --account b9b7f688b6a806a1941007d73c6e4784
systemctl reload nginx
```

Пока DNS нет — стоит временный self-signed сертификат.

Подробности: [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Инженерные решения

См. [docs/DECISIONS.md](docs/DECISIONS.md): свой Gantt; DeepSeek+fallback; SQLite + in-process jobs; graceful degradation; Agent Trace; reset-seed.

## Golden prompts

1. Сдвинь всю доклинику на 10 дней  
2. Назначь Иванова на все задачи фазы CMC  
3. Добавь задачу «Резервный анализ образцов» в доклинику на 5 дней после T2.3  
4. Сделай предшественником для T3.1 задачу T2.4  
5. Отмени последнее  
6. Кто перегружен по числу задач?  
7. Уточни описания всех задач регуляторики: добавь префикс [REG]  

## Как использовались AI-ассистенты

- Cursor использовался для ускорения каркаса (FastAPI/React), генерации сида и черновиков UI.
- Архитектура, срезы P0/P1, контракт MCP tools, инварианты и критерии демо зафиксированы вручную в `TECHNICAL_SPEC.md` до кода.
- Качество агента проверяется журналом (`/api/agent/*`), pytest на validate/excel и прогоном golden prompts на стенде с живым ключом.

## Документы

- [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md)  
- [ROADMAP_TO_PRODUCTION.md](ROADMAP_TO_PRODUCTION.md)  
- [docs/DECISIONS.md](docs/DECISIONS.md)  
- [docs/RUNBOOK.md](docs/RUNBOOK.md)  
