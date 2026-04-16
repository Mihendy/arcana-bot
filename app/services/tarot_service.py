"""Business logic for tarot spread generation."""

from __future__ import annotations

import random

from app.schemas.tarot import SpreadCard
from app.services.tarot_data import tarot_data_service


class TarotService:
    """Service for tarot spread generation."""

    async def generate_spread(self, count: int = 3) -> list[SpreadCard]:
        """Generate spread with unique cards and random orientation."""
        deck = tarot_data_service.get_deck()
        if count < 1:
            raise ValueError("count must be greater than 0")
        if count > len(deck):
            raise ValueError("count cannot exceed deck size")

        selected_cards = random.sample(deck, k=count)
        return [
            SpreadCard(
                id=card["id"],
                name=card["name"],
                slug=card["slug"],
                arcana=card["arcana"],
                is_reversed=bool(random.getrandbits(1)),
                position=position,
            )
            for position, card in enumerate(selected_cards, start=1)
        ]


tarot_service = TarotService()
