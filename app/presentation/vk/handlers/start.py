"""VK /start (message_new) handler — registration and referral flow."""

from __future__ import annotations

import logging

from dishka import AsyncContainer
from vkbottle.bot import BotLabeler, Message

from app.application.use_cases.register_user import RegisterUserUseCase
from app.core.config import Settings
from app.domain.entities.tarot import SpreadType
from app.presentation.vk.formatters.keyboards import build_main_keyboard, build_spread_keyboard

logger = logging.getLogger(__name__)

_PLATFORM = "vk"
_GREETING_NEW = "Привет! Добро пожаловать в Arcana Bot."
_GREETING_RETURNING = "Привет! Рад тебя видеть снова."
_START_TEMPLATE = "{greeting}\n\nНапиши свой вопрос для расклада, и карты дадут ответ."
_PROMPT_SPREAD = "Выбери тип расклада:"
_SERVICE_UNAVAILABLE = "Сервис временно недоступен. Попробуй позже."
_REFERRAL_NOTIFICATION = (
    "🎉 По твоей ссылке зарегистрировался новый пользователь!\n\n"
    "Тебе начислено +3 дополнительных расклада. "
    "Проверить баланс можно в разделе «Профиль»."
)


def _parse_referrer_id(text: str | None) -> str | None:
    """Extract referrer id from VK deep-link payload (ref_XXXXXXX)."""
    if not text:
        return None
    # VK passes deep-link as the first word after the command word,
    # e.g. "start ref_123456789"
    parts = text.strip().split(maxsplit=1)
    payload = parts[1] if len(parts) > 1 else parts[0]
    if payload.startswith("ref_") and payload[4:].isdigit():
        return payload[4:]
    return None


def register(
    labeler: BotLabeler,
    container: AsyncContainer,
    settings: Settings,
    spread_store: dict[int, str],
) -> None:
    """Register start-related handlers on *labeler*."""

    @labeler.message(text=["start", "начать", "/start"])
    async def handle_start(message: Message) -> None:
        user_id = message.from_id
        display_name = str(user_id)  # VK API requires separate call for name; use ID as fallback
        referrer_id = _parse_referrer_id(message.text)

        try:
            async with container() as di:
                use_case: RegisterUserUseCase = await di.get(RegisterUserUseCase)
                reg = await use_case.execute(
                    platform=_PLATFORM,
                    external_id=str(user_id),
                    display_name=display_name,
                    referrer_external_id=referrer_id,
                )
        except Exception:
            logger.exception("vk start failed user_id=%s", user_id)
            await message.answer(_SERVICE_UNAVAILABLE)
            return

        if reg.is_new_user and reg.has_referrer and reg.referrer_external_id:
            try:
                from vkbottle import API
                api: API = message.ctx_api  # type: ignore[assignment]
                await api.messages.send(
                    user_id=int(reg.referrer_external_id),
                    message=_REFERRAL_NOTIFICATION,
                    random_id=0,
                )
            except Exception:
                logger.warning(
                    "vk referral push failed referrer=%s", reg.referrer_external_id
                )

        spread_store[user_id] = SpreadType.THREE_CARDS.value
        greeting = _GREETING_NEW if reg.is_new_user else _GREETING_RETURNING
        current_spread = SpreadType(spread_store[user_id])

        await message.answer(
            _START_TEMPLATE.format(greeting=greeting),
            keyboard=build_main_keyboard(),
        )
        await message.answer(_PROMPT_SPREAD, keyboard=build_spread_keyboard(current_spread))
        logger.info(
            "vk start user_id=%s is_new=%s has_referrer=%s",
            user_id, reg.is_new_user, reg.has_referrer,
        )
