# Архитектурный аудит arcana-bot

> Дата: 2026-05-21  
> Ревьюер: Senior Software Architect (Claude Sonnet 4.6)  
> Контекст: аудит перед масштабированием на мультиплатформенность, Web/Web3, монетизацию

---

## 1. КРИТИЧЕСКИЙ АУДИТ ТЕКУЩЕЙ АРХИТЕКТУРЫ

### Нарушения SRP — где один модуль делает слишком много

**`app/bot/handlers/start.py` — главный нарушитель (505 строк, 12 импортов из services/repos).**

Функция `question_handler` последовательно выполняет 8 разных задач в одной функции:

```
1. Проверка prompt-injection           ← security
2. Генерация расклада                  ← domain
3. Сборка промпта для LLM              ← application
4. Вызов LLM                           ← infrastructure
5. Генерация изображения               ← infrastructure
6. Загрузка в S3                       ← infrastructure
7. Сохранение в БД (2 отдельных блока) ← infrastructure
8. Отправка сообщений в Telegram       ← presentation
```

Она открывает `SessionLocal()` дважды (строки 78 и 168), при этом первый вызов используется только для `get_or_create`, а второй — снова для чтения того же пользователя. Это не просто неэффективно — это race condition: между двумя сессиями пользователь теоретически может быть удалён.

Вспомогательные функции `_build_spread_prompt`, `_format_cards_for_user`, `_build_layout_payload`, `_map_llm_error_to_status` — это application-layer и domain-layer логика, которая осела в presentation-слое.

`_record_llm_usage_event` — самостоятельный use case, закопанный в конец файла с хэндлерами.

**`app/services/analytics_service.py` — сервис, который пишет репозиторные запросы.**

Методы `get_total_users`, `get_readings_count`, `get_llm_usage_stats` содержат голые SQLAlchemy-запросы, открывают сессии сами (`async with SessionLocal()`), и импортируют ORM-модели напрямую. Это типичное нарушение SRP: сервис должен вызывать репозиторий, а не строить `select(func.count(User.id))`.

**`app/services/daily_card_service.py` — сервис, знающий о Telegram.**

`_build_share_story_miniapp_url` строит URL с Telegram Mini App параметрами (`widget_url`, `widget_name`). `get_recipient_tg_ids` возвращает `tg_id` — идентификатор конкретного мессенджера — вместо абстрактного user id. `_to_russian_card_name` — это локализационный словарь, который в будущем должен жить в domain/i18n, а не в сервисе доставки.

**`app/services/llm_service.py` — дублирование HTTP-кода.**

`get_interpretation` и `get_daily_card_prediction` содержат ~45 одинаковых строк: проверка API-ключа, сборка headers, POST-запрос, обработка TimeoutException, обработка RequestError, проверка статус-кодов 401/403/4xx. Это жёсткое нарушение DRY на уровне одного класса.

---

### Нарушения DIP — зависимости направлены неправильно

Каждый из сервисов и хэндлеров зависит от конкретных реализаций, а не от абстракций:

```python
# start.py — прямые import конкретных синглтонов
from app.services.llm_service import llm_service
from app.services.storage_service import storage_service
from app.services.tarot_service import tarot_service
from app.services.image_service import image_service
```

Нет ни одного `Protocol` или ABC-интерфейса для `ILLMProvider`, `IStoragePort`, `IReadingRepository`. Следствие — невозможно:
- заменить OpenRouter на Anthropic без правки хэндлера
- заменить S3 на локальный диск в тестах
- добавить второй мессенджер без копирования всей логики расклада

**Сервисы создаются как модульные синглтоны:**

```python
storage_service = StorageService()   # boto3.client() вызывается при import
llm_service = LLMService()
tarot_service = TarotService()
```

`StorageService.__init__` вызывает `boto3.client()` при импорте модуля. Если S3 недоступен или не настроен — падает весь импорт. Тесты, которые не нужны S3, не могут импортировать модуль без мокирования окружения.

---

### Замечания по работе с данными

**SQLAlchemy модели:**

Поле `tg_id` в модели `User` — это Telegram-специфичный идентификатор на уровне domain entity. При добавлении WhatsApp или Web3 авторизации нужна будет либо миграция, либо хак. Правильная абстракция: `User(id, created_at)` + `PlatformIdentity(user_id, platform, external_id)`.

`Reading` содержит одновременно `image_url: Text` и `image_urls: JSONB` — избыточность. `image_url` — реликт, `image_urls` включает его. Оба нужно объединить в `image_urls: JSONB`.

**Управление сессиями:**

Сессии открываются в 5 разных местах вне репозиториев: в `start.py` (2 раза), `analytics_service.py` (3 метода), `daily_card_service.py`, `_record_llm_usage_event`. Нет единой точки управления транзакцией. Unit of Work паттерн отсутствует.

---

### Насколько легко "выдрать" логику расклада в HTTP API?

Сейчас — **невозможно без значительного копирования кода**. Вот минимальный список изменений для одного нового эндпоинта `/api/reading`:

1. Скопировать prompt injection check из `start.py`
2. Скопировать `_build_spread_prompt` из `start.py`
3. Скопировать `_build_layout_payload` из `start.py`
4. Скопировать логику открытия сессии из `start.py`
5. Переписать вывод (не Telegram-сообщение, а JSON-ответ)

Всё потому что application-layer логика находится внутри Telegram-хэндлера.

---

## 2. ЦЕЛЕВАЯ АРХИТЕКТУРА — Clean Architecture / Ports & Adapters

### Схема слоёв

```
┌─────────────────────────────────────────────────────────────┐
│  PRESENTATION (Entrypoints)                                 │
│  Telegram Bot  │  FastAPI REST  │  (WhatsApp/VK - future)   │
│  Тонкие хэндлеры, только вызов use case + форматирование    │
├─────────────────────────────────────────────────────────────┤
│  APPLICATION (Use Cases)                                    │
│  PerformReadingUseCase  │  GetDailyCardUseCase              │
│  GetAdminStatsUseCase   │  RegisterUserUseCase              │
│  Оркестрируют domain + порты. Без импортов telegram/fastapi │
├──────────────────────────────┬──────────────────────────────┤
│  DOMAIN (Core)               │  PORTS (Interfaces)          │
│  TarotCard, SpreadResult     │  IUserRepository             │
│  SpreadType (Enum)           │  IReadingRepository          │
│  TarotDeck.draw()            │  ILLMProvider                │
│  SpreadFactory               │  IStoragePort                │
│  Чистая логика, нет import   │  IPaymentGateway             │
│  SQLAlchemy/telegram/httpx   │  (Protocol классы)           │
├──────────────────────────────┴──────────────────────────────┤
│  INFRASTRUCTURE (Adapters — реализуют порты)                │
│  PostgresUserRepo  │  S3StorageAdapter  │  OpenRouterAdapter│
│  PillowRenderer    │  AlembicMigrations                     │
└─────────────────────────────────────────────────────────────┘
```

**Domain/Core Layer** — ноль зависимостей от библиотек инфраструктуры:

- `TarotCard` — неизменяемый dataclass с полями `id`, `name`, `slug`, `arcana`
- `SpreadType` — `Enum`, не `Literal`-строка
- `SpreadResult` — dataclass с картами, метаданными, группами позиций
- `TarotDeck` — сервис с методами `draw(count, arcana_filter, allow_reversed)`
- `SpreadFactory` — стратегия-фабрика, строит `SpreadResult` из выбранных карт
- `User` — `id`, `created_at`. Без `tg_id`

**Application Layer** — бизнес-сценарии:

- `PerformReadingUseCase(user_repo, reading_repo, llm_port, storage_port, image_renderer)` — принимает `PerformReadingCommand(user_id, question, spread_type)`, возвращает `ReadingResult`
- `GetDailyCardUseCase(user_repo, llm_port, storage_port, image_renderer)`
- `GetAdminStatsUseCase(reading_repo, llm_usage_repo, user_repo)`

**Infrastructure Layer** — реализации портов:

- `PostgresUserRepository(session)` реализует `IUserRepository`
- `OpenRouterLLMAdapter(api_key, model, base_url)` реализует `ILLMProvider`
- `S3StorageAdapter(client, bucket)` реализует `IStoragePort`
- `PillowImageRenderer` — не нужен интерфейс сейчас, но изолирован

**Presentation Layer** — максимально тонкие:

- Telegram хэндлер получает use case через DI, вызывает его, форматирует ответ для Telegram
- FastAPI роутер делает то же самое — те же use cases, другой форматтер

---

## 3. ЭТАЛОННАЯ СТРУКТУРА ПРОЕКТА

```
arcana-bot/
├── app/
│   │
│   ├── domain/                          # ← Чистая бизнес-логика. Нет внешних зависимостей
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   ├── tarot.py                 # TarotCard, SpreadResult, SpreadType(Enum)
│   │   │   ├── user.py                  # User(id, created_at), PlatformIdentity
│   │   │   └── reading.py               # Reading(id, user_id, question, ...)
│   │   ├── ports/                       # Protocol-интерфейсы (абстракции)
│   │   │   ├── user_repo.py             # IUserRepository
│   │   │   ├── reading_repo.py          # IReadingRepository
│   │   │   ├── llm_port.py              # ILLMProvider
│   │   │   ├── storage_port.py          # IStoragePort
│   │   │   └── payment_port.py          # IPaymentGateway (заглушка для будущего)
│   │   └── services/                    # Чистые domain-сервисы
│   │       ├── tarot_deck.py            # TarotDeck: draw(), filter_by_arcana()
│   │       └── spread_factory.py        # SpreadFactory + стратегии
│   │
│   ├── application/                     # ← Use cases. Зависит только от domain
│   │   ├── __init__.py
│   │   ├── use_cases/
│   │   │   ├── perform_reading.py       # PerformReadingUseCase
│   │   │   ├── get_daily_card.py        # GetDailyCardUseCase
│   │   │   ├── register_user.py         # RegisterUserUseCase
│   │   │   └── get_admin_stats.py       # GetAdminStatsUseCase
│   │   ├── dto/                         # Platform-agnostic I/O структуры
│   │   │   ├── reading.py               # PerformReadingCommand, ReadingResult
│   │   │   └── daily_card.py            # DailyCardResult
│   │   └── security/
│   │       └── prompt_guard.py          # find_injection_phrase() ← переезжает сюда
│   │
│   ├── infrastructure/                  # ← Адаптеры. Реализуют порты из domain
│   │   ├── __init__.py
│   │   ├── db/
│   │   │   ├── engine.py                # create_async_engine, SessionLocal
│   │   │   ├── models/                  # SQLAlchemy ORM модели (переезжают)
│   │   │   │   ├── base.py
│   │   │   │   ├── user.py
│   │   │   │   ├── reading.py
│   │   │   │   └── llm_usage.py
│   │   │   └── repositories/            # Конкретные реализации репозиториев
│   │   │       ├── user.py              # PostgresUserRepository
│   │   │       ├── reading.py           # PostgresReadingRepository
│   │   │       └── llm_usage.py         # PostgresLLMUsageRepository
│   │   ├── llm/
│   │   │   ├── openrouter.py            # OpenRouterLLMAdapter (реализует ILLMProvider)
│   │   │   └── prompts.py               # SYSTEM_PROMPT, SPREAD_PROMPT_HINTS
│   │   ├── storage/
│   │   │   └── s3.py                    # S3StorageAdapter (реализует IStoragePort)
│   │   └── image/
│   │       ├── renderer.py              # PillowImageRenderer
│   │       └── tarot_data.py            # TarotDataService (загрузка JSON + assets)
│   │
│   ├── presentation/                    # ← Точки входа. Максимально тонкие
│   │   ├── telegram/
│   │   │   ├── bot.py                   # TelegramPollingService + lifecycle
│   │   │   ├── handlers/
│   │   │   │   ├── start.py             # /start, question_handler → вызов use case
│   │   │   │   ├── spread_select.py     # callback_handler для выбора расклада
│   │   │   │   ├── admin.py             # admin_stats_handler
│   │   │   │   └── daily_card.py        # DailyCard broadcast loop
│   │   │   └── formatters/
│   │   │       ├── reading.py           # build_result_text(), send_result_images()
│   │   │       └── keyboards.py         # build_spread_keyboard()
│   │   └── api/
│   │       ├── router.py                # /health, /public/media
│   │       └── v1/
│   │           └── reading.py           # POST /api/v1/reading (будущее)
│   │
│   ├── core/
│   │   ├── config.py                    # Settings (без изменений)
│   │   └── container.py                 # DI-контейнер (сборка зависимостей)
│   │
│   ├── assets/                          # Статика (без изменений)
│   └── main.py                          # FastAPI app + lifespan
│
├── alembic/
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   └── application/
│   └── integration/
│       └── infrastructure/
└── pyproject.toml
```

### Куда переезжают текущие файлы

| Сейчас | После рефакторинга |
|---|---|
| `app/bot/handlers/start.py` | → `presentation/telegram/handlers/start.py` (~100 строк вместо 505) |
| `app/services/tarot_service.py` | → `domain/services/spread_factory.py` |
| `app/services/llm_service.py` | → `infrastructure/llm/openrouter.py` |
| `app/services/storage_service.py` | → `infrastructure/storage/s3.py` |
| `app/services/image_service.py` | → `infrastructure/image/renderer.py` |
| `app/services/tarot_data.py` | → `infrastructure/image/tarot_data.py` |
| `app/services/analytics_service.py` | → `application/use_cases/get_admin_stats.py` |
| `app/services/daily_card_service.py` | → `application/use_cases/get_daily_card.py` (без Telegram-URL) |
| `app/schemas/tarot.py` | → `domain/entities/tarot.py` (SpreadType → Enum) |
| `app/models/` | → `infrastructure/db/models/` |
| `app/repositories/` | → `infrastructure/db/repositories/` |
| `app/bot/middlewares/prompt_guard.py` | → `application/security/prompt_guard.py` |
| `app/bot/main.py` | → `presentation/telegram/bot.py` |
| `app/core/db.py` | → `infrastructure/db/engine.py` |

---

## 4. ШАБЛОНЫ КОДА И BEST PRACTICES

### Domain Port (абстракция, без зависимостей)

```python
# app/domain/ports/llm_port.py
from typing import Protocol
from app.domain.entities.tarot import SpreadCard, SpreadType


class LLMInterpretationResult:
    interpretation: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    status: str


class ILLMProvider(Protocol):
    async def get_interpretation(
        self,
        question: str,
        cards: list[SpreadCard],
        spread_type: SpreadType,
    ) -> LLMInterpretationResult: ...

    async def get_daily_card_prediction(
        self,
        card: SpreadCard,
    ) -> LLMInterpretationResult: ...
```

```python
# app/domain/ports/user_repo.py
from typing import Protocol
from app.domain.entities.user import User


class IUserRepository(Protocol):
    async def get_by_platform_id(self, platform: str, external_id: str) -> User | None: ...
    async def get_or_create(self, platform: str, external_id: str, display_name: str) -> tuple[User, bool]: ...
    async def count_all(self) -> int: ...
```

---

### Infrastructure Repository (реализует порт)

```python
# app/infrastructure/db/repositories/user.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User as UserEntity
from app.infrastructure.db.models.user import UserORM


class PostgresUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_platform_id(self, platform: str, external_id: str) -> UserEntity | None:
        result = await self._session.execute(
            select(UserORM).where(
                UserORM.platform == platform,
                UserORM.external_id == external_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_or_create(
        self, platform: str, external_id: str, display_name: str
    ) -> tuple[UserEntity, bool]:
        existing = await self.get_by_platform_id(platform, external_id)
        if existing:
            return existing, False
        orm = UserORM(platform=platform, external_id=external_id, display_name=display_name)
        self._session.add(orm)
        await self._session.flush()  # flush, не commit — транзакция управляется снаружи
        return self._to_entity(orm), True

    def _to_entity(self, row: UserORM) -> UserEntity:
        return UserEntity(id=row.id, created_at=row.created_at)
```

Ключевой момент: `flush()` вместо `commit()` внутри репозитория — транзакция принадлежит use case, а не репозиторию.

---

### Application Use Case (оркестрация)

```python
# app/application/use_cases/perform_reading.py
from dataclasses import dataclass
from io import BytesIO

from app.domain.entities.tarot import SpreadType
from app.domain.ports.llm_port import ILLMProvider
from app.domain.ports.reading_repo import IReadingRepository
from app.domain.ports.storage_port import IStoragePort
from app.domain.ports.user_repo import IUserRepository
from app.domain.services.spread_factory import SpreadFactory
from app.application.security.prompt_guard import find_injection_phrase


@dataclass
class PerformReadingCommand:
    platform: str
    external_user_id: str
    user_display_name: str
    question: str
    spread_type: SpreadType


@dataclass
class ReadingResult:
    cards_summary: str
    interpretation: str
    image: BytesIO | None
    image_url: str | None
    llm_status: str
    llm_tokens: int | None


class InjectionBlockedError(Exception):
    pass


class PerformReadingUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        reading_repo: IReadingRepository,
        llm: ILLMProvider,
        storage: IStoragePort,
        image_renderer,
        spread_factory: SpreadFactory,
    ) -> None:
        self._user_repo = user_repo
        self._reading_repo = reading_repo
        self._llm = llm
        self._storage = storage
        self._image_renderer = image_renderer
        self._spread_factory = spread_factory

    async def execute(self, cmd: PerformReadingCommand) -> ReadingResult:
        blocked = find_injection_phrase(cmd.question)
        if blocked:
            raise InjectionBlockedError(blocked)

        user, _ = await self._user_repo.get_or_create(
            platform=cmd.platform,
            external_id=cmd.external_user_id,
            display_name=cmd.user_display_name,
        )

        spread = self._spread_factory.build(cmd.spread_type)
        llm_result = await self._llm.get_interpretation(
            question=cmd.question,
            cards=spread.cards,
            spread_type=spread.spread_type,
        )

        image = self._image_renderer.render(spread)
        stored = await self._storage.save(image, suffix=".png")

        await self._reading_repo.create(
            user_id=user.id,
            question=cmd.question,
            spread=spread,
            interpretation=llm_result.interpretation,
            image_url=stored.public_url if stored else None,
        )

        return ReadingResult(
            cards_summary=self._format_cards(spread.cards),
            interpretation=llm_result.interpretation,
            image=image,
            image_url=stored.public_url if stored else None,
            llm_status=llm_result.status,
            llm_tokens=llm_result.total_tokens,
        )

    def _format_cards(self, cards) -> str:
        parts = []
        for card in cards:
            orientation = "перевернутая" if card.is_reversed else "прямая"
            label = card.position_name or f"Карта {card.position}"
            parts.append(f"{label}: {card.name} ({orientation})")
        return ", ".join(parts)
```

---

### DI-контейнер (ручная сборка)

```python
# app/core/container.py
from functools import lru_cache
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.llm.openrouter import OpenRouterLLMAdapter
from app.infrastructure.storage.s3 import S3StorageAdapter
from app.infrastructure.image.renderer import PillowImageRenderer
from app.infrastructure.db.repositories.user import PostgresUserRepository
from app.infrastructure.db.repositories.reading import PostgresReadingRepository
from app.domain.services.spread_factory import SpreadFactory
from app.application.use_cases.perform_reading import PerformReadingUseCase
from app.application.use_cases.get_admin_stats import GetAdminStatsUseCase


class Container:
    def __init__(self, settings: Settings) -> None:
        # Синглтоны — один экземпляр на приложение
        self._llm = OpenRouterLLMAdapter(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
            timeout=settings.openrouter_timeout_seconds,
        )
        self._storage = S3StorageAdapter.from_settings(settings)
        self._image_renderer = PillowImageRenderer(settings)
        self._spread_factory = SpreadFactory()

    def reading_use_case(self, session: AsyncSession) -> PerformReadingUseCase:
        # Сессия — per-request зависимость
        return PerformReadingUseCase(
            user_repo=PostgresUserRepository(session),
            reading_repo=PostgresReadingRepository(session),
            llm=self._llm,
            storage=self._storage,
            image_renderer=self._image_renderer,
            spread_factory=self._spread_factory,
        )

    def admin_stats_use_case(self, session: AsyncSession) -> GetAdminStatsUseCase:
        return GetAdminStatsUseCase(
            user_repo=PostgresUserRepository(session),
            reading_repo=PostgresReadingRepository(session),
        )


@lru_cache
def get_container() -> Container:
    from app.core.config import settings
    return Container(settings)
```

---

### Тонкий Telegram-хэндлер

```python
# app/presentation/telegram/handlers/start.py
from telegram import Update
from telegram.ext import ContextTypes

from app.application.use_cases.perform_reading import (
    PerformReadingCommand, InjectionBlockedError,
)
from app.core.container import get_container
from app.infrastructure.db.engine import SessionLocal
from app.presentation.telegram.formatters.reading import send_reading_result
from app.presentation.telegram.formatters.keyboards import build_spread_keyboard

STATE_KEY = "tarot_state"
SPREAD_TYPE_KEY = "spread_type"
_INJECTION_MSG = "Карты туманны для такого запроса. Сформулируй вопрос проще."
_FAILED_MSG = "Не удалось получить трактовку. Попробуй позже."


async def question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    tg_user = update.effective_user
    user_data = context.user_data
    if not (message and tg_user and user_data and message.text):
        return

    spread_type = user_data.get(SPREAD_TYPE_KEY, "3_cards")
    cmd = PerformReadingCommand(
        platform="telegram",
        external_user_id=str(tg_user.id),
        user_display_name=tg_user.full_name or "",
        question=message.text.strip(),
        spread_type=spread_type,
    )

    container = get_container()
    try:
        async with SessionLocal() as session:
            result = await container.reading_use_case(session).execute(cmd)
    except InjectionBlockedError:
        await message.reply_text(_INJECTION_MSG)
        return
    except Exception:
        await message.reply_text(_FAILED_MSG)
        return

    await send_reading_result(message, result)
    await message.reply_text(
        "Если есть ещё вопросы, задавай.",
        reply_markup=build_spread_keyboard(spread_type),
    )
```

Хэндлер теперь: парсит Telegram-контекст → формирует platform-agnostic команду → вызывает use case → форматирует ответ для Telegram. Никакой бизнес-логики.

---

### FastAPI-эндпоинт (те же use cases)

```python
# app/presentation/api/v1/reading.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.container import get_container
from app.application.use_cases.perform_reading import PerformReadingCommand
from app.infrastructure.db.engine import get_db

router = APIRouter(prefix="/api/v1")


class ReadingRequest(BaseModel):
    user_id: str
    question: str
    spread_type: str = "3_cards"


@router.post("/reading")
async def create_reading(body: ReadingRequest, session: AsyncSession = Depends(get_db)):
    cmd = PerformReadingCommand(
        platform="web",
        external_user_id=body.user_id,
        user_display_name="",
        question=body.question,
        spread_type=body.spread_type,
    )
    result = await get_container().reading_use_case(session).execute(cmd)
    return {
        "interpretation": result.interpretation,
        "cards": result.cards_summary,
        "image_url": result.image_url,
    }
```

Тот же `PerformReadingUseCase`, нулевая дупликация бизнес-логики.

---

## 5. ПРИОРИТЕТНЫЙ ПЛАН РЕФАКТОРИНГА

### Фаза 1 — Изоляция (без ломки функциональности)

1. Создать `domain/entities/` с dataclass-сущностями и `SpreadType` как `Enum`
2. Создать `domain/ports/` с Protocol-интерфейсами
3. Перенести `prompt_guard` в `application/security/`
4. Извлечь `_call_api` в `LLMService` — убрать дублирование HTTP-кода

### Фаза 2 — Application Layer

5. Создать `PerformReadingUseCase` — перенести логику из `question_handler`
6. Создать `GetDailyCardUseCase` — убрать Telegram-специфику из `DailyCardService`
7. Переписать `AnalyticsService` как `GetAdminStatsUseCase` с вызовами репозиториев

### Фаза 3 — Infrastructure

8. Репозитории: заменить `commit()` на `flush()` внутри методов
9. `PostgresUserRepository` — добавить `platform` / `external_id` поля (миграция)
10. `OpenRouterLLMAdapter` — вынести за `ILLMProvider` протокол
11. `S3StorageAdapter` — вынести за `IStoragePort` протокол

### Фаза 4 — DI и тонкие хэндлеры

12. Создать `Container` — убрать модульные синглтоны
13. Переписать Telegram-хэндлеры как тонкие адаптеры
14. Добавить `tests/unit/application/` с моками портов
