# Roadmap to production

Порядок закрытия долгов MVP BioPlan до боевого использования во внутренней фарм-среде.

## 1. Данные и миграции

- Postgres вместо SQLite
- Alembic-миграции, бэкапы, PITR
- Мульти-план / проекты на пользователя

## 2. Очередь агента

- Вынести jobs из процесса uvicorn в Redis + worker (Arq/RQ/Celery)
- Идемпотентность job_id, ретраи LLM с backoff
- Горизонтальное масштабирование API

## 3. LLM / compliance

- On-prem или корпоративный gateway (Azure OpenAI / внутренний proxy)
- DPA, запрет утечки PII/формул в внешние API
- Редaction полей перед отправкой в модель
- Kill-switch агента без деплоя

## 4. Доступ и аудит (GxP-lite)

- RBAC (viewer / editor / admin)
- Неизменяемый audit trail правок плана и tool-calls
- SSO (OIDC)

## 5. RAG (когда понадобится)

Сейчас агенту достаточно `get_plan_snapshot`. RAG нужен, когда потребуются:

- SOP / шаблоны протоколов
- Исторические планы и best practices
- Реестр ролей/ресурсов компании

## 6. Планирование

- Календарь рабочих дней РФ и праздники
- Resource leveling / загрузка исполнителей
- Типы связей кроме FS, lag/lead

## 7. Качество и наблюдаемость

- Playwright e2e по demo script
- CI: pytest + golden prompts smoke
- Метрики/логи/traces (OpenTelemetry)
- Экспорт Agent Trace, eval-наборы

## 8. Коллаборация

- Одновременное редактирование / presence
- Комментарии к задачам
- Уведомления (email/Mattermost)

## Сознательные упрощения MVP

- SQLite + in-process jobs
- Внешний DeepSeek/OpenAI
- Self-signed TLS до появления DNS A-записи
- Нет полноценного i18n UI (только RU)
- Удаление задач с детьми запрещено без каскада в патче
