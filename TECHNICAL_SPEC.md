# BioPlan — Technical Specification

**Product:** BioPlan — AI-native interactive Gantt for R&D project planning  
**Target:** АО «БИОКАД» test assignment (Full-stack AI-native, React + FastAPI + MCP + LLM)  
**Deploy:** `https://Bio.2alexs.ru`  
**Timeline:** 2 days (MVP with explicit cut-line)

---

## English summary

BioPlan is an internal web app: open the page → see a seeded hierarchical Gantt (pharma R&D plan) → edit the plan in bulk via a natural-language chat powered by an LLM that calls a real MCP server → changes appear on the diagram immediately (with change summary + bar highlight). Users can upload/export Excel, open a task modal, drag bars, undo up to 10 steps, and continue agent jobs after closing the tab (chat history + toast on return). Stack: React (Vite/TS), FastAPI, SQLite, MCP, DeepSeek V4 Flash (OpenAI-compatible fallback). Auth: login/password (seeded users). UI in Russian; README in RU + EN summary. This document is the single source of truth for scope, architecture, agent contract, demo script, and definition of done.

---

## 1. Контекст и цель

### 1.1 Зачем продукт

В фарм-R&D планы живут в Excel и «ручных» правках. BioPlan даёт:

1. Наглядный иерархический Gantt с зависимостями.
2. Массовые правки на естественном языке (сдвиг фаз, переназначение, зависимости).
3. Round-trip Excel без потери структуры.
4. Контроль: summary изменений, подсветка, undo, валидация до commit.

### 1.2 Связь с вакансией

Роль — full-cycle AI-native: потребность → продукт → деплой → объяснение решений. Тестовое проверяет React, FastAPI, MCP, LLM-агента и production-мышление (Roadmap). BioPlan демонстрирует ownership: имя продукта, фарм-сценарий, MCP как переиспользуемая AI-инфраструктура (тот же сервер можно подключить из Cursor).

### 1.3 Персона

Руководитель проекта / PM в R&D: правит план перед статусом, загружает Excel от коллег, просит агента «сдвинь доклинику на 10 дней».

---

## 2. Приоритеты: P0 / P1 / cut-line

### 2.1 P0 — без этого не сдаём

| # | Требование |
|---|------------|
| P0.1 | Сид фарма-плана + иерархический Gantt (дерево, зависимости, zoom дни/недели) |
| P0.2 | Чат-агент через **реальный MCP** → apply → мгновенное обновление диаграммы |
| P0.3 | Summary изменений в чате + подсветка изменённых баров 3–5 сек |
| P0.4 | Excel import / export + sample-файл в репо |
| P0.5 | Login (2 сид-пользователя), UI на русском |
| P0.6 | Деплой `https://Bio.2alexs.ru` |
| P0.7 | README (архитектура, решения, AI-ассистенты, demo script) + `ROADMAP_TO_PRODUCTION.md` + demo gif/видео |
| P0.8 | Модалка задачи (детали на выбор реализации, см. §8) |
| P0.9 | **Graceful degradation:** без LLM работают Gantt/Excel/undo; чат — понятная ошибка (§6.7) |
| P0.10 | **Инварианты плана + транзакционный** `apply_plan_patch` (§6.8) |
| P0.11 | Корневой **Makefile** (`up` / `seed` / `test`) |
| P0.12 | **Сброс демо-плана** (API + кнопка «Сбросить демо» + `make seed`) |

### 2.2 P1 — повышает оценку

| # | Требование |
|---|------------|
| P1.1 | Background `agent_jobs`: переживают закрытие вкладки |
| P1.2 | История чата + toast при возврате (done/failed) |
| P1.3 | Undo стек до **10** шагов (чат + ручные правки) |
| P1.4 | Drag-and-drop сроков на диаграмме |
| P1.5 | Collapsible лог tool-calls в чате |
| P1.6 | В модалке: «последнее изменение» (человек / агент) |
| P1.7 | Минимум pytest: `validate_plan` + Excel round-trip |
| P1.8 | Переключатель **светлой / тёмной темы** (localStorage + CSS variables) |
| P1.9 | **Agent Trace** — журнал качества агента для разработчика/ревьюера (§8.7) |
| P1.10 | **ADR** — 2–3 решения в `docs/adr/` или `docs/DECISIONS.md` (§6.9) |
| P1.11 | **Runbook** — `docs/RUNBOOK.md` (§6.10) |

### 2.3 Cut-line (если отстаём к ~концу дня 1.5)

- DnD: не полируем; сроки правятся через чат.
- Undo: не ниже **5** шагов (цель всё же 10).
- Jobs: таблица + переживание refresh обязательны; toast можно упростить.
- Confirm только на delete / «очистить план», не на каждое действие.
- Тёмная тема: оставляем (дёшево на CSS variables).
- Agent Trace: минимум — персист полей в `agent_jobs` + раскрываемый JSON/детали у job; отдельную страницу метрик можно отложить.
- ADR → один файл `docs/DECISIONS.md`; Runbook → секция в README.
- **Не режем:** MCP-агент, summary+highlight, Excel, деплой, README, Roadmap, gif, graceful degradation, транзакции/инварианты, Makefile + сброс сида.

---

## 3. User stories и acceptance criteria

### US-1. Первый вход

**Как** PM, **хочу** сразу видеть план, **чтобы** не настраивать систему.

**Acceptance:** после логина загружен сид «Вывод препарата-кандидата на КИ»; фазы свёрнуты/развёрнуты; зависимости видны.

### US-2. Excel round-trip

**Как** PM, **хочу** загрузить свой Excel и выгрузить обратно.

**Acceptance:** колонки из §5; иерархия через `код`/`родитель`; предшественники — коды через запятую; после импорта Gantt обновлён; экспорт открывается в Excel/LibreOffice.

### US-3. Правка через чат

**Как** PM, **хочу** массово менять план на естественном языке.

**Acceptance:** сообщение → job → агент вызывает MCP → план обновлён без перезагрузки; в чате summary; bars подсвечены; при ошибке валидации план не меняется.

### US-4. Детали задачи

**Как** PM, **хочу** кликнуть задачу и увидеть детали.

**Acceptance:** модалка с полями §8; Escape/кнопка закрытия; focus trap базовый.

### US-5. Undo

**Как** PM, **хочу** откатить до 10 последних действий.

**Acceptance:** кнопка Undo + фраза в чате «отмени» / «отмени последнее»; стек общий для агента и UI.

### US-6. Фон

**Как** PM, **хочу** закрыть вкладку, пока агент думает, и увидеть результат позже.

**Acceptance:** job в БД; история чата восстанавливается; toast при `done`/`failed`, если завершилось в отсутствие UI.

### US-7. Auth

**Как** заказчик демо, **хочу** вход по логину/паролю.

**Acceptance:** без сессии API/UI плана недоступны; 2 пользователя в сиде и README; пароли не в git (только `.env.example` / README demo creds для тестового стенда — осознанно).

### US-8. Тема

**Как** пользователь, **хочу** переключать светлую и тёмную тему.

**Acceptance:** toggle в шапке; выбор сохраняется в `localStorage`; обе темы на CSS variables; контраст читаемый (WCAG AA по возможности); Gantt/чат/модалка корректны в обеих темах.

### US-9. Журнал качества агента

**Как** разработчик / ревьюер, **хочу** видеть трассировку прогонов агента и простые метрики качества.

**Acceptance:** для каждого job сохраняются prompt, tools, latency, validate, changes, error, model; UI «Журнал ассистента» со списком и деталями; видны агрегаты (% success, % validate fail, % undo после агента, avg latency); можно поставить 👍/👎 на ответ ассистента.

### US-10. Работа без LLM

**Как** PM / ревьюер, **хочу** пользоваться планом даже если AI недоступен.

**Acceptance:** при отсутствии ключа или ошибке провайдера логин, Gantt, Excel, undo работают; чат показывает понятное сообщение на русском; остальные API не 500 из‑за LLM.

### US-11. Сброс демо

**Как** ревьюер, **хочу** одним действием вернуть сид-план.

**Acceptance:** кнопка «Восстановить демо-план» (с confirm) и/или `make seed` пересоздают фарм-сид; стек undo можно очистить; wow-path снова воспроизводим.

---

## 4. Demo script (3 минуты) — wow-path

Чеклист для gif/видео и раздела README «Как проверить за 3 минуты»:

1. Открыть `https://Bio.2alexs.ru` → логин сид-пользователем → сразу виден сид-Gantt BioPlan.
2. Загрузить `examples/plan_vax_b_demo.xlsx` (чуть отличный от сида план) → диаграмма обновилась.
3. В чат:  
   `Сдвинь всю доклинику на 10 дней и назначь Иванова на все задачи фазы CMC`
4. Дождаться завершения → summary в чате + подсветка изменённых баров.
5. Undo → план откатился.
6. Экспорт Excel → файл скачался, колонки на месте.

Перед записью gif — прогон golden prompts (§7.4). При нестабильности DeepSeek Flash — временно `LLM_PROVIDER=openai` для записи; в README описать как operational practice.

---

## 5. Формат Excel и сид-данные

### 5.1 Колонки

Обязательные (из задания) + иерархия:

| Колонка | Тип | Описание |
|---------|-----|----------|
| `код` | string | Уникальный код задачи в плане (`P1`, `T1.2`) |
| `задача` | string | Название |
| `описание` | string | Текст |
| `исполнитель` | string | ФИО / роль; у фаз может быть пусто |
| `длительность` | int | Календарные дни (> 0 для листьев; у фаз — вычисляемо или сумма) |
| `дата начала` | date | Старт задачи (`DD.MM.YYYY` / ISO). При импорте имеет приоритет над авторасчётом |
| `дата конца` | date | Конец = начало + длительность. При импорте без длительности: `длительность = конец − начало` |
| `предшественники` | string | Коды через запятую (`T1,T3`); тип связи MVP: FS |
| `родитель` | string | Код родителя; пусто = корень |

Единица времени MVP: **календарные дни** (без праздников РФ — долг Roadmap).  
Если в Excel нет колонок дат — `start_date` считается через предшественников / `plan.start_date` (как раньше).  
Если даты заданы — импорт берёт их как есть.

### 5.2 Сид-сценарий

**Название плана:** Вакцина VAX-B: discovery → доклиника → CMC → КИ I–III → регистрация РФ → коммерческий выпуск

Фазы (упрощённо для 3-минутного демо, ~35 строк):

1. Discovery и целеполагание  
2. Доклинические исследования  
3. CMC / производство DS–DP  
4. Регуляторика: разрешение на КИ (Минздрав)  
5. Клинические исследования I–III  
6. Регистрация (Минздрав / ГРЛС)  
7. Коммерческое производство  

Внутри — задачи и 1 уровень подзадач. Исполнители вымышленные (Иванов, Петрова, …). Объём: ~30–40 строк.

### 5.3 Sample-файл

`examples/plan_vax_b_demo.xlsx` — валидный импорт, немного отличается от сида (чтобы шаг 2 demo script был заметен). Legacy-имя `plan_biokad_demo.xlsx` — копия того же файла.

---

## 6. Архитектура

### 6.1 Общая схема

```
Browser (React SPA)
    │  HTTPS REST + cookie JWT
    ▼
FastAPI (auth, plans, excel, chat, jobs, undo)
    │                    │
    │                    ├── asyncio background worker
    │                    │         │
    │                    │         ├── LLM (DeepSeek / OpenAI)
    │                    │         │
    │                    │         └── MCP client ──► MCP server (stdio/SSE)
    │                    │                                   │
    └────────────────────┴───────────────────────────────────┘
                         ▼
                   SQLite (MVP)
```

Структура репозитория:

```
/var/CRM_test/
  TECHNICAL_SPEC.md          ← этот документ
  README.md
  ROADMAP_TO_PRODUCTION.md
  Makefile                   # make up | seed | test
  frontend/                  # React + Vite + TS + Tailwind
  backend/                   # FastAPI
  mcp_server/                # отдельный MCP-процесс
  examples/
    plan_vax_b_demo.xlsx
    plan_biokad_demo.xlsx          # legacy alias = копия VAX-B sample
  docs/
    demo.gif                 # или demo.mp4
    RUNBOOK.md
    adr/                     # или DECISIONS.md
  .env.example
```

### 6.2 Стек (зафиксирован)

| Слой | Выбор | Комментарий |
|------|--------|-------------|
| Frontend | React, Vite, TypeScript, Tailwind | UI только RU |
| Gantt | **Собственный** (CSS grid/SVG): дерево, bars, FS-линии, drag, highlight | Не frappe; контроль UX |
| Backend | FastAPI, SQLAlchemy, Pydantic | Без Alembic в MVP |
| DB | SQLite | Postgres → Roadmap |
| Auth | JWT в httpOnly cookie, bcrypt | 2 сид-юзера |
| Agent | OpenAI SDK, `base_url` DeepSeek, thinking off | `LLM_PROVIDER` switch |
| MCP | отдельный процесс, Python MCP SDK | Подключаем и из Cursor |
| Jobs | таблица `agent_jobs` + asyncio на uvicorn | Single-process limit → Roadmap |
| Excel | openpyxl | Import/export только REST |
| Deploy | nginx → static + uvicorn; systemd; TLS на Bio.2alexs.ru | |

### 6.3 Модель данных

- `users` — id, login, password_hash  
- `plans` — id, user_id, title, start_date, updated_at  
- `tasks` — id, plan_id, code, parent_id, title, description, assignee, duration_days, start_date, sort_order, last_changed_by (`user` \| `agent`), updated_at  
- `dependencies` — id, plan_id, predecessor_task_id, successor_task_id (FS)  
- `chat_messages` — id, plan_id, role (`user`\|`assistant`\|`system`), content, job_id?, meta_json?, created_at  
- `agent_jobs` — id, plan_id, status (`queued`\|`running`\|`done`\|`failed`), request_text, result_summary, error, changes_json, created_at, finished_at; поля качества: `provider`, `model`, `latency_ms`, `validate_ok`, `validate_errors_json`, `tool_calls_json`, `tokens_input`, `tokens_output`, `undone_within_5m`, `rating` (`up`\|`down`\|null), `rating_comment`  
- `plan_snapshots` — id, plan_id, payload_json, source (`agent`\|`ui`\|`excel`\|`undo`), created_at  

При undo, если откатывается результат агента младше 5 минут — выставить `undone_within_5m=true` на соответствующем job (прокси неудачной правки).

MVP: один активный план на пользователя (при импорте Excel — замена/пересборка задач этого плана).

### 6.4 Undo

- Перед каждым мутирующим действием (агент, DnD, ручное редактирование в модалке, import) — push snapshot.  
- Хранить ≤ **10** на план (FIFO drop oldest).  
- `POST /api/plans/{id}/undo` восстанавливает последний snapshot и снимает его со стека.  
- Чат: «отмени» / «отмени последнее» → тот же undo (можно без LLM, rule-based).

### 6.5 Background jobs и уведомления

- `POST /api/chat` создаёт `agent_job` (`queued`), пишет user message, возвращает `{ job_id }`.  
- Worker: `running` → LLM ↔ MCP → validation → apply (+ snapshot) → assistant message + `changes[]` → `done` / `failed`.  
- Фронт: poll `GET /api/jobs/{id}` пока активен; при mount — история + проверка незакрытых/свежезавершённых job → toast.

### 6.6 API surface (кратко)

| Method | Path | Назначение |
|--------|------|------------|
| POST | `/api/auth/login` | Логин |
| POST | `/api/auth/logout` | Выход |
| GET | `/api/auth/me` | Текущий пользователь |
| GET | `/api/plans/current` | План + tasks + deps |
| PATCH | `/api/tasks/{id}` | Ручное обновление |
| POST | `/api/plans/current/import` | Excel upload |
| GET | `/api/plans/current/export` | Excel download |
| POST | `/api/chat` | Новое сообщение → job |
| GET | `/api/chat/messages` | История |
| GET | `/api/jobs/{id}` | Статус job (+ trace fields) |
| GET | `/api/agent/runs` | Список прогонов агента (журнал) |
| GET | `/api/agent/stats` | Агрегаты качества (success / validate fail / undo / latency) |
| POST | `/api/jobs/{id}/rating` | 👍/👎 + опциональный comment |
| POST | `/api/plans/current/undo` | Undo |
| POST | `/api/plans/current/reset-seed` | Восстановить демо-сид (confirm на UI) |
| GET | `/api/health` | Healthcheck (в т.ч. DB; LLM — опциональный статус, не валит health) |

Все кроме login/health — под auth.

### 6.7 Graceful degradation (AI не SPOF)

- Без ключа / при 5xx / timeout LLM: логин, Gantt, Excel import/export, ручные правки, undo — **работают**.
- `POST /api/chat` возвращает контролируемую ошибку (job `failed` или 503 с RU-текстом), не роняет процесс.
- UI чата показывает: «Ассистент временно недоступен…»; остальной экран без изменений.
- `GET /api/health` успешен, если живы API+DB; отдельное поле `llm: ok|degraded` допустимо.

### 6.8 Инварианты плана и транзакции

Инварианты (проверяет `validate_plan`, перечислены в README):

1. Уникальный `code` в рамках плана.  
2. `parent` существует или пуст; нет циклов в дереве.  
3. Precedessors существуют; нет циклов в графе FS.  
4. `duration_days > 0` для листьев.  
5. Нельзя удалить задачу, пока на неё ссылаются deps — или каскад явно в патче.

`apply_plan_patch`: snapshot → validate → **одна DB-транзакция** на все operations → commit. При любой ошибке — полный rollback, план не меняется.

### 6.9 ADR

2–3 коротких ADR в `docs/adr/` (или один `docs/DECISIONS.md`):

- ADR-001: свой Gantt вместо библиотеки  
- ADR-002: DeepSeek V4 Flash + OpenAI fallback  
- ADR-003: SQLite + in-process jobs (лимиты честно)

Формат: Context / Decision / Consequences (полстраницы каждый).

### 6.10 Runbook и Makefile

`docs/RUNBOOK.md`: рестарт `bioplan-api`, где journald-логи, смена `LLM_PROVIDER`, `make seed` / reset-seed, проверка `/api/health`, типичные сбои (ключ, диск SQLite).

Корневой `Makefile`:

- `make up` — поднять API (+ сборка фронта по договорённости)  
- `make seed` — пересид пользователей и демо-плана  
- `make test` — pytest  

README ведёт с `make up`, не с длинной портянки.

---

## 7. Агент и MCP

### 7.1 Контракт MCP tools

Мало и мощно (Excel **не** в MCP):

| Tool | Назначение |
|------|------------|
| `get_plan_snapshot` | Полный снимок плана (коды, иерархия, даты, deps, assignees) |
| `apply_plan_patch` | Batch JSON-патч: create / update / delete / set_deps / reassign / shift |
| `validate_plan` | Проверка циклов, битых parent/pred, duration |

Схема патча (логическая):

```json
{
  "operations": [
    { "op": "shift", "filter": { "phase_code": "P2" }, "days": 10 },
    { "op": "reassign", "filter": { "phase_code": "P3" }, "assignee": "Иванов" },
    { "op": "create", "code": "T2.9", "parent": "P2", "title": "...", "duration_days": 5, "predecessors": ["T2.8"] },
    { "op": "update", "code": "T1.1", "fields": { "title": "..." } },
    { "op": "set_deps", "code": "T3.1", "predecessors": ["T2.9"] },
    { "op": "delete", "code": "T4.3" }
  ]
}
```

Сервер: `validate` → при ошибке **не apply** → текст ошибки агенту/пользователю.  
Успешный путь: snapshot → validate → apply **в одной транзакции** (§6.8).  
Delete в UI/агенте — с подтверждением на фронте или явным маркером в диалоге (P1/cut-line: confirm на delete).

### 7.2 LLM

- Default: **Timeweb Cloud AI** (`LLM_PROVIDER=timeweb`), OpenAI-compatible agent endpoint.  
  Fallback: DeepSeek / OpenAI.   
- Thinking mode: **выключен** в MVP.  
- Fallback: `LLM_PROVIDER=openai` + модель из env (например `gpt-4o-mini`).  
- System prompt + 3 few-shot на русском под BioPlan.  
- Ответ ассистента: краткий текст + structured `changes[]` (коды задач) для подсветки UI.

### 7.3 Риски DeepSeek V4 Flash и митигации

| Риск | Влияние | Митигация |
|------|---------|-----------|
| Flash слабее Pro/GPT-4o на сложных multi-edit | Ломается демо | Узкий patch-tool, few-shot, golden prompts, валидация до commit |
| Thinking + tools требует эхо `reasoning_content` | Сложность цикла | Thinking off |
| Данные плана уходят во внешний LLM | Compliance для фармы | Roadmap: on-prem / Azure OpenAI / gateway; в README — честный disclaimer |
| Квоты / сеть / ключ | Демо down | `LLM_PROVIDER` switch; health + понятная ошибка в чате |
| Нестабильные tool args | Частичный apply | Только atomic apply всего патча после validate |

**Решение:** DeepSeek по умолчанию; OpenAI — запасной переключатель без переписывания агента.

### 7.4 Golden prompts (обязательный прогон перед сдачей)

| # | Промпт (пример) | Ожидание |
|---|-----------------|----------|
| G1 | «Сдвинь всю доклинику на 10 дней» | Все задачи фазы доклиники + потомки сдвинуты; summary |
| G2 | «Назначь Иванова на все задачи фазы CMC» | Массовый reassign; summary |
| G3 | «Добавь задачу "Резервный анализ антигена" в доклинику на 5 дней после T2.3» | create + predecessor |
| G4 | «Сделай предшественником для T3.1 задачу T2.9» | set_deps |
| G5 | «Отмени последнее» | undo без порчи плана |
| G6 | «Кто перегружен по числу задач?» | read-only summary через snapshot, без mutate |
| G7 | «Уточни описания всех задач регуляторики: добавь префикс [REG]» | batch update descriptions |

Список дублируется в README. Перед gif — все G1–G7 green на стенде.

### 7.5 MCP из Cursor (AI-infra)

Тот же `mcp_server/` должен запускаться отдельно и подключаться к Cursor.

Пример фрагмента для README / Cursor MCP config:

```json
{
  "mcpServers": {
    "bioplan": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/repo",
      "env": {
        "BIOPLAN_DATABASE_URL": "sqlite:////path/to/bioplan.db"
      }
    }
  }
}
```

В README: команда запуска, список tools (`get_plan_snapshot`, `apply_plan_patch`, `validate_plan`), замечание что FastAPI-агент — MCP-клиент к тому же серверу. Это закрывает тезис вакансии «создаёте AI-инструменты для команды».

Транспорт MVP: **stdio** (удобно для Cursor); из FastAPI — subprocess stdio client. Альтернатива SSE — только если stdio неудобен в systemd (зафиксировать фактически выбранное в README).

---

## 8. UI / UX

### 8.1 Визуальный язык

- Бренд **BioPlan** — заметный сигнал в шапке (не только текст в nav).  
- Палитра light: тёплый off-white / slate, один акцент — глубокий teal. Без purple-gradient, glow, «кислоты», Inter/Roboto.  
- Палитра dark: глубокий ink/slate фон, приглушённые surfaces, тот же teal-акцент, без neon/glow; текст и bars с достаточным контрастом.  
- Тема: `data-theme="light|dark"` на `html`, токены через CSS variables (`--bg`, `--surface`, `--text`, `--muted`, `--accent`, `--border`, `--danger`); toggle в шапке; persist в `localStorage` (ключ `bioplan-theme`).  
- Шрифты: выразительный display + читаемый body (например Manrope + Source Serif 4 или эквивалент с открытой лицензией).  
- После логина: одна композиция — Gantt (центр/лево) + чат (право). Не дашборд со статистикой.

### 8.2 Gantt (свой)

- Иерархия с indent + collapse.  
- Bars по `start_date` + `duration_days`.  
- SVG/Canvas линии FS.  
- Zoom: дни / недели.  
- Highlight изменённых task id/code 3–5 сек (лёгкий pulse).  
- DnD бара = сдвиг start (P1); после drag — snapshot + пересчёт зависящих по правилам MVP (документировать: сдвигаем только dragged leaf или cascade — выбрать одно и держаться).

### 8.3 Модалка задачи

Показывать:

- код, название, описание  
- исполнитель  
- длительность, start (и вычисленный end)  
- родитель  
- предшественники (коды + названия)  
- последнее изменение: кто (`user`/`agent`) и когда  

Редактирование полей в модалке — желательно (пишет snapshot); минимум — read-only + закрытие, если режет срок (лучше editable title/assignee/duration).

### 8.4 Чат

- Статус job (queued/running/done/failed).  
- Summary + список `changes`.  
- P1: collapsible «агент вызвал apply_plan_patch».  
- Ошибки LLM/валидации — человекочитаемо по-русски.

### 8.5 Состояния

Loading job, empty plan, ошибка LLM, Undo disabled (стек пуст), upload progress.

### 8.6 Motion

2–3 осмысленных: highlight bars, появление сообщения ассистента, лёгкий transition панели чата — без декоративного шума.

### 8.7 Agent Trace — журнал качества агента

Цель: дать разработчику и ревьюеру данные, чтобы оценивать и улучшать качество LLM-задач (не сырой dump логов сервера).

**На каждый `agent_job` сохраняем:**

| Поле | Зачем |
|------|--------|
| `request_text` | что просил пользователь |
| `provider` / `model` | сравнение DeepSeek vs OpenAI |
| `tool_calls_json` | какие MCP tools, args summary, ok/error, duration_ms |
| `validate_ok` / `validate_errors_json` | ловит галлюцинации патча |
| `changes_json` | что реально изменилось |
| `latency_ms` | скорость |
| `tokens_*` | стоимость/объём (если API отдаёт) |
| `status` / `error` | успех или причина fail |
| `undone_within_5m` | прокси «плохая правка» |
| `rating` / `rating_comment` | ручная оценка ответа |

**UI «Журнал ассистента»** (пункт в шапке или drawer, для залогиненных):

1. Сводка метрик по текущему плану / всем своим job: % `done`, % validate fail, % undo-after-agent, avg latency.  
2. Таблица прогонов: время, статус, model, latency, validate, undo?, rating.  
3. Детали по клику: prompt, tool-calls, patch/changes, errors (collapsible JSON ок).  
4. В чате у сообщения ассистента — кнопки 👍 / 👎 (пишут rating на job).

Связь с golden prompts (§7.4): после прогона G1–G7 смотрим журнал — все `done` + validate ok; failures разбираем по trace.

В Roadmap: экспорт traces, eval-набор как CI job, дашборд по провайдерам.

---

## 9. Безопасность и конфиг

- Секреты только в `.env` (не в git): `SECRET_KEY`, `DEEPSEEK_API_KEY` / `OPENAI_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `DATABASE_URL`.  
- `.env.example` без реальных ключей.  
- httpOnly Secure cookie на HTTPS; CORS только свой origin.  
- Пароли bcrypt.  
- Upload Excel: лимит размера, только xlsx, парсинг на сервере.  
- Disclaimer: содержимое плана уходит в внешний LLM — для боевой фармы недопустимо без DPA/on-prem (Roadmap).

Демо-учётки (пример, зафиксировать при сиде):

| Логин | Пароль |
|-------|--------|
| `pm` | (задать при реализации, указать в README) |
| `viewer` | (задать при реализации, указать в README) |

---

## 10. Деплой Bio.2alexs.ru

- Домен и сертификат уже есть.  
- nginx: TLS → `/` static frontend, `/api` → uvicorn.  
- systemd: `bioplan-api.service` (+ при необходимости MCP не как отдельный публичный порт, а subprocess агента).  
- Health: `GET /api/health`.  
- Логи journald; в Roadmap — структурированные логи + metrics.

---

## 11. План работ на 2 дня

### День 1 — каркас + визуал + данные (P0 без агента)

| Блок | Результат |
|------|-----------|
| Monorepo + Makefile | `frontend/`, `backend/`, `mcp_server/`, `examples/`, `make up/seed/test` |
| Auth + seed + reset | 2 пользователя, фарм-план, API/кнопка reset-seed |
| REST + инварианты | plan/tasks, import/export, validate, транзакции |
| Gantt UI | иерархия, deps, modal, highlight-ready |
| Excel | round-trip вручную проверен |
| Deploy | сайт по HTTPS; без ключа LLM чат degraded, остальное ок |

### День 2 — агент + P1 + сдача

| Блок | Результат |
|------|-----------|
| MCP | 3 tools, клиент из FastAPI |
| Agent loop | DeepSeek, atomic patch apply, summary + degradation |
| UI agent | highlight + changes |
| Jobs + history + toast | P1 |
| Undo ≤10 | P1 |
| Тема light/dark | P1 |
| Agent Trace + rating + stats API/UI | P1 |
| DnD | если успеваем |
| pytest минимум | validate + excel |
| Docs + gif | README (инженерные решения), ADR, Runbook, Roadmap, demo script |
| Golden G1–G7 | на проде |
| Git | 1–2 аккуратных коммита перед сдачей |

### Код и git

- Имена: английский `snake_case` / `camelCase` (`task_id`, `assignee`, `predecessors`) — без транслита.  
- Стиль мидла: простые сервисы, без AI-slop абстракций и комментариев «# This function…».  
- UI-тексты русские.  
- Коммиты осмысленные, не история чата с ассистентом.

---

## 12. Definition of done (сдача)

- [ ] `https://Bio.2alexs.ru` открывается, логин работает  
- [ ] Сид-Gantt виден сразу после входа  
- [ ] Demo script §4 проходит end-to-end  
- [ ] Golden prompts G1–G7 проходят (или задокументирован fallback-провайдер для демо)  
- [ ] Excel sample в репо; import/export работают  
- [ ] MCP реален; в README — как подключить из Cursor  
- [ ] Переключение light/dark темы работает и переживает reload  
- [ ] Журнал ассистента показывает прогоны + базовые метрики; rating 👍/👎 сохраняется  
- [ ] Без LLM-ключа: Gantt/Excel/undo работают; чат — контролируемая ошибка  
- [ ] `apply_plan_patch` атомарный; инварианты описаны в README  
- [ ] `make up` / `make seed` / `make test` работают; кнопка сброса демо-плана есть  
- [ ] ADR (или DECISIONS.md) + Runbook на месте  
- [ ] README: запуск, архитектура, блок «Инженерные решения», AI-ассистенты, 3-min checklist  
- [ ] `ROADMAP_TO_PRODUCTION.md` с долгами, рисками, порядком закрытия (в т.ч. RAG под SOP, Postgres, queue, GxP-lite audit, on-prem LLM, календарь РФ)  
- [ ] Demo gif/видео  
- [ ] Нет секретов в git  

---

## 13. Задел под Roadmap (не делать в MVP)

Порядок закрытия (черновик для будущего `ROADMAP_TO_PRODUCTION.md`):

1. Postgres + миграции (Alembic) + бэкапы  
2. Отдельный worker/queue (Redis/RQ/Arq) вместо in-process jobs  
3. LLM gateway / on-prem; запрет утечки PII; DPA  
4. RBAC, multi-plan, audit trail (GxP-lite)  
5. **RAG** по SOP / шаблонам протоколов / историческим планам — когда snapshot плана недостаточен  
6. Календарь рабочих дней РФ, resource leveling  
7. E2E (Playwright), CI, observability (logs/metrics/traces)  
8. Совместное редактирование / sync  
9. Agent eval CI: прогон golden prompts + дашборд качества по `agent_jobs` / экспорт traces  

Явная связь с вакансией: RAG не нужен, пока агенту достаточно `get_plan_snapshot`; появляется, когда нужны корпоративные регламенты и шаблоны. Agent Trace в MVP — зачаток observability AI-инструментов.

---

## 14. Соответствие обязательному заданию заказчика

| Требование задания | Где в BioPlan |
|--------------------|---------------|
| Интерактивный Gantt + сид | §2 P0.1, §5.2, §8.2 |
| Загрузка своего Excel | §2 P0.4, §5, API import |
| Чат NL массовые правки | §2 P0.2, §7 |
| Мгновенное отражение на диаграмме | §2 P0.3, highlight |
| Модалка по клику | §2 P0.8, §8.3 |
| Экспорт Excel | §2 P0.4 |
| React + FastAPI + MCP + LLM API | §6.2 |
| README + архитектура + AI-assistants | §12 |
| Demo gif + sample Excel + Roadmap | §12, §13 |
| Репозиторий + развёрнутое приложение | git + Bio.2alexs.ru |

Дополнительно (ваши требования): иерархия, DnD, undo×10, background+history+toast, auth, фарм-сценарий, DeepSeek, двуязычность документов, dark theme, Agent Trace — см. P0/P1 и cut-line.

Системная зрелость (§6.7–6.10): graceful degradation, ADR, Makefile, транзакции/инварианты, Runbook, reset-seed.

---

*Документ является ТЗ для реализации MVP BioPlan. При расхождении срока и объёма действует cut-line §2.3; ядро агента и wow-path не жертвуются.*
