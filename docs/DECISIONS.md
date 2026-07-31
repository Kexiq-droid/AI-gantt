# Architecture decisions

## ADR-001: Свой Gantt вместо библиотеки

**Context:** Нужны иерархия, FS-зависимости, highlight после агента, DnD и контроль UI под lab/clinical стиль за 2 дня. `frappe-gantt` слабо закрывает иерархию/deps.

**Decision:** Реализовать лёгкий Gantt на CSS + SVG в React.

**Consequences:** Больше своего кода, зато полный контроль UX и лицензий. Сложный MS Project-паритет не цель MVP.

## ADR-002: DeepSeek V4 Flash (+ Timeweb / OpenAI fallback)

**Context:** Требуется LLM через API и tool calling. Бюджет и скорость важны; для демо нужна страховка.

**Decision:** По умолчанию `LLM_PROVIDER=deepseek` и модель **DeepSeek V4 Flash** — её достаточно для задач ассистента. Запасные провайдеры: `timeweb` (OpenAI-compatible gateway), `openai`. Thinking mode выключен.

**Consequences:** Нужна серверная валидация патчей. Внешний LLM — compliance-долг для чувствительных контуров (см. Roadmap).

## ADR-003: SQLite + in-process jobs

**Context:** Один VPS, демо, срок 2 дня.

**Decision:** SQLite файл + `asyncio` background tasks в uvicorn, состояние job в таблице `agent_jobs`.

**Consequences:** Не переживает multi-worker и рестарты mid-job надёжно. Закрытие — в [ROADMAP_TO_PRODUCTION.md](../ROADMAP_TO_PRODUCTION.md) раздел **Now** (Postgres + очередь/worker).

## ADR-004: Shared MCP tool runtime (in-process + stdio)

**Context:** Нужен «настоящий» MCP и тот же контракт для UI-агента и Cursor.

**Decision:** Доменная tool-логика в `backend/app/services/mcp_runtime.py` (`execute_tool`). FastAPI-чат вызывает runtime **in-process** (низкая латентность, без subprocess на каждый tool-call). `mcp_server` экспортирует те же public tools (+ resource `plan://current`, prompt `golden_shift_preclinical`) по **stdio** для Cursor. `apply_plan_patch` поддерживает `dry_run`; лимит `MAX_BATCH_OPS=60` — агент применяет
весь WBS одним apply (без UX «по 3»). После `create`/`set_deps`/`delete` даты
пересчитываются через `compute_schedule` (каскад на Ганте). Одиночный `create` без
`parent` / `after|position` / `predecessors` → `need_clarification`. Нельзя сдать только
фазы без листьев. Замена непустого плана = delete-all + WBS после одного «да».

**Consequences:** Один источник правды по инвариантам; демо надёжнее, чем MCP-client через stdio на каждый chat job. На защите формулировка: «UI и IDE — одна MCP tool surface, разный транспорт».
