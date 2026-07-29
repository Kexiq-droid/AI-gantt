# Architecture decisions

## ADR-001: Свой Gantt вместо библиотеки

**Context:** Нужны иерархия, FS-зависимости, highlight после агента, DnD и контроль UI под lab/clinical стиль за 2 дня. `frappe-gantt` слабо закрывает иерархию/deps.

**Decision:** Реализовать лёгкий Gantt на CSS + SVG в React.

**Consequences:** Больше своего кода, зато полный контроль UX и лицензий. Сложный MS Project-паритет не цель MVP.

## ADR-002: Timeweb Cloud AI (+ DeepSeek / OpenAI fallback)

**Context:** Требуется LLM через API и tool calling. Бюджет и скорость важны; для демо нужна страховка.

**Decision:** По умолчанию `LLM_PROVIDER=timeweb` (OpenAI-compatible endpoint агента Timeweb). Запасные провайдеры: `deepseek`, `openai`. Thinking mode выключен.

**Consequences:** Нужна серверная валидация патчей. Для продакшена фармы внешний провайдер — compliance-долг (см. Roadmap).

## ADR-003: SQLite + in-process jobs

**Context:** Один VPS, демо, срок 2 дня.

**Decision:** SQLite файл + `asyncio` background tasks в uvicorn, состояние job в таблице `agent_jobs`.

**Consequences:** Не переживает multi-worker и рестарты mid-job надёжно. В Roadmap — очередь и Postgres.

## ADR-004: Shared MCP tool runtime (in-process + stdio)

**Context:** Нужен «настоящий» MCP и тот же контракт для UI-агента и Cursor.

**Decision:** Доменная tool-логика в `backend/app/services/mcp_runtime.py` (`execute_tool`). FastAPI-чат вызывает runtime **in-process** (низкая латентность, без subprocess на каждый tool-call). `mcp_server` экспортирует те же public tools (+ resource `plan://current`, prompt `golden_shift_preclinical`) по **stdio** для Cursor. `apply_plan_patch` поддерживает `dry_run` и лимит `MAX_BATCH_OPS=3`.

**Consequences:** Один источник правды по инвариантам; демо надёжнее, чем MCP-client через stdio на каждый chat job. На защите формулировка: «UI и IDE — одна MCP tool surface, разный транспорт».
