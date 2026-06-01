"""Schemas for tarot spreads."""

from typing import Any, Literal

from pydantic import BaseModel

SpreadType = Literal["1_card", "3_cards", "5_cards_line", "pentagram"]


class SpreadCard(BaseModel):
    """Single card in generated spread."""

    id: int
    name: str
    slug: str
    arcana: Literal["major", "minor"]
    is_reversed: bool
    position: int
    position_name: str | None = None


class SpreadResult(BaseModel):
    """Generated spread payload with rendering metadata."""

    spread_type: SpreadType
    cards: list[SpreadCard]
    image_groups: list[list[int]]
    metadata: dict[str, Any]
