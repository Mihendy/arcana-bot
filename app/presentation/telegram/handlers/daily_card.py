"""Daily card broadcast logic."""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO

from dishka import AsyncContainer
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.error import Forbidden
from telegram.ext import Application

from app.application.use_cases.get_daily_card import GetDailyCardUseCase
from app.core.config import Settings
from app.domain.entities.user import PlatformIdentity
from app.domain.ports.unit_of_work import IUnitOfWork
from app.domain.ports.user_repo import IUserRepository
from app.presentation.telegram.formatters.daily_card import (
    build_caption,
    build_share_story_url,
)

logger = logging.getLogger(__name__)

# Max concurrent Telegram API calls — respects the ~30 msg/sec bot rate limit
# while keeping memory overhead minimal.
_SEND_CONCURRENCY = 25


class DailyCardBroadcaster:
    """Sends the card-of-the-day to all registered Telegram users.

    One instance is created during bot startup and reused across daily
    broadcast runs. Each run opens a fresh REQUEST scope so it gets a
    fresh DB session.
    """

    def __init__(self, container: AsyncContainer, settings: Settings) -> None:
        self._container = container
        self._settings = settings

    async def broadcast(self, app: Application) -> None:
        """Generate and send the daily card to all active Telegram users.

        Sends are parallelised up to _SEND_CONCURRENCY concurrent requests.
        Users who have blocked the bot are recorded and excluded from all
        future broadcasts automatically.
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
        logger.info(
            "daily_card broadcasting card=%s to %d users",
            result.card_name,
            len(identities),
        )

        semaphore = asyncio.Semaphore(_SEND_CONCURRENCY)
        blocked: list[str] = []

        async def _send_one(identity: PlatformIdentity) -> None:
            share_url = build_share_story_url(
                result, self._settings, tg_id=identity.external_id
            )
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    text="Поделиться в сторис",
                    web_app=WebAppInfo(url=share_url),
                )
            ]])
            if result.image_bytes:
                photo: BytesIO | str = BytesIO(result.image_bytes)
                photo.name = "daily_card.png"  # type: ignore[attr-defined]
            else:
                photo = result.image_url

            async with semaphore:
                try:
                    await app.bot.send_photo(
                        chat_id=identity.external_id,
                        photo=photo,
                        caption=caption,
                        reply_markup=keyboard,
                    )
                except Forbidden:
                    logger.warning(
                        "daily_card: user blocked bot, will be excluded "
                        "from future broadcasts external_id=%s",
                        identity.external_id,
                    )
                    blocked.append(identity.external_id)
                except Exception:
                    logger.exception(
                        "daily_card send failed external_id=%s",
                        identity.external_id,
                    )

        await asyncio.gather(*[_send_one(i) for i in identities])

        if blocked:
            async with self._container() as di:
                user_repo = await di.get(IUserRepository)
                uow: IUnitOfWork = await di.get(IUnitOfWork)
                await user_repo.mark_blocked_many(blocked)
                await uow.commit()
            logger.info("daily_card: marked %d users as blocked", len(blocked))
