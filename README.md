# Arcana Bot

Telegram-бот для таро-раскладов с визуализацией карт, интерпретацией через LLM, реферальной системой и платными подписками.  
Запускается как единый FastAPI-процесс: бот работает в режиме polling через lifecycle приложения, вебхуки принимаются через HTTP-роуты.

## Стек

| Слой | Технологии |
|---|---|
| Язык | Python 3.12+, `uv` |
| Web / Bot | FastAPI · Uvicorn · python-telegram-bot v22 (polling) |
| БД | PostgreSQL 15 · SQLAlchemy 2.0 async · asyncpg · Alembic |
| DI | dishka 1.x |
| Изображения | Pillow |
| LLM | OpenRouter API |
| Хранилище | S3-совместимое (MinIO для self-hosted) |
| Платежи | Telegram Stars · YooKassa |
| Логирование | Loguru |
| Инфра | Docker · Docker Compose · GitHub Actions |

## Архитектура

Проект построен по принципам **Clean Architecture / Ports & Adapters**:

```
app/
├── domain/           # Entities, Port-протоколы (чистая бизнес-логика, нет импортов инфры)
├── application/      # Use cases, DTO, исключения
├── infrastructure/   # Реализации портов: DB-репозитории, S3, LLM, платёжные шлюзы, DI-провайдеры
├── presentation/
│   └── telegram/     # Хэндлеры PTB, форматтеры, DI-биндинг контейнера
├── api/              # FastAPI-роуты: healthcheck, вебхук YooKassa
├── core/             # Settings (pydantic-settings)
├── bot/              # Telegram-lifecycle: сборка PTB Application, polling, DI-wiring
└── services/         # Вспомогательные синглтоны (ImageService, TarotDataService)
```

**Правило зависимостей:** `domain` ← `application` ← `infrastructure` / `presentation`. Инфра знает о домене, домен не знает об инфре.

## Функциональность

- **Расклады** — 1, 3 и 5 карт; генерация изображения через Pillow; интерпретация через LLM; сохранение в S3
- **Дневная карта** — ежедневная рассылка по расписанию МСК
- **Лимиты** — 3 бесплатных расклада в день (сброс в полночь); бонусный баланс; атомарный CASE UPDATE без race condition
- **Реферальная система** — deep-link `?start=ref_<id>`; +3 бонусных расклада рефереру при регистрации
- **Профиль** — `/profile` или кнопка «👤 Профиль»: статус подписки, лимиты, реферальная ссылка
- **Подписка Премиум** — 30 дней безлимита; оплата через Telegram Stars или YooKassa (карта); мгновенная активация

## Переменные окружения

```bash
cp .env.example .env
```

| Переменная | Обязательна | Описание |
|---|---|---|
| `BOT_TOKEN` | ✅ | Токен Telegram-бота |
| `OPENROUTER_API_KEY` | ✅ | Ключ OpenRouter |
| `DB_*` | ✅ | Параметры PostgreSQL |
| `ADMIN_TG_ID` | ✅ | Telegram ID администратора |
| `S3_*` | ✅ | S3/MinIO реквизиты |
| `YOOKASSA_SHOP_ID` | для карт | ID магазина YooKassa |
| `YOOKASSA_SECRET_KEY` | для карт | Секретный ключ YooKassa |
| `PREMIUM_PRICE_STARS` | — | Цена в Stars (default: `79`) |
| `PREMIUM_PRICE_RUB` | — | Цена в рублях (default: `159`) |
| `BOT_PUBLIC_URL` | — | `https://t.me/<username>` — return_url для YooKassa |

> **Docker vs локальная разработка**  
> В Docker: `DB_HOST=db`, `S3_ENDPOINT_URL=http://minio:9000`  
> Локально: `DB_HOST=127.0.0.1`, `S3_ENDPOINT_URL=http://127.0.0.1:9000`

## Быстрый старт (Docker)

```bash
cp .env.example .env   # заполнить
make rebuild           # собрать и поднять
make migrate-docker    # применить миграции
curl http://localhost:8000/health
```

## Команды Makefile

```bash
make help                  # полный список

make run-dev               # локальный запуск с --reload
make rebuild               # пересобрать и перезапустить Docker-стек
make migrate-docker        # миграции внутри контейнера
make logs-app              # логи приложения
make shell-app             # bash в контейнере
make reset-limits-docker   # сбросить daily_limit=3 для всех
make health                # проверить /health
```

## Сброс дневных лимитов

Скрипт `app/infrastructure/db/scripts/reset_daily_limits.py` сбрасывает `daily_limit = 3`. Запускай через cron каждую ночь в полночь МСК (21:00 UTC):

```cron
0 21 * * * docker exec arcana-bot-app uv run python -m app.infrastructure.db.scripts.reset_daily_limits
```

## Продакшн-деплой

### Схема

```
Internet → Nginx (443 SSL) → 127.0.0.1:8000 → FastAPI (Docker)
                                                     | arcana-net
                                              PostgreSQL · MinIO
```

Все порты Docker-сервисов привязаны к `127.0.0.1` — снаружи недоступны.

### CI/CD (GitHub Actions)

Пуш в `main` → SSH на VM → `git pull` → `make rebuild`. Конфиг: [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml).

Секреты репозитория (**Settings → Secrets → Actions**):

| Секрет | Значение |
|---|---|
| `SSH_HOST` | IP или домен VM |
| `SSH_USER` | SSH-пользователь |
| `SSH_KEY` | Приватный SSH-ключ |
| `DEPLOY_PATH` | Путь к папке проекта на VM |

### Nginx

Готовый конфиг: [`nginx/arcana-bot.conf`](nginx/arcana-bot.conf).  
Uvicorn запускается с `--proxy-headers`, поэтому FastAPI и вебхук YooKassa видят реальные IP клиентов.

```bash
cp nginx/arcana-bot.conf /etc/nginx/sites-available/arcana-bot.conf
ln -s /etc/nginx/sites-available/arcana-bot.conf /etc/nginx/sites-enabled/
certbot --nginx -d api.yourdomain.ru
nginx -t && systemctl reload nginx
```

### Вебхук YooKassa

В личном кабинете YooKassa укажи URL нотификации:

```
https://api.yourdomain.ru/api/v1/payments/yookassa/webhook
```

## Локальная разработка

```bash
uv sync
make run-dev    # или: uv run uvicorn app.main:app --reload
make migrate
```

## Наблюдаемость

- Логи: `logs/bot.log`, ротация 10 МБ, retention 30 дней
- Каждый вызов LLM фиксируется в таблице `llm_usage_events`
- Статистика администратора: команда `/admin_stats` в боте
- Healthcheck: `GET /health` (проверяет доступность БД)
