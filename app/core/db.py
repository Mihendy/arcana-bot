"""Async SQLAlchemy session setup."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield request-scoped async database session.

    Yields:
        AsyncSession: Open SQLAlchemy async session bound to the app engine.
    """
    async with SessionLocal() as session:
        yield session


async def check_db_health() -> bool:
    """Check database connectivity with a lightweight query.

    Returns:
        bool: ``True`` if the database responds to ``SELECT 1``, otherwise ``False``.
    """
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
