"""Tarot deck data access helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, TypedDict

from app.core.config import settings


class TarotCard(TypedDict):
    """Card schema stored in tarot_deck.json."""

    id: int
    name: str
    slug: str
    arcana: Literal["major", "minor"]


class TarotDataService:
    """Loads tarot deck mapping and exposes card lookup."""

    def __init__(self, deck_path: Path | None = None) -> None:
        """Initialize deck storage and fast lookup cache.

        Args:
            deck_path: Optional custom path to the tarot deck JSON file.
        """
        self._deck_path = deck_path or Path(__file__).resolve().parent.parent / "assets" / "tarot_deck.json"
        self._cards: list[TarotCard] = self._load_cards()
        self._cards_by_id: dict[int, TarotCard] = {card["id"]: card for card in self._cards}

    def _load_cards(self) -> list[TarotCard]:
        """Load tarot card definitions from JSON file.

        Returns:
            list[TarotCard]: Parsed card list ordered as in source file.

        Raises:
            FileNotFoundError: If deck file does not exist.
            json.JSONDecodeError: If deck file has invalid JSON.
        """
        with self._deck_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return list(data)

    def get_card_by_id(self, card_id: int) -> TarotCard | None:
        """Return one card by its numeric id.

        Args:
            card_id: Card identifier from ``tarot_deck.json``.

        Returns:
            TarotCard | None: Card payload when found, otherwise ``None``.
        """
        return self._cards_by_id.get(card_id)

    def get_deck(self) -> list[TarotCard]:
        """Return a shallow copy of all available cards.

        Returns:
            list[TarotCard]: Complete tarot deck.
        """
        return list(self._cards)

    def verify_assets(self) -> None:
        """Validate that all card images exist on disk.

        Raises:
            FileNotFoundError: If one or more card images are missing.
        """
        missing_files = []
        for card in self._cards:
            png_file = settings.cards_assets_path / f"{card['slug']}.png"
            jpg_file = settings.cards_assets_path / f"{card['slug']}.jpg"
            if not png_file.is_file() and not jpg_file.is_file():
                missing_files.append(f"{card['slug']}.png/.jpg")

        if missing_files:
            preview = ", ".join(missing_files[:10])
            remainder = len(missing_files) - min(len(missing_files), 10)
            suffix = f" ... (+{remainder} more)" if remainder > 0 else ""
            raise FileNotFoundError(
                "Missing tarot card assets in "
                f"{settings.cards_assets_path}: {preview}{suffix}"
            )

    def get_card_asset_path(self, slug: str) -> Path:
        """Resolve image path for a card slug.

        Args:
            slug: Card slug used in asset file names.

        Returns:
            Path: Existing path to ``.png`` or ``.jpg`` card image.

        Raises:
            FileNotFoundError: If no asset exists for the provided slug.
        """
        png_file = settings.cards_assets_path / f"{slug}.png"
        if png_file.is_file():
            return png_file

        jpg_file = settings.cards_assets_path / f"{slug}.jpg"
        if jpg_file.is_file():
            return jpg_file

        raise FileNotFoundError(f"Card asset not found for slug '{slug}'.")


tarot_data_service = TarotDataService()
