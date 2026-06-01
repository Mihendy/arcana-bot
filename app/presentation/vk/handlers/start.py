"""VK start handler — registration, greeting, referral flow."""

from __future__ import annotations

import logging

from dishka import AsyncContainer
from vkbottle.bot import BotLabeler, Message

from app.application.use_cases.register_user import RegisterUserUseCase
from app.bot.spread_store import VKSessionStore
from app.core.config import Settings
from app.domain.entities.tarot import SpreadType
from app.presentation.vk.formatters.keyboards import (
    START_BUTTON_TEXT,
    build_main_keyboard,
    build_spread_keyboard,
)

logger = logging.getLogger(__name__)

_PLATFORM = "vk"

_GREETING_NEW = "Привет! Добро пожаловать в Arcana Bot."
_GREETING_RETURNING = "Привет! Рад тебя видеть снова."
_START_TEMPLATE = "{greeting}\n\nНапиши свой вопрос для расклада."
_PROMPT_SPREAD = "Выбери тип расклада:"
_SERVICE_UNAVAILABLE = "Сервис временно недоступен. Попробуй позже."
_REFERRAL_NOTIFICATION = (
    "🎉 По твоей ссылке зарегистрировался новый пользователь!\n\n"
    "Тебе начислено +3 дополнительных расклада. "
    "Проверить баланс можно в разделе «Профиль»."
)

START_TRIGGERS = frozenset({
    "start", "/start", "начать", "привет", "hi", "hello",
    START_BUTTON_TEXT.lower(),
})


async def resolve_display_name(message: Message, user_id: int, store: VKSessionStore) -> str:
    """Return display name from cache, or fetch from VK API and cache it."""
    cached = store.get_name(user_id)
    if cached is not None:
        return cached

    name = str(user_id)
    try:
        users = await message.ctx_api.users.get(user_ids=[user_id])
        if users:
            u = users[0]
            fetched = f"{u.first_name} {u.last_name}".strip()
            if fetched:
                name = fetched
    except Exception:
        logger.warning("vk users.get failed user_id=%s", user_id)

    store.set_name(user_id, name)
    return name


async def greet_user(
    message: Message,
    user_id: int,
    container: AsyncContainer,
    settings: Settings,
    store: VKSessionStore,
    *,
    referrer_id: str | None = None,
) -> None:
    """Register user (if new) and send greeting with main + spread keyboards."""
    display_name = await resolve_display_name(message, user_id, store)
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
        await message.answer(_SERVICE_UNAVAILABLE, keyboard=build_main_keyboard())
        return

    if reg.is_new_user and reg.has_referrer and reg.referrer_external_id:
        try:
            await message.ctx_api.messages.send(
                user_id=int(reg.referrer_external_id),
                message=_REFERRAL_NOTIFICATION,
                random_id=0,
            )
        except Exception:
            logger.warning("vk referral push failed referrer=%s", reg.referrer_external_id)

    store.set_spread(user_id, SpreadType.THREE_CARDS)
    greeting = _GREETING_NEW if reg.is_new_user else _GREETING_RETURNING

    await message.answer(_START_TEMPLATE.format(greeting=greeting), keyboard=build_main_keyboard())
    await message.answer(_PROMPT_SPREAD, keyboard=build_spread_keyboard(store.get_spread(user_id)))

    logger.info(
        "vk start user_id=%s is_new=%s has_referrer=%s",
        user_id, reg.is_new_user, reg.has_referrer,
    )


def _extract_ref(message: Message) -> str | None:
    ref: str | None = None
    for attr_path in (
        lambda m: getattr(m, "ref", None),
        lambda m: getattr(getattr(m, "object", None), "ref", None),
    ):
        try:
            ref = attr_path(message)
        except Exception:
            pass
        if ref:
            break
    if ref and isinstance(ref, str) and ref.startswith("ref_") and ref[4:].isdigit():
        return ref[4:]
    return None


def register(
    labeler: BotLabeler,
    container: AsyncContainer,
    settings: Settings,
    store: VKSessionStore,
) -> None:
    """Register start-related handlers on *labeler*."""

    @labeler.message(text=list(START_TRIGGERS) + [START_BUTTON_TEXT])
    async def handle_start(message: Message) -> None:
        user_id = message.from_id
        if store.has_user(user_id):
            await message.answer(
                _START_TEMPLATE.format(greeting=_GREETING_RETURNING),
                keyboard=build_main_keyboard(),
            )
            await message.answer(_PROMPT_SPREAD, keyboard=build_spread_keyboard(store.get_spread(user_id)))
            return
        referrer_id = _extract_ref(message)
        await greet_user(message, user_id, container, settings, store, referrer_id=referrer_id)
