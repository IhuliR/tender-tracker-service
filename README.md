# Tender Tracker Service

Небольшой backend-сервис для создания тендеров, управления их статусами и хранения истории изменений. Проект демонстрирует реализацию обязательной API/инфраструктурной части тестового задания и дополнительный асинхронный AI-анализ конкретного изменения статуса. Проект реализован в рамках тестового задания и намеренно ограничен его масштабом - это не production-ready система.

Подробные архитектурные решения описаны в [docs/DESIGN.md](docs/DESIGN.md).

## Возможности

- создание и получение Tender;
- изменение статуса `draft`, `active`, `won` или `lost`;
- атомарная запись нового статуса и `TenderStatusHistory`;
- получение истории изменений;
- отдельный запуск AI-анализа выбранного перехода статуса;
- выполнение LLM-запроса в Celery worker;
- получение состояния и результата задачи по `task_id`.

## Стек

- Python 3.12, FastAPI, Pydantic v2 и pydantic-settings;
- SQLAlchemy 2.x async, PostgreSQL, psycopg 3 и Alembic;
- Redis и Celery;
- OpenAI API;
- Docker и Docker Compose;
- pytest, Ruff и GitHub Actions.

## Архитектура

```text
FastAPI
  |
  +--> PostgreSQL
  |
  +--> Redis broker --> Celery worker --> OpenAI
                         |
                         +--> Redis result backend
```

Смена статуса и создание истории выполняются в одной PostgreSQL-транзакции. AI-анализ запускается отдельным HTTP-запросом уже после сохранения истории, поэтому недоступность Redis, Celery или OpenAI не откатывает и не блокирует основной Tender workflow.

## Конфигурация

Безопасный пример находится в `.env.example`:

```bash
cp .env.example .env
```

| Переменная | Назначение |
|---|---|
| `DATABASE_URL` | PostgreSQL URL для приложения и локальных команд |
| `CELERY_BROKER_URL` | Redis URL для публикации Celery tasks |
| `CELERY_RESULT_BACKEND` | Redis URL для состояния и результатов tasks |
| `OPENAI_API_KEY` | Ключ OpenAI; необязателен для core API, но нужен для успешного AI-анализа |
| `OPENAI_MODEL` | Модель OpenAI; default — `gpt-5.6-luna` |

Реальный ключ нельзя добавлять в Git. В Docker Compose OpenAI-настройки передаются только worker; FastAPI-контейнер не требует provider credentials.

## Запуск через Docker Compose

```bash
docker compose up --build
```

Compose запускает `app`, `db`, `redis` и `worker`. Перед Uvicorn приложение автоматически выполняет:

```bash
alembic upgrade head
```

После запуска:

- API: `http://localhost:8000`;
- Swagger UI: `http://localhost:8000/docs`;
- OpenAPI schema: `http://localhost:8000/openapi.json`.

## API

```text
POST  /api/v1/tenders
GET   /api/v1/tenders/{tender_id}
PATCH /api/v1/tenders/{tender_id}/status
GET   /api/v1/tenders/{tender_id}/history

POST  /api/v1/tenders/{tender_id}/history/{history_id}/ai-analysis
GET   /api/v1/ai-analysis/{task_id}

GET   /health
```

Пример создания Tender:

```bash
curl -X POST http://localhost:8000/api/v1/tenders \
  -H "Content-Type: application/json" \
  -d '{"title":"Bridge inspection","description":"Annual inspection"}'
```

Пример смены статуса:

```bash
curl -X PATCH http://localhost:8000/api/v1/tenders/1/status \
  -H "Content-Type: application/json" \
  -d '{"new_status":"active","changed_by":"publisher-1","reason":"Tender published"}'
```

AI endpoint возвращает `202 Accepted`, `task_id` и статус `queued`; он не ждёт ответа OpenAI. Полные request/response schemas доступны в Swagger UI.

## Тесты и linting

Автоматические интеграционные тесты используют PostgreSQL, а не SQLite. `TEST_DATABASE_URL` должен указывать на отдельную PostgreSQL database, имя которой содержит `test`:

```bash
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/tender_tracker_test \
  python -m pytest

ruff check .
python -m compileall -q app alembic tests
python -m pip check
```

AI/OpenAI boundaries в automated tests заменяются mocks/fakes, поэтому тесты не требуют Redis или реального API key. GitHub Actions поднимает PostgreSQL и выполняет `ruff check .` и `python -m pytest` при push и pull request.

## AI design

Сервис передаёт general-purpose LLM только ограниченный контекст одного изменения статуса: название, описание, старый и новый статусы и причину. `OpenAILLMClient` изолирован контрактом `LLMClient`, использует OpenAI Responses API и получает структурированный `StatusChangeAnalysis`, провалидированный Pydantic.

Fine-tuning, RAG, embeddings и предметный scoring намеренно не добавлены. В задании нет исторических бизнес-данных, размеченных примеров, специфичных правил заказчика и критериев качества, по которым можно было бы обоснованно выбрать и оценить эти подходы.

В реальном продукте развитие AI-части началось бы с бизнес-целей, репрезентативных примеров и evals. После измерения baseline можно улучшать prompt, добавлять релевантный исторический контекст или RAG, а fine-tuning применять только при наличии данных и подтверждённой необходимости.

## Ограничения

- нет authentication/authorization; `changed_by` передаётся строкой;
- AI results временно хранятся в Celery/Redis result backend, а не PostgreSQL;
- неизвестный или ещё не завершённый `task_id` может отображаться как `pending`;
- успешный AI-анализ требует доступного OpenAI provider и credentials;
- AI output носит рекомендательный характер и не доказывает причины победы или поражения.

## License

See [LICENSE](LICENSE).
