"""Business logic for tarot spread generation."""

from __future__ import annotations

import random
from abc import ABC
from dataclasses import dataclass
from typing import Any

from app.schemas.tarot import SpreadCard, SpreadResult, SpreadType
from app.services.tarot_data import TarotCard, tarot_data_service


@dataclass(frozen=True)
class BaseSpreadStrategy(ABC):
    """Base strategy for one spread type generation."""

    spread_type: SpreadType
    card_count: int
    position_names: list[str]
    image_groups: list[list[int]]

    def build_result(
        self,
        selected_cards: list[TarotCard],
        allow_reversed: bool,
        arcana_filter: str,
    ) -> SpreadResult:
        """Build ``SpreadResult`` from selected deck cards.

        Args:
            selected_cards: Randomly sampled cards from filtered deck.
            allow_reversed: Whether reversed orientation is allowed.
            arcana_filter: Arcana filter used for deck selection.

        Returns:
            SpreadResult: Final spread payload.
        """
        cards = [
            SpreadCard(
                id=card["id"],
                name=card["name"],
                slug=card["slug"],
                arcana=card["arcana"],
                is_reversed=bool(random.getrandbits(1)) if allow_reversed else False,
                position=position,
                position_name=self.position_names[position - 1] if position - 1 < len(self.position_names) else None,
            )
            for position, card in enumerate(selected_cards, start=1)
        ]
        return SpreadResult(
            spread_type=self.spread_type,
            cards=cards,
            image_groups=self.image_groups,
            metadata={
                "positions": self.position_names,
                "allow_reversed": allow_reversed,
                "arcana_filter": arcana_filter,
            },
        )


class OneCardSpreadStrategy(BaseSpreadStrategy):
    """Strategy for one-card spread."""

    def __init__(self) -> None:
        super().__init__(
            spread_type="1_card",
            card_count=1,
            position_names=["Фокус"],
            image_groups=[[1]],
        )


class ThreeCardsSpreadStrategy(BaseSpreadStrategy):
    """Strategy for classic three-card spread."""

    def __init__(self) -> None:
        super().__init__(
            spread_type="3_cards",
            card_count=3,
            position_names=["Прошлое", "Настоящее", "Будущее"],
            image_groups=[[1, 2, 3]],
        )


class FiveCardsLineSpreadStrategy(BaseSpreadStrategy):
    """Strategy for five cards in a line spread."""

    def __init__(self) -> None:
        super().__init__(
            spread_type="5_cards_line",
            card_count=5,
            position_names=["1", "2", "3", "4", "5"],
            image_groups=[[1, 2, 3, 4, 5]],
        )


class PentagramSpreadStrategy(BaseSpreadStrategy):
    """Strategy for pentagram spread."""

    def __init__(self) -> None:
        super().__init__(
            spread_type="pentagram",
            card_count=5,
            position_names=["Земля", "Огонь", "Вода", "Воздух", "Дух"],
            image_groups=[[1, 2, 3, 4, 5]],
        )


class TarotService:
    """Service for tarot spread generation."""

    def __init__(self) -> None:
        """Initialize available spread strategies."""
        strategies = (
            OneCardSpreadStrategy(),
            ThreeCardsSpreadStrategy(),
            FiveCardsLineSpreadStrategy(),
            PentagramSpreadStrategy(),
        )
        self._strategies: dict[SpreadType, BaseSpreadStrategy] = {
            strategy.spread_type: strategy for strategy in strategies
        }

    async def generate_spread(
        self,
        spread_type: SpreadType = "3_cards",
        allow_reversed: bool = True,
        arcana_filter: str = "all",
    ) -> SpreadResult:
        """Generate spread cards and metadata for selected spread type.

        Args:
            spread_type: Spread type key.
            allow_reversed: Whether reversed orientation is allowed.
            arcana_filter: Arcana selection scope (``all``, ``major``, ``minor``).

        Returns:
            SpreadResult: Generated cards and spread layout metadata.

        Raises:
            ValueError: If spread configuration is invalid.
        """
        strategy = self._get_strategy(spread_type)
        deck = self._filter_deck(arcana_filter)
        if strategy.card_count > len(deck):
            raise ValueError("Requested spread size cannot exceed filtered deck size.")

        selected_cards = random.sample(deck, k=strategy.card_count)
        return strategy.build_result(
            selected_cards=selected_cards,
            allow_reversed=allow_reversed,
            arcana_filter=arcana_filter,
        )

    def _get_strategy(self, spread_type: SpreadType) -> BaseSpreadStrategy:
        """Resolve strategy by spread type.

        Args:
            spread_type: Spread type key.

        Returns:
            BaseSpreadStrategy: Spread strategy instance.

        Raises:
            ValueError: If spread type is not supported.
        """
        strategy = self._strategies.get(spread_type)
        if strategy is None:
            raise ValueError(f"Unsupported spread_type '{spread_type}'.")
        return strategy

    def _filter_deck(self, arcana_filter: str) -> list[TarotCard]:
        """Filter tarot deck by arcana mode.

        Args:
            arcana_filter: Arcana scope value.

        Returns:
            list[TarotCard]: Filtered card deck.

        Raises:
            ValueError: If unknown arcana filter is provided.
        """
        deck = tarot_data_service.get_deck()
        if arcana_filter == "all":
            return deck
        if arcana_filter in {"major", "minor"}:
            return [card for card in deck if card["arcana"] == arcana_filter]
        raise ValueError(f"Unsupported arcana_filter '{arcana_filter}'.")


tarot_service = TarotService()
