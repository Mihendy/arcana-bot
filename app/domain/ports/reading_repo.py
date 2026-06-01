from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from app.domain.entities.reading import Reading
from app.domain.entities.tarot import SpreadResult, SpreadType


class IReadingRepository(Protocol):
    """Abstract persistence contract for Reading aggregates."""

    async def create(
        self,
        user_id: int,
        question: str,
        spread: SpreadResult,
        interpretation: str,
        image_url: str | None,
    ) -> Reading:
        """Persist a completed tarot reading and return the stored entity."""
        ...

    async def count_since(self, since: datetime) -> int:
        """Return number of readings created at or after ``since``."""
        ...