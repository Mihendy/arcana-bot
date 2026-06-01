"""VK keyboard builders."""

from __future__ import annotations

from vkbottle import Keyboard, KeyboardButtonColor
from vkbottle.tools.keyboard import Callback, Text, VKApps

from app.domain.entities.tarot import SpreadType

_SPREAD_LABELS: dict[SpreadType, str] = {
    SpreadType.ONE_CARD: "1 карта",
    SpreadType.THREE_CARDS: "3 карты",
    SpreadType.FIVE_CARDS_LINE: "5 карт",
    SpreadType.PENTAGRAM: "Пентаграмма",
}

PROFILE_BUTTON_TEXT = "👤 Профиль"
START_BUTTON_TEXT = "Старт"


def build_main_keyboard() -> str:
    """Persistent reply keyboard shown after /start.

    Returns:
        str: JSON keyboard string for ``keyboard`` parameter of ``messages.send``.
    """
    kb = Keyboard(one_time=False, inline=False)
    kb.add(Text(START_BUTTON_TEXT), color=KeyboardButtonColor.POSITIVE)
    kb.add(Text(PROFILE_BUTTON_TEXT), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()


def build_story_keyboard(app_id: int, group_id: int, hash_params: str) -> str:
    """Inline keyboard with a single 'Share to stories' button.

    Args:
        app_id: VK Mini App ID.
        group_id: VK group ID (positive); converted to negative owner_id internally.
        hash_params: URL-encoded params forwarded to the mini app as vk_hash.

    Returns:
        str: JSON keyboard string for ``keyboard`` parameter of ``messages.send``.
    """
    kb = Keyboard(inline=True)
    kb.add(VKApps(
        app_id=app_id,
        owner_id=-group_id,
        label="Поделиться в сторис",
        hash=hash_params,
    ))
    return kb.get_json()


def build_spread_keyboard(current: SpreadType) -> str:
    """Inline callback keyboard for spread type selection.

    The currently selected spread gets a ✅ prefix. Returns JSON string.
    """
    kb = Keyboard(inline=True)

    def _label(st: SpreadType) -> str:
        return f"✅ {_SPREAD_LABELS[st]}" if st == current else _SPREAD_LABELS[st]

    kb.add(Callback(_label(SpreadType.ONE_CARD), {"action": "spread", "type": "1_card"}))
    kb.add(Callback(_label(SpreadType.THREE_CARDS), {"action": "spread", "type": "3_cards"}))
    kb.row()
    kb.add(Callback(_label(SpreadType.FIVE_CARDS_LINE), {"action": "spread", "type": "5_cards_line"}))
    kb.add(Callback(_label(SpreadType.PENTAGRAM), {"action": "spread", "type": "pentagram"}))
    return kb.get_json()
