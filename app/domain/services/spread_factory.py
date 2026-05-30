"""Pure domain service for tarot spread generation.

``SpreadFactory`` accepts a raw deck (list of dicts loaded from JSON by
infrastructure) and returns domain ``SpreadResult`` objects.  No I/O is
performed here — deck loading is the caller's responsibility.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from app.domain.entities.tarot import ArcanaType, SpreadResult, SpreadType, TarotCard


@dataclass(slots=True)
class _SpreadConfig:
    """Static configuration for one spread type."""

    card_count: int
    position_names: tuple[str, ...]
    image_groups: tuple[tuple[int, ...], ...]


_SPREAD_CONFIGS: dict[SpreadType, _SpreadConfig] = {
    SpreadType.ONE_CARD: _SpreadConfig(
        card_count=1,
        position_names=("Фокус",),
        image_groups=((1,),),
    ),
    SpreadType.THREE_CARDS: _SpreadConfig(
        card_count=3,
        position_names=("Прошлое", "Настоящее", "Будущее"),
        image_groups=((1, 2, 3),),
    ),
    SpreadType.FIVE_CARDS_LINE: _SpreadConfig(
        card_count=5,
        position_names=("1", "2", "3", "4", "5"),
        image_groups=((1, 2, 3, 4, 5),),
    ),
    SpreadType.PENTAGRAM: _SpreadConfig(
        card_count=5,
        position_names=("Земля", "Огонь", "Вода", "Воздух", "Дух"),
        image_groups=((1, 2, 3, 4, 5),),
    ),
}


class SpreadFactory:
    """Builds ``SpreadResult`` from a static tarot deck.

    The deck is injected as a list of plain dicts (same schema as
    ``tarot_deck.json``) so this class has zero I/O dependencies.
    The container (or any caller) is responsible for loading the deck.

    Example::

        from app.infrastructure.assets.tarot_data import tarot_data_service
        factory = SpreadFactory(raw_deck=tarot_data_service.get_deck())
        result = factory.build(SpreadType.THREE_CARDS)
    """

    def __init__(self, raw_deck: list[dict[str, Any]]) -> None:
        self._deck = raw_deck

    def build(
        self,
        spread_type: SpreadType,
        allow_reversed: bool = True,
        arcana_filter: str = "all",
    ) -> SpreadResult:
        """Draw cards and assemble a ``SpreadResult``.

        Args:
            spread_type: Desired spread layout.
            allow_reversed: When ``True`` each card may be drawn reversed.
            arcana_filter: ``"all"``, ``"major"``, or ``"minor"``.

        Returns:
            SpreadResult: Immutable snapshot of drawn cards and layout metadata.

        Raises:
            ValueError: For unknown spread type or arcana filter, or if
                the filtered deck is smaller than the requested card count.
        """
        config = _SPREAD_CONFIGS.get(spread_type)
        if config is None:
            raise ValueError(f"Unsupported spread_type: {spread_type!r}")

        deck = self._filter_deck(arcana_filter)
        if config.card_count > len(deck):
            raise ValueError(
                f"Spread requires {config.card_count} cards but filtered deck has {len(deck)}."
            )

        selected = random.sample(deck, k=config.card_count)
        cards = [
            TarotCard(
                id=raw["id"],
                name=raw["name"],
                slug=raw["slug"],
                arcana=ArcanaType(raw["arcana"]),
                is_reversed=bool(random.getrandbits(1)) if allow_reversed else False,
                position=pos,
                position_name=config.position_names[pos - 1]
                if pos - 1 < len(config.position_names)
                else None,
            )
            for pos, raw in enumerate(selected, start=1)
        ]
        return SpreadResult(
            spread_type=spread_type,
            cards=cards,
            image_groups=[list(group) for group in config.image_groups],
            metadata={
                "positions": list(config.position_names),
                "allow_reversed": allow_reversed,
                "arcana_filter": arcana_filter,
            },
        )

    def _filter_deck(self, arcana_filter: str) -> list[dict[str, Any]]:
        if arcana_filter == "all":
            return list(self._deck)
        if arcana_filter in {"major", "minor"}:
            return [card for card in self._deck if card["arcana"] == arcana_filter]
        raise ValueError(f"Unsupported arcana_filter: {arcana_filter!r}")
