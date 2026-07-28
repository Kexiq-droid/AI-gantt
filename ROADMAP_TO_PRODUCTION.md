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

## 8. Голос и мессенджеры

### Telegram-бот (диктовка команд)

Канал вне UI: пользователь надиктовывает или пишет команду в боте — агент применяет те же tool-calls / patch, что и веб-чат.

- Bot API + webhook (или long polling для staging)
- Привязка Telegram-аккаунта к пользователю BioPlan (deep-link / one-time code)
- Голосовые сообщения → STT (Whisper / корпоративный speech-to-text) → тот же agent pipeline, что `/chat`
- Подтверждение критичных правок в боте (preview diff → «Применить» / «Отмена»)
- Rate-limit, антиспам, журнал команд в audit trail
- Уведомления из бота: job done / conflict / ошибка валидации плана

### Голосовой чат в приложении

Голос внутри веб-UI рядом с текстовым чатом агента.

- Запись с микрофона в браузере (MediaRecorder / Web Speech API как fallback)
- Streaming или chunked STT → сообщение в чат → тот же agent job
- Опционально TTS ответов агента (озвучка summary / подтверждения патча)
- UI: кнопка «удерживать / нажать для записи», индикатор уровня, отмена до отправки
- Права на микрофон, работа за reverse-proxy (HTTPS обязателен), офлайн/ошибки сети

## 9. Коллаборация

- Одновременное редактирование / presence
- Комментарии к задачам
- Уведомления (email/Mattermost/Telegram)

## Сознательные упрощения MVP

- SQLite + in-process jobs
- Внешний DeepSeek/OpenAI
- Self-signed TLS до появления DNS A-записи
- Нет полноценного i18n UI (только RU)
- Удаление задач с детьми запрещено без каскада в патче
- Нет Telegram-бота и голосового ввода (только текст в веб-чате)
