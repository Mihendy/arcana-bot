"""Repository for reading persistence."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reading import Reading


class ReadingRepository:
    """CRUD operations for Reading model."""

    def __init__(self, session: AsyncSession) -> None:
        """Store session dependency.

        Args:
            session: Active SQLAlchemy async session.
        """
        self.session = session

    async def create_reading(
        self,
        user_id: int,
        question: str,
        spread_type: str,
        layout: dict[str, Any],
        interpretation: str,
        image_url: str | None,
        image_urls: list[str] | None = None,
    ) -> Reading:
        """Create and persist a tarot reading.

        Args:
            user_id: Internal user ID from ``users`` table.
            question: User question text.
            spread_type: Spread type identifier.
            layout: Serialized spread layout payload.
            interpretation: Generated LLM interpretation text.
            image_url: Optional local path or URL of generated spread image.
            image_urls: Optional list of local paths or URLs of generated spread images.

        Returns:
            Reading: Persisted reading entity.
        """
        reading = Reading(
            user_id=user_id,
            question=question,
            spread_type=spread_type,
            layout=layout,
            interpretation=interpretation,
            image_url=image_url,
            image_urls=image_urls,
        )
        self.session.add(reading)
        await self.session.commit()
        await self.session.refresh(reading)
        return reading
