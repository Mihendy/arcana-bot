"""Daily card broadcast logic — replaces DailyCardService.

The broadcaster is instantiated once and wired into the
``TelegramPollingService`` loop.  It owns the dishka container reference
so it can open a new REQUEST scope per broadcast run.
"""

from __future__ import annotations

import logging
from io import BytesIO

from dishka import AsyncContainer
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application

from app.application.use_cases.get_daily_card import GetDailyCardUseCase
from app.core.config import Settings
from app.domain.ports.user_repo import IUserRepository
from app.presentation.telegram.formatters.daily_card import build_caption, build_share_story_url

logger = logging.getLogger(__name__)


class DailyCardBroadcaster:
    """Sends the card-of-the-day to all registered Telegram users.

    One instance is created during bot startup and reused across daily
    broadcast runs.  Each run opens a fresh REQUEST scope so it gets a
    fresh DB session.
    """

    def __init__(self, container: AsyncContainer, settings: Settings) -> None:
        self._container = container
        self._settings = settings

    async def broadcast(self, app: Application) -> None:
        """Generate and send the daily card to all Telegram users.

        Args:
            app: Running PTB application, used only for ``app.bot.send_photo``.
        """
        async with self._container() as di:
            use_case: GetDailyCardUseCase = await di.get(GetDailyCardUseCase)
            result = await use_case.execute()

            user_repo: IUserRepository = await di.get(IUserRepository)
            identities = await user_repo.list_platform_identities("telegram")

        if not identities:
            logger.info("daily_card broadcast skipped: no recipients")
            return

        caption = build_caption(result)
        share_url = build_share_story_url(result, self._settings)
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="Поделиться в сторис", web_app=WebAppInfo(url=share_url))]]
        )

        logger.info("daily_card broadcasting card=%s to %d users", result.card_name, len(identities))

        for identity in identities:
            try:
                if result.image_bytes:
                    photo: BytesIO | str = BytesIO(result.image_bytes)
                    photo.name = "daily_card.png"  # type: ignore[attr-defined]
                else:
                    photo = result.image_url
                await app.bot.send_photo(
                    chat_id=identity.external_id,
                    photo=photo,
                    caption=caption,
                    reply_markup=keyboard,
                )
            except Exception:
                logger.exception("daily_card send failed external_id=%s", identity.external_id)
