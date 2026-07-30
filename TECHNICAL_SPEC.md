# BioPlan — что сдано

Короткий scope сдачи. Полное исходное ТЗ (архив): [docs/TECHNICAL_SPEC_FULL.md](docs/TECHNICAL_SPEC_FULL.md).

## Продукт

**BioPlan** — контроль проектной деятельности с ИИ-ассистентом: иерархический Gantt, Excel, чат на естественном языке. Демо-сценарий — план вакцины **VAX-B**.

Стек: React (Vite/TS) + FastAPI + SQLite + MCP + LLM (**DeepSeek V4 Flash** достаточно).

Запуск: [README.md](README.md) (Ubuntu / Windows). Пилот: [ROADMAP_TO_PRODUCTION.md](ROADMAP_TO_PRODUCTION.md). ADR: [docs/DECISIONS.md](docs/DECISIONS.md).

## Delivered (MVP)

| Область | В сдаче |
|---------|---------|
| Gantt | Иерархия, зависимости FS, zoom день/неделя, «Сегодня», DnD сдвига, прогресс % |
| Задачи | Модалка, создание (в т.ч. ПКМ), исполнители, undo/redo ≤10 |
| Excel | Импорт/экспорт; sample `examples/plan_vax_b_demo.xlsx` |
| Ассистент | Чат NL → rules и/или LLM → `plan_commands` / `apply_plan_patch`; summary + highlight |
| MCP | Одна tool surface: web **in-process**, Cursor **stdio** (`mcp_server`) |
| Надёжность | Validate-before-apply, atomic patch, лимит batch, mass-delete confirm, single-flight jobs |
| UX | Тема light/dark, журнал ассистента + rating, «Сбросить демо», UI action log (агент) |
| Auth | `pm` / `pm12345` (editor). Роль `viewer` в коде/тестах, не в seed |
| Качество | pytest (backend), Vitest (frontend), Playwright e2e (happy-path) |
| Docs | README, Roadmap Now/Next/Later, ADR, Runbook, demo.gif |

## English summary

BioPlan is a project-control web app with an AI chat that edits a hierarchical Gantt via a shared MCP tool surface (in-process for the web agent, stdio for Cursor). Includes Excel I/O, undo, agent journal, and seeded VAX-B demo plan. Default LLM: DeepSeek V4 Flash.

## Golden prompts (smoke)

1. Сдвинь всю доклинику на 10 дней  
2. Назначь Иванова на все задачи фазы CMC  
3. Добавь задачу «Резервный анализ антигена» в доклинику на 5 дней после T2.3  
4. Отмени последнее  
5. Кто перегружен по числу задач?

Полный список G1–G10 — в архиве ТЗ.

## Сознательные упрощения

- SQLite + jobs в процессе uvicorn (не Postgres / очередь)  
- Один план на пользователя  
- Внешний LLM (не on-prem)  
- Нет паритета с MS Project  

Детали и порядок закрытия — в Roadmap.
