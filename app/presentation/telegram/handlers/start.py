"""Thin start, question and spread-selection handlers.

Each handler opens a single dishka REQUEST scope, pulls the relevant
use case, and delegates all business logic to it.  No direct DB or
service imports live here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    BaseHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.application.dto.reading import PerformReadingCommand
from app.application.exceptions import InsufficientLimitsError
from app.application.use_cases.perform_reading import InjectionBlockedError, PerformReadingUseCase
from app.application.use_cases.register_user import RegisterUserUseCase
from app.bot.states import TarotState
from app.domain.entities.tarot import SpreadType
from app.presentation.telegram.di import get_container
from app.presentation.telegram.formatters.keyboards import build_main_reply_keyboard, build_spread_keyboard
from app.presentation.telegram.formatters.reading import send_reading_result

logger = logging.getLogger(__name__)

_STATE_KEY = "tarot_state"
_SPREAD_KEY = "spread_type"
_PLATFORM = "telegram"

_GREETING_NEW = "Привет! Добро пожаловать в Arcana Bot."
_GREETING_RETURNING = "Привет! Рад тебя видеть снова."
_START_TEMPLATE = "{greeting}\n\nНапиши свой вопрос для расклада."
_PROMPT_AGAIN = "Если есть ещё вопросы, задавай."
_PROMPT_SPREAD = "Выбери тип расклада кнопками:"
_PROMPT_START_FIRST = "Чтобы начать, нажми /start."
_INJECTION_BLOCKED = (
    "Карты туманны для такого запроса. "
    "Сформулируй вопрос проще и без служебных инструкций."
)
_LIMITS_EXHAUSTED_TEMPLATE = (
    "Закончились ежедневные расклады 🌙\n\n"
    "Новые бесплатные расклады появятся через {time_until}. "
    "Хочешь еще сейчас? Пригласи друга по своей реферальной ссылке "
    "и получи +3 расклада за каждого!\n\n"
    "Твоя ссылка: https://t.me/{bot_username}?start=ref_{tg_id}"
)
_INTERPRETATION_FAILED = (
    "Не удалось получить трактовку прямо сейчас. "
    "Попробуй задать вопрос еще раз чуть позже."
)
_UNKNOWN_COMMAND = "Неизвестная команда. Используй /start."
_SERVICE_UNAVAILABLE = "Сервис временно недоступен. Попробуй позже."
_REFERRAL_NOTIFICATION = (
    "🎉 По твоей ссылке зарегистрировался новый пользователь!\n\n"
    "Тебе начислено +3 дополнительных расклада. "
    "Спасибо, что делишься ботом! "
    "Проверить баланс можно в меню 👤 Профиль."
)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start: register the user and initialise the question flow."""
    tg_user = update.effective_user
    message = update.effective_message
    user_data = context.user_data
    if tg_user is None or message is None or user_data is None:
        return

    display_name = (tg_user.full_name or tg_user.username or str(tg_user.id)).strip()
    referrer_id = _parse_referrer_id(message.text)

    try:
        async with get_container(context)() as di:
            use_case: RegisterUserUseCase = await di.get(RegisterUserUseCase)
            reg = await use_case.execute(
                platform=_PLATFORM,
                external_id=str(tg_user.id),
                display_name=display_name,
                referrer_external_id=referrer_id,
            )
    except Exception:
        logger.exception("start failed tg_id=%s", tg_user.id)
        await message.reply_text(_SERVICE_UNAVAILABLE)
        return

    # Push notification to the referrer — outside the DI scope so a Telegram
    # error here never rolls back or blocks the new user's registration.
    if reg.is_new_user and reg.has_referrer and reg.referrer_external_id:
        try:
            await context.bot.send_message(
                chat_id=int(reg.referrer_external_id),
                text=_REFERRAL_NOTIFICATION,
            )
        except Exception:
            logger.warning(
                "referral push failed referrer_external_id=%s", reg.referrer_external_id
            )

    current_spread = _resolve_spread(user_data)
    user_data[_STATE_KEY] = TarotState.WAITING_FOR_QUESTION
    user_data[_SPREAD_KEY] = current_spread.value

    greeting = _GREETING_NEW if reg.is_new_user else _GREETING_RETURNING
    await message.reply_text(
        _START_TEMPLATE.format(greeting=greeting),
        reply_markup=build_main_reply_keyboard(),
    )
    await message.reply_text(_PROMPT_SPREAD, reply_markup=build_spread_keyboard(current_spread))
    logger.info("start tg_id=%s is_new=%s has_referrer=%s", tg_user.id, reg.is_new_user, reg.has_referrer)


async def question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process the user's question and deliver the tarot reading."""
    message = update.effective_message
    user_data = context.user_data
    if message is None or user_data is None:
        return

    if user_data.get(_STATE_KEY) != TarotState.WAITING_FOR_QUESTION:
        await message.reply_text(_PROMPT_START_FIRST)
        return

    tg_user = update.effective_user
    if tg_user is None or message.text is None:
        return

    question = message.text.strip()
    spread_type = _resolve_spread(user_data)
    display_name = (tg_user.full_name or tg_user.username or str(tg_user.id)).strip()

    cmd = PerformReadingCommand(
        question=question,
        spread_type=spread_type,
        platform=_PLATFORM,
        external_user_id=str(tg_user.id),
        user_display_name=display_name,
    )

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)

    try:
        async with get_container(context)() as di:
            use_case: PerformReadingUseCase = await di.get(PerformReadingUseCase)
            result = await use_case.execute(cmd)
    except InsufficientLimitsError:
        bot_username = context.bot.username or "arcana_r_bot"
        await message.reply_text(
            _LIMITS_EXHAUSTED_TEMPLATE.format(
                time_until=_time_until_midnight_msk(),
                bot_username=bot_username,
                tg_id=tg_user.id,
            )
        )
        return
    except InjectionBlockedError:
        await message.reply_text(_INJECTION_BLOCKED)
        return
    except Exception:
        logger.exception("reading failed tg_id=%s", tg_user.id)
        await message.reply_text(_INTERPRETATION_FAILED)
        return

    await send_reading_result(message, result)

    user_data[_STATE_KEY] = TarotState.WAITING_FOR_QUESTION
    await message.reply_text(
        f"{_PROMPT_AGAIN}\n{_PROMPT_SPREAD}",
        reply_markup=build_spread_keyboard(_resolve_spread(user_data)),
    )


async def spread_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Update the active spread type from the inline keyboard."""
    query = update.callback_query
    user_data = context.user_data
    if query is None or user_data is None:
        return

    await query.answer()
    data = query.data or ""
    if not data.startswith("spread:"):
        return

    raw = data.split(":", 1)[1]
    try:
        spread_type = SpreadType(raw)
    except ValueError:
        await query.answer("Неизвестный тип расклада.", show_alert=True)
        return

    if user_data.get(_SPREAD_KEY) == spread_type.value:
        return  # already selected — Telegram would reject the identical edit

    user_data[_SPREAD_KEY] = spread_type.value
    if query.message is not None:
        await query.edit_message_reply_markup(reply_markup=build_spread_keyboard(spread_type))


async def unknown_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to unrecognised commands."""
    del context
    message = update.effective_message
    if message:
        await message.reply_text(_UNKNOWN_COMMAND)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MSK = ZoneInfo("Europe/Moscow")


def _time_until_midnight_msk() -> str:
    """Return human-readable time remaining until midnight Moscow time.

    Always returns at least "1 мин." so the message never says "0 мин."
    """
    now = datetime.now(_MSK)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    total_minutes = max(1, int((midnight - now).total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    if hours == 0:
        return f"{minutes} мин."
    return f"{hours} ч. {minutes} мин."


def _parse_referrer_id(text: str | None) -> str | None:
    """Extract referrer external_id from a /start deep-link payload.

    Telegram passes deep-link parameters as a single string after the command,
    e.g. ``/start ref_123456789``.  Returns the digit string after ``ref_``,
    or ``None`` when the payload is absent or malformed.
    """
    if not text:
        return None
    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    payload = parts[1]
    if payload.startswith("ref_") and payload[4:].isdigit():
        return payload[4:]
    return None


def _resolve_spread(user_data: dict[str, Any]) -> SpreadType:
    """Return the spread type from user state, defaulting to THREE_CARDS."""
    raw = user_data.get(_SPREAD_KEY, SpreadType.THREE_CARDS.value)
    try:
        return SpreadType(raw)
    except ValueError:
        return SpreadType.THREE_CARDS


def get_start_handlers() -> list[BaseHandler]:
    """Return the ordered handler list for the question flow."""
    return [
        CommandHandler("start", start_handler),
        CallbackQueryHandler(spread_callback_handler, pattern=r"^spread:"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, question_handler),
        MessageHandler(filters.COMMAND, unknown_command_handler),
    ]
