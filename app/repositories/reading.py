"""Repository for reading persistence."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reading import Reading


class ReadingRepository:
    """CRUD operations for Reading model."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_reading(
        self,
        user_id: int,
        question: str,
        layout: dict,
        interpretation: str,
        image_url: str | None,
    ) -> Reading:
        """Create reading with generated layout and interpretation."""
        reading = Reading(
            user_id=user_id,
            question=question,
            layout=layout,
            interpretation=interpretation,
            image_url=image_url,
        )
        self.session.add(reading)
        await self.session.commit()
        await self.session.refresh(reading)
        return reading
