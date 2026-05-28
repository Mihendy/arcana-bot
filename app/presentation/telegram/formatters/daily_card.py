"""Daily card caption and share-story URL builders.

All Telegram-specific URL construction that used to live in
``DailyCardService._build_share_story_miniapp_url`` and
``DailyCardService._to_russian_card_name`` is moved here so the use
case stays platform-agnostic.
"""

from __future__ import annotations

from urllib.parse import urlencode

from app.application.dto.daily_card import DailyCardResult
from app.core.config import Settings


def build_caption(result: DailyCardResult) -> str:
    """Build the Telegram photo caption for a daily card broadcast."""
    return f"Карта дня: {result.card_name}\n\n{result.interpretation}"


def build_share_story_url(
    result: DailyCardResult,
    settings: Settings,
    tg_id: str | None = None,
) -> str:
    """Build the Mini App URL that triggers ``shareToStory``.

    Args:
        result: Daily card data from use case.
        settings: Application settings (for base URL and bot URL).
        tg_id: Telegram user ID; when provided the share widget link becomes
            a personalised referral URL (``?start=ref_{tg_id}``).

    Returns:
        str: Fully-encoded Mini App share URL.
    """
    share_text = f"Моя карта дня: {_to_russian_card_name(result.card_name)}"
    base = f"{settings.api_public_base_url}/miniapp/share-story.html"
    if tg_id:
        referral_url = f"{settings.bot_public_url}?start=ref_{tg_id}"
    else:
        referral_url = settings.bot_public_url
    query = urlencode(
        {
            "image_url": result.image_url,
            "text": share_text[:220],
            "widget_url": referral_url,
            "widget_name": "Узнать свою карту дня",
        }
    )
    return f"{base}?{query}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_MAJOR_ARCANA_RU: dict[str, str] = {
    "The Fool": "Шут",
    "The Magician": "Маг",
    "The High Priestess": "Верховная Жрица",
    "The Empress": "Императрица",
    "The Emperor": "Император",
    "The Hierophant": "Иерофант",
    "The Lovers": "Влюбленные",
    "The Chariot": "Колесница",
    "Strength": "Сила",
    "The Hermit": "Отшельник",
    "Wheel of Fortune": "Колесо Фортуны",
    "Justice": "Справедливость",
    "The Hanged Man": "Повешенный",
    "Death": "Смерть",
    "Temperance": "Умеренность",
    "The Devil": "Дьявол",
    "The Tower": "Башня",
    "The Star": "Звезда",
    "The Moon": "Луна",
    "The Sun": "Солнце",
    "Judgement": "Суд",
    "The World": "Мир",
}

_RANK_RU: dict[str, str] = {
    "Ace": "Туз", "Two": "Двойка", "Three": "Тройка", "Four": "Четверка",
    "Five": "Пятерка", "Six": "Шестерка", "Seven": "Семерка", "Eight": "Восьмерка",
    "Nine": "Девятка", "Ten": "Десятка", "Page": "Паж", "Knight": "Рыцарь",
    "Queen": "Королева", "King": "Король",
}

_SUIT_RU: dict[str, str] = {
    "Wands": "Жезлов", "Cups": "Кубков", "Swords": "Мечей", "Pentacles": "Пентаклей",
}


def _to_russian_card_name(english_name: str) -> str:
    """Translate a card's English name to Russian for share text."""
    if english_name in _MAJOR_ARCANA_RU:
        return _MAJOR_ARCANA_RU[english_name]
    if " of " not in english_name:
        return english_name
    rank_en, suit_en = english_name.split(" of ", 1)
    rank_ru = _RANK_RU.get(rank_en.strip())
    suit_ru = _SUIT_RU.get(suit_en.strip())
    if rank_ru and suit_ru:
        return f"{rank_ru} {suit_ru}"
    return english_name
