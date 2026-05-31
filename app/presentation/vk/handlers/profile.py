"""VK profile handler."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from dishka import AsyncContainer
from vkbottle.bot import BotLabeler, Message

from app.application.dto.profile import UserProfileDTO
from app.application.use_cases.get_user_profile import GetUserProfileUseCase
from app.core.config import Settings
from app.presentation.vk.formatters.keyboards import PROFILE_BUTTON_TEXT

logger = logging.getLogger(__name__)

_PLATFORM = "vk"
_PROFILE_ERROR = "Не удалось загрузить профиль. Попробуй позже."


def _subscription_line(profile: UserProfileDTO) -> str:
    now = datetime.now(tz=timezone.utc)
    if profile.premium_expires_at and profile.premium_expires_at > now:
        until = profile.premium_expires_at.strftime("%d.%m.%Y")
        return f"💎 Подписка: Премиум (до {until})"
    return "📦 Подписка: Базовый"


def _build_profile_text(user_id: int, settings: Settings, profile: UserProfileDTO) -> str:
    ref_url = f"{settings.vk_public_url}?ref=ref_{user_id}"
    return (
        "👤 Ваш профиль\n\n"
        f"🆔 Ваш VK ID: {user_id}\n"
        f"{_subscription_line(profile)}\n"
        f"🌙 Ежедневные расклады: {profile.daily_limit} из 3 осталось\n"
        f"🎁 Бонусные расклады: {profile.bonus_balance}\n\n"
        f"👥 Приглашено друзей: {profile.referrals_count} чел.\n\n"
        f"🔗 Ваша реферальная ссылка: {ref_url}"
    )


def register(
    labeler: BotLabeler,
    container: AsyncContainer,
    settings: Settings,
) -> None:
    """Register profile handler on *labeler*."""

    @labeler.message(text=["профиль", "/profile", PROFILE_BUTTON_TEXT])
    async def handle_profile(message: Message) -> None:
        user_id = message.from_id

        try:
            async with container() as di:
                use_case: GetUserProfileUseCase = await di.get(GetUserProfileUseCase)
                profile = await use_case.execute(
                    platform=_PLATFORM,
                    external_id=str(user_id),
                )
        except Exception:
            logger.exception("vk profile failed user_id=%s", user_id)
            await message.answer(_PROFILE_ERROR)
            return

        await message.answer(
            _build_profile_text(user_id, settings, profile),
            dont_parse_links=True,
        )
