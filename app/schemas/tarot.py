"""Schemas for tarot spreads."""

from typing import Literal

from pydantic import BaseModel


class SpreadCard(BaseModel):
    """Single card in generated spread."""

    id: int
    name: str
    slug: str
    arcana: Literal["major", "minor"]
    is_reversed: bool
    position: int
