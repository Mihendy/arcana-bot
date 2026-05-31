from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SpreadType(str, Enum):
    """Available tarot spread types.

    Inherits ``str`` so values compare equal to legacy string literals
    (e.g. ``SpreadType.THREE_CARDS == "3_cards"`` is ``True``), making
    incremental migration of existing code safe.
    """

    ONE_CARD = "1_card"
    THREE_CARDS = "3_cards"
    FIVE_CARDS_LINE = "5_cards_line"
    PENTAGRAM = "pentagram"


class ArcanaType(str, Enum):
    """Tarot arcana classification."""

    MAJOR = "major"
    MINOR = "minor"


@dataclass(frozen=True)
class TarotCard:
    """A card as drawn in a spread — combines deck identity with position context.

    Frozen because a drawn card is an immutable fact: the position, orientation,
    and card identity are fixed the moment the spread is generated.
    """

    id: int
    name: str
    slug: str
    arcana: ArcanaType
    is_reversed: bool
    position: int
    position_name: str | None = None


@dataclass
class SpreadResult:
    """Generated spread payload: cards drawn plus layout metadata.

    Not frozen because ``metadata`` is a plain dict (infrastructure detail
    that should not leak into the entity but is kept for backward compat
    during incremental migration).
    """

    spread_type: SpreadType
    cards: list[TarotCard]
    image_groups: list[list[int]]
    metadata: dict[str, Any] = field(default_factory=dict)
