"""VK reading flow — spread selection (callback) and question handling."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dishka import AsyncContainer
from vkbottle import GroupEventType
from vkbottle.bot import BotLabeler, Message, MessageEvent

from app.application.dto.reading import PerformReadingCommand
from app.application.exceptions import InsufficientLimitsError
from app.application.use_cases.perform_reading import InjectionBlockedError, PerformReadingUseCase
from app.core.config import Settings
from app.domain.entities.tarot import SpreadType
from app.infrastructure.vk.photo_uploader import VKPhotoUploader
from app.presentation.vk.formatters.keyboards import build_spread_keyboard
from app.presentation.vk.formatters.reading import send_reading_result

logger = logging.getLogger(__name__)

_PLATFORM = "vk"
_MSK = ZoneInfo("Europe/Moscow")

_PROMPT_SPREAD = "Выбери тип расклада:"
_PROMPT_AGAIN = "Если есть ещё вопросы, задавай."
_INJECTION_BLOCKED = (
    "Карты туманны для такого запроса. "
    "Сформулируй вопрос проще и без служебных инструкций."
)
_INTERPRETATION_FAILED = (
    "Не удалось получить трактовку прямо сейчас. Попробуй чуть позже."
)
_LIMITS_EXHAUSTED_TEMPLATE = (
    "Закончились ежедневные расклады 🌙\n\n"
    "Новые бесплатные расклады появятся через {time_until}. "
    "Хочешь ещё сейчас? Пригласи друга по своей реферальной ссылке "
    "и получи +3 расклада за каждого!\n\n"
    "Твоя ссылка: {ref_url}"
)


def _time_until_midnight_msk() -> str:
    now = datetime.now(_MSK)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    total_minutes = max(1, int((midnight - now).total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours} ч. {minutes} мин." if hours else f"{minutes} мин."


def register(
    labeler: BotLabeler,
    container: AsyncContainer,
    settings: Settings,
    spread_store: dict[int, str],
    uploader: VKPhotoUploader,
) -> None:
    """Register reading flow handlers on *labeler*."""

    @labeler.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent)
    async def handle_spread_callback(event: MessageEvent) -> None:
        """Handle inline keyboard spread selection."""
        payload = event.payload or {}
        if payload.get("action") != "spread":
            return

        raw_type = payload.get("type", "")
        try:
            spread_type = SpreadType(raw_type)
        except ValueError:
            await event.show_snackbar("Неизвестный тип расклада.")
            return

        user_id = event.user_id
        if spread_store.get(user_id) == spread_type.value:
            await event.show_snackbar("")  # acknowledge without change
            return

        spread_store[user_id] = spread_type.value
        await event.edit_message(
            keyboard=build_spread_keyboard(spread_type),
        )

    @labeler.message()
    async def handle_question(message: Message) -> None:
        """Process any plain-text message as a tarot question."""
        user_id = message.from_id
        text = (message.text or "").strip()

        if not text:
            return

        spread_value = spread_store.get(user_id, SpreadType.THREE_CARDS.value)
        try:
            spread_type = SpreadType(spread_value)
        except ValueError:
            spread_type = SpreadType.THREE_CARDS

        cmd = PerformReadingCommand(
            question=text,
            spread_type=spread_type,
            platform=_PLATFORM,
            external_user_id=str(user_id),
            user_display_name=str(user_id),
        )

        try:
            async with container() as di:
                use_case: PerformReadingUseCase = await di.get(PerformReadingUseCase)
                result = await use_case.execute(cmd)
        except InsufficientLimitsError:
            ref_url = f"{settings.vk_public_url}?ref=ref_{user_id}"
            await message.answer(
                _LIMITS_EXHAUSTED_TEMPLATE.format(
                    time_until=_time_until_midnight_msk(),
                    ref_url=ref_url,
                )
            )
            return
        except InjectionBlockedError:
            await message.answer(_INJECTION_BLOCKED)
            return
        except Exception:
            logger.exception("vk reading failed user_id=%s", user_id)
            await message.answer(_INTERPRETATION_FAILED)
            return

        await send_reading_result(message, result, uploader)

        current = SpreadType(spread_store.get(user_id, SpreadType.THREE_CARDS.value))
        await message.answer(
            f"{_PROMPT_AGAIN}\n{_PROMPT_SPREAD}",
            keyboard=build_spread_keyboard(current),
        )
