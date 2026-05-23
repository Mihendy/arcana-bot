"""Keyboard builders for the Arcana Bot."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.domain.entities.tarot import SpreadType

PROFILE_BUTTON_TEXT = "👤 Профиль"


def build_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent bottom keyboard shown after /start.

    Returns:
        ReplyKeyboardMarkup: one-button keyboard with the profile shortcut.
    """
    return ReplyKeyboardMarkup(
        [[KeyboardButton(PROFILE_BUTTON_TEXT)]],
        resize_keyboard=True,
        is_persistent=True,
    )

_SPREAD_LABELS: dict[SpreadType, str] = {
    SpreadType.ONE_CARD: "1 карта",
    SpreadType.THREE_CARDS: "3 карты",
    SpreadType.FIVE_CARDS_LINE: "5 карт",
    SpreadType.PENTAGRAM: "Пентаграмма",
}


def build_spread_keyboard(current: SpreadType) -> InlineKeyboardMarkup:
    """Build inline keyboard with a checkmark on the currently selected spread.

    Args:
        current: The spread type currently selected by the user.

    Returns:
        InlineKeyboardMarkup: 2×2 keyboard with spread options.
    """

    def _label(st: SpreadType) -> str:
        prefix = "✅ " if st == current else ""
        return f"{prefix}{_SPREAD_LABELS[st]}"

    rows = [
        [
            InlineKeyboardButton(_label(SpreadType.ONE_CARD), callback_data="spread:1_card"),
            InlineKeyboardButton(_label(SpreadType.THREE_CARDS), callback_data="spread:3_cards"),
        ],
        [
            InlineKeyboardButton(_label(SpreadType.FIVE_CARDS_LINE), callback_data="spread:5_cards_line"),
            InlineKeyboardButton(_label(SpreadType.PENTAGRAM), callback_data="spread:pentagram"),
        ],
    ]
    return InlineKeyboardMarkup(rows)
