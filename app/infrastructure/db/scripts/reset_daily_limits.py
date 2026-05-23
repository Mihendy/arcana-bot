"""One-shot script: restore daily_limit = 3 for every user who has spent readings.

Touches only rows where daily_limit < 3, so users who never used all their
daily readings are skipped — no unnecessary WAL writes.

Local:
    python -m app.infrastructure.db.scripts.reset_daily_limits

Docker (pass -T so cron doesn't allocate a TTY):
    docker compose exec -T app uv run python -m app.infrastructure.db.scripts.reset_daily_limits

Server cron (00:00 MSK = 21:00 UTC):
    0 21 * * * cd /srv/arcana-bot && docker compose exec -T app \\
        uv run python -m app.infrastructure.db.scripts.reset_daily_limits \\
        >> /var/log/arcana-limits-reset.log 2>&1
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.infrastructure.db.models.user import UserORM

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_DAILY_LIMIT_DEFAULT = 3


async def reset_daily_limits() -> None:
    from sqlalchemy import update

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            result = await session.execute(
                update(UserORM)
                .where(UserORM.daily_limit < _DAILY_LIMIT_DEFAULT)
                .values(daily_limit=_DAILY_LIMIT_DEFAULT)
            )
            await session.commit()
        logger.info(
            "reset complete: %d rows updated to daily_limit=%d",
            result.rowcount,
            _DAILY_LIMIT_DEFAULT,
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reset_daily_limits())
