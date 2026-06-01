"""Dishka DI providers for the Arcana Bot application.

Two provider classes, two scopes:

``InfraProvider`` (Scope.APP)
    Singletons that live for the entire process lifetime: database engine,
    session factory, LLM adapter, S3 adapter, image renderer, spread factory.

``SessionProvider`` (Scope.REQUEST)
    Short-lived objects created once per handler invocation: DB session,
    repositories, and all use-case instances.  The session is yielded so
    SQLAlchemy can do its own cleanup on scope exit.

Usage::

    from dishka import make_async_container
    from app.infrastructure.di.providers import InfraProvider, SessionProvider

    container = make_async_container(InfraProvider(), SessionProvider())

    # in a PTB handler:
    async with container() as di:
        use_case = await di.get(PerformReadingUseCase)
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.application.use_cases.get_admin_stats import GetAdminStatsUseCase
from app.application.use_cases.get_daily_card import GetDailyCardUseCase
from app.application.use_cases.get_user_profile import GetUserProfileUseCase
from app.application.use_cases.perform_reading import PerformReadingUseCase
from app.application.use_cases.register_user import RegisterUserUseCase
from app.core.config import Settings, settings as _settings
from app.domain.ports.image_renderer import IImageRenderer
from app.domain.ports.llm_port import ILLMProvider
from app.domain.ports.llm_usage_repo import ILLMUsageRepository
from app.domain.ports.payment_repo import IPaymentRepository
from app.domain.ports.reading_repo import IReadingRepository
from app.domain.ports.storage_port import IStoragePort
from app.domain.ports.unit_of_work import IUnitOfWork
from app.domain.ports.user_repo import IUserRepository
from app.domain.services.spread_factory import SpreadFactory
from app.infrastructure.assets.image_service import ImageService
from app.infrastructure.assets.tarot_data import TarotDataService
from app.infrastructure.db.uow import SqlAlchemyUoW
from app.infrastructure.db.repositories.llm_usage import PostgresLLMUsageRepository
from app.infrastructure.db.repositories.payment import PostgresPaymentRepository
from app.infrastructure.db.repositories.reading import PostgresReadingRepository
from app.infrastructure.db.repositories.user import PostgresUserRepository
from app.infrastructure.image.renderer import PillowImageRenderer
from app.infrastructure.llm.openrouter import OpenRouterLLMAdapter
from app.infrastructure.storage.s3 import S3StorageAdapter


class InfraProvider(Provider):
    """Application-scoped singletons (one instance per process)."""

    scope = Scope.APP

    @provide
    def get_settings(self) -> Settings:
        return _settings

    @provide
    async def get_engine(self, s: Settings) -> AsyncIterator[AsyncEngine]:
        engine = create_async_engine(s.database_url, pool_pre_ping=True)
        yield engine
        await engine.dispose()

    @provide
    def get_session_factory(
        self, engine: AsyncEngine
    ) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    @provide
    def get_llm(self, s: Settings) -> ILLMProvider:
        return OpenRouterLLMAdapter(
            api_key=s.openrouter_api_key,
            model=s.openrouter_model,
            base_url=s.openrouter_base_url,
            timeout=s.openrouter_timeout_seconds,
        )

    @provide
    def get_storage(self, s: Settings) -> IStoragePort:
        return S3StorageAdapter.from_settings(s)

    @provide
    def get_image_service(self) -> ImageService:
        return ImageService()

    @provide
    def get_image_renderer(self, svc: ImageService) -> IImageRenderer:
        return PillowImageRenderer(svc)

    @provide
    def get_tarot_data(self) -> TarotDataService:
        return TarotDataService()

    @provide
    def get_spread_factory(self, td: TarotDataService) -> SpreadFactory:
        return SpreadFactory(raw_deck=td.get_deck())


class SessionProvider(Provider):
    """Request-scoped objects (one instance per handler invocation)."""

    scope = Scope.REQUEST

    @provide
    async def get_session(
        self, factory: async_sessionmaker[AsyncSession]
    ) -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    @provide
    def get_uow(self, session: AsyncSession) -> IUnitOfWork:
        return SqlAlchemyUoW(session)

    @provide
    def get_user_repo(self, session: AsyncSession) -> IUserRepository:
        return PostgresUserRepository(session)

    @provide
    def get_payment_repo(self, session: AsyncSession) -> IPaymentRepository:
        return PostgresPaymentRepository(session)

    @provide
    def get_reading_repo(self, session: AsyncSession) -> IReadingRepository:
        return PostgresReadingRepository(session)

    @provide
    def get_llm_usage_repo(self, session: AsyncSession) -> ILLMUsageRepository:
        return PostgresLLMUsageRepository(session)

    @provide
    def get_register_user(
        self,
        user_repo: IUserRepository,
        uow: IUnitOfWork,
    ) -> RegisterUserUseCase:
        return RegisterUserUseCase(user_repo=user_repo, uow=uow)

    @provide
    def get_perform_reading(
        self,
        uow: IUnitOfWork,
        user_repo: IUserRepository,
        reading_repo: IReadingRepository,
        llm_usage_repo: ILLMUsageRepository,
        llm: ILLMProvider,
        storage: IStoragePort,
        image_renderer: IImageRenderer,
        spread_factory: SpreadFactory,
        settings: Settings,
    ) -> PerformReadingUseCase:
        return PerformReadingUseCase(
            uow=uow,
            user_repo=user_repo,
            reading_repo=reading_repo,
            llm_usage_repo=llm_usage_repo,
            llm=llm,
            storage=storage,
            image_renderer=image_renderer,
            spread_factory=spread_factory,
            settings=settings,
        )

    @provide
    def get_daily_card_use_case(
        self,
        llm: ILLMProvider,
        storage: IStoragePort,
        image_renderer: IImageRenderer,
        spread_factory: SpreadFactory,
    ) -> GetDailyCardUseCase:
        return GetDailyCardUseCase(
            llm=llm,
            storage=storage,
            image_renderer=image_renderer,
            spread_factory=spread_factory,
        )

    @provide
    def get_user_profile_use_case(
        self, user_repo: IUserRepository, s: Settings
    ) -> GetUserProfileUseCase:
        return GetUserProfileUseCase(user_repo=user_repo, settings=s)

    @provide
    def get_admin_stats_use_case(
        self,
        user_repo: IUserRepository,
        reading_repo: IReadingRepository,
        llm_usage_repo: ILLMUsageRepository,
    ) -> GetAdminStatsUseCase:
        return GetAdminStatsUseCase(
            user_repo=user_repo,
            reading_repo=reading_repo,
            llm_usage_repo=llm_usage_repo,
        )
