"""VK reading flow — spread selection (callback) and question handling."""

from __future__ import annotations

import logging

from dishka import AsyncContainer
from vkbottle import GroupEventType
from vkbottle.bot import BotLabeler, Message, MessageEvent

from app.application.dto.reading import PerformReadingCommand
from app.application.exceptions import InjectionBlockedError, InsufficientLimitsError
from app.bot.spread_store import VKSessionStore
from app.bot.utils import time_until_midnight_msk
from app.application.use_cases.perform_reading import PerformReadingUseCase
from app.core.config import Settings
from app.domain.entities.tarot import SpreadType
from app.infrastructure.vk.photo_uploader import VKPhotoUploader
from app.presentation.vk.formatters.keyboards import (
    PROFILE_BUTTON_TEXT,
    build_main_keyboard,
    build_spread_keyboard,
)
from app.presentation.vk.formatters.reading import send_reading_result
from app.presentation.vk.handlers.start import START_TRIGGERS, greet_user, resolve_display_name

logger = logging.getLogger(__name__)

_PLATFORM = "vk"

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

_PROFILE_TRIGGERS = frozenset({"профиль", "/profile", PROFILE_BUTTON_TEXT.lower()})


def register(
    labeler: BotLabeler,
    container: AsyncContainer,
    settings: Settings,
    store: VKSessionStore,
    uploader: VKPhotoUploader,
) -> None:
    """Register reading flow handlers on *labeler*."""

    @labeler.raw_event(GroupEventType.MESSAGE_EVENT, MessageEvent)
    async def handle_spread_callback(event: MessageEvent) -> None:
        payload = event.payload or {}
        if payload.get("action") != "spread":
            return

        raw_type = payload.get("type", "")
        try:
            spread_type = SpreadType(raw_type)
        except ValueError:
            await event.show_snackbar("Неизвестный тип расклада.")
            return

        user_id = event.object.user_id
        if store.get_spread(user_id) == spread_type:
            await event.show_snackbar("Уже выбрано")
            return

        store.set_spread(user_id, spread_type)
        await event.edit_message(
            message=_PROMPT_SPREAD,
            keyboard=build_spread_keyboard(spread_type),
        )

    @labeler.message()
    async def handle_question(message: Message) -> None:
        user_id = message.from_id
        text = (message.text or "").strip()

        if not text:
            return

        text_lower = text.lower()

        if text_lower in _PROFILE_TRIGGERS:
            return

        if not store.has_user(user_id):
            await greet_user(message, user_id, container, settings, store)
            return

        spread_type = store.get_spread(user_id)
        display_name = await resolve_display_name(message, user_id, store)

        cmd = PerformReadingCommand(
            question=text,
            spread_type=spread_type,
            platform=_PLATFORM,
            external_user_id=str(user_id),
            user_display_name=display_name,
        )

        try:
            async with container() as di:
                use_case: PerformReadingUseCase = await di.get(PerformReadingUseCase)
                result = await use_case.execute(cmd)
        except InsufficientLimitsError:
            ref_url = f"{settings.vk_public_url}?ref=ref_{user_id}"
            await message.answer(
                _LIMITS_EXHAUSTED_TEMPLATE.format(
                    time_until=time_until_midnight_msk(),
                    ref_url=ref_url,
                ),
                keyboard=build_main_keyboard(),
            )
            return
        except InjectionBlockedError:
            await message.answer(_INJECTION_BLOCKED, keyboard=build_main_keyboard())
            return
        except Exception:
            logger.exception("vk reading failed user_id=%s", user_id)
            await message.answer(_INTERPRETATION_FAILED, keyboard=build_main_keyboard())
            return

        await send_reading_result(message, result, uploader)

        await message.answer(
            f"{_PROMPT_AGAIN}\n{_PROMPT_SPREAD}",
            keyboard=build_spread_keyboard(store.get_spread(user_id)),
        )
