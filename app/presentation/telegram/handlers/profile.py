"""Profile handler — /profile command and "👤 Профиль" reply-button."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, Update
from telegram.ext import BaseHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.application.dto.profile import UserProfileDTO
from app.application.use_cases.get_user_profile import GetUserProfileUseCase
from app.presentation.telegram.di import get_container
from app.presentation.telegram.formatters.keyboards import PROFILE_BUTTON_TEXT

logger = logging.getLogger(__name__)

_PLATFORM = "telegram"
_PROFILE_ERROR = "Не удалось загрузить профиль. Попробуй позже."


def _subscription_line(profile: UserProfileDTO) -> str:
    now = datetime.now(tz=timezone.utc)
    if profile.premium_expires_at and profile.premium_expires_at > now:
        until = profile.premium_expires_at.strftime("%d.%m.%Y")
        return f"💎 Подписка: Премиум (до {until})"
    return "📦 Подписка: Базовый"


def _payment_section_header(profile: UserProfileDTO) -> str:
    now = datetime.now(tz=timezone.utc)
    if profile.premium_expires_at and profile.premium_expires_at > now:
        return "🔄 Продлить подписку «Премиум»"
    return "🌟 Оформить подписку «Премиум»"


def _build_profile_text(tg_id: int, bot_username: str, profile: UserProfileDTO) -> str:
    return (
        "👤 Ваш профиль\n\n"
        f"🆔 Ваш Telegram ID: {tg_id}\n"
        f"{_subscription_line(profile)}\n"
        f"🌙 Ежедневные расклады: {profile.daily_limit} из 3 осталось\n"
        f"🎁 Бонусные расклады: {profile.bonus_balance}\n\n"
        f"👥 Приглашено друзей: {profile.referrals_count} чел.\n\n"
        f"🔗 Ваша реферальная ссылка: https://t.me/{bot_username}?start=ref_{tg_id}\n\n"
        "──────────────────\n"
        f"{_payment_section_header(profile)}\n"
        "Подписка полностью отключает лимиты — делайте бесконечное количество раскладов целых 30 дней!\n\n"
        "Выберите удобный способ оплаты ниже:"
    )


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user's current limits, bonus balance, and referral link."""
    tg_user = update.effective_user
    message = update.effective_message
    if tg_user is None or message is None:
        return

    try:
        async with get_container(context)() as di:
            use_case: GetUserProfileUseCase = await di.get(GetUserProfileUseCase)
            profile = await use_case.execute(
                platform=_PLATFORM,
                external_id=str(tg_user.id),
            )
    except Exception:
        logger.exception("profile failed tg_id=%s", tg_user.id)
        await message.reply_text(_PROFILE_ERROR)
        return

    bot_username = context.bot.username or "arcana_r_bot"
    await message.reply_text(
        _build_profile_text(tg_user.id, bot_username, profile),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"⭐️ Telegram Stars ({profile.premium_price_stars} 🌟)",
                    callback_data="buy:tg_stars",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"💳 Картой ({profile.premium_price_rub} ₽)",
                    callback_data="buy:yookassa",
                ),
            ],
        ]),
    )


def get_profile_handlers() -> list[BaseHandler]:
    """Return handlers for /profile and the reply-keyboard button."""
    return [
        CommandHandler("profile", profile_handler),
        MessageHandler(filters.Regex(f"^{PROFILE_BUTTON_TEXT}$"), profile_handler),
    ]
