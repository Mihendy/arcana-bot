# Arcana Bot

Telegram-бот для генерации таро-раскладов с визуализацией карт, интерпретацией через LLM и хранением истории в PostgreSQL.  
Приложение запускается как FastAPI-сервис и поднимает polling-бота через lifecycle приложения.

## Стек технологий

- Python 3.12+
- `uv` для управления зависимостями и запуска команд
- FastAPI + Uvicorn
- python-telegram-bot (polling mode)
- SQLAlchemy 2.0 (async) + asyncpg
- Alembic (миграции БД)
- PostgreSQL 15+
- Pillow (генерация изображений расклада)
- Loguru (структурированное логирование и ротация)
- OpenRouter API (интерпретация раскладов)
- Docker + Docker Compose

## Развертывание через Docker Compose

### 1) Подготовка окружения

1. Создайте файл `.env` в корне проекта.
2. Заполните обязательные значения:
   - `BOT_TOKEN`
   - `OPENROUTER_API_KEY`
   - параметры БД (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`)
   - `ADMIN_TG_ID`

### 2) Запуск контейнеров

```bash
docker compose up -d --build
```

Или через `Makefile`:

```bash
make rebuild
```

### 3) Применение миграций

В контейнере:

```bash
make migrate-docker
```

Локально:

```bash
make migrate
```

### 4) Проверка состояния

- API healthcheck: `GET /health`
- Логи приложения: `logs/bot.log`
- Статистика для администратора: команда `/admin_stats` в Telegram

## Структура проекта

```text
app/
  api/            # HTTP-роуты (healthcheck)
  bot/            # Telegram-слой: handlers, middleware, lifecycle
  core/           # Конфигурация и инфраструктурные зависимости (DB, settings)
  models/         # ORM-модели SQLAlchemy
  repositories/   # Слой доступа к данным
  schemas/        # Pydantic-схемы
  services/       # Бизнес-логика (tarot, llm, image, analytics, storage)
  assets/         # tarot_deck.json, изображения карт, шрифты

alembic/          # Миграции БД
data/output/      # Временное хранилище сгенерированных изображений
logs/             # Логи приложения
```

## Архитектурные решения (Clean Architecture)

Проект использует практичный вариант Clean Architecture с разделением на уровни:

- **Presentation layer**  
  `app/api` и `app/bot/handlers` принимают входящие запросы (HTTP/Telegram), валидируют поток и формируют ответы.

- **Application layer**  
  `app/services` реализуют сценарии: генерация расклада, запрос к LLM, сбор аналитики, рендер изображения.

- **Domain contracts**  
  Доменные структуры (`app/schemas`) и модели (`app/models`) описывают бизнес-сущности и контракт данных.

- **Infrastructure layer**  
  `app/core` (настройки, DB engine/session), `repositories` (доступ к БД), внешние интеграции (OpenRouter, Telegram, файловое хранилище).

Ключевые принципы:

- зависимости направлены из внешних слоев к внутренним абстракциям;
- бизнес-логика изолирована в сервисах и не размазана по handlers;
- доступ к данным инкапсулирован в репозиториях;
- инфраструктурные детали (proxy, токены, пути, DSN) вынесены в конфиг.

## Локальная разработка

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Полезные команды:

```bash
make run-dev
make migrate
uv run mypy app
```

## Наблюдаемость

- Логи пишутся в `logs/bot.log` с ротацией и retention.
- Каждое обращение к LLM фиксируется как событие в таблице `llm_usage_events`.
- Базовые метрики доступны через SQL-агрегации (`AnalyticsService`) и команду `/admin_stats`.