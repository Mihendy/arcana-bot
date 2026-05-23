from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.reading import Reading
from app.domain.entities.tarot import SpreadResult, SpreadType
from app.infrastructure.db.models.reading import ReadingORM


class PostgresReadingRepository:
    """Implements IReadingRepository against PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: int,
        question: str,
        spread: SpreadResult,
        interpretation: str,
        image_url: str | None,
    ) -> Reading:
        """Persist a completed reading.

        ``image_url`` is normalised into a one-element ``image_urls`` list so
        the ORM model never stores the legacy scalar column.
        No ``commit()`` — the outer unit-of-work (use case) owns the transaction.
        """
        orm = ReadingORM(
            user_id=user_id,
            question=question,
            spread_type=spread.spread_type.value,
            layout=_spread_to_layout(spread),
            interpretation=interpretation,
            image_urls=[image_url] if image_url else [],
        )
        self._session.add(orm)
        await self._session.flush()  # populate orm.id, no commit
        return _reading_to_entity(orm)

    async def count_since(self, since: datetime) -> int:
        """Return number of readings created at or after ``since``."""
        result = await self._session.execute(
            select(func.count(ReadingORM.id)).where(ReadingORM.created_at >= since)
        )
        return int(result.scalar() or 0)

    async def count_all(self) -> int:
        """Return total number of readings across all time."""
        result = await self._session.execute(select(func.count(ReadingORM.id)))
        return int(result.scalar() or 0)


def _spread_to_layout(spread: SpreadResult) -> dict[str, Any]:
    """Serialise SpreadResult to the JSONB layout payload for storage."""
    return {
        "spread_type": spread.spread_type.value,
        "cards": [
            {
                "id": card.id,
                "position": card.position,
                "position_name": card.position_name,
                "is_reversed": card.is_reversed,
            }
            for card in spread.cards
        ],
        "image_groups": spread.image_groups,
        "metadata": spread.metadata,
    }


def _reading_to_entity(row: ReadingORM) -> Reading:
    return Reading(
        id=row.id,
        user_id=row.user_id,
        question=row.question,
        spread_type=SpreadType(row.spread_type),
        interpretation=row.interpretation,
        image_urls=list(row.image_urls or []),
        created_at=row.created_at,
    )
