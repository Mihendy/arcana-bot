"""VK Bot polling service — mirrors TelegramPollingService structure."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dishka import AsyncContainer
from vkbottle import API, Bot

from app.core.config import Settings
from app.presentation.vk.handlers.daily_card import VKDailyCardBroadcaster
from app.presentation.vk.handlers.router import setup_handlers

logger = logging.getLogger(__name__)


class VKPollingService:
    """Encapsulates VK Long Poll startup/shutdown lifecycle.

    Mirrors TelegramPollingService so both services are managed identically
    in the FastAPI lifespan.  Both share the same DI container — each
    incoming event opens a fresh REQUEST scope independently.
    """

    def __init__(self, container: AsyncContainer, settings: Settings) -> None:
        self._container = container
        self._settings = settings
        self._api = API(token=settings.vk_group_token)
        self._bot = Bot(token=settings.vk_group_token)
        self._broadcaster = VKDailyCardBroadcaster(container, self._api, settings)
        self._daily_card_task: asyncio.Task[None] | None = None
        self._polling_task: asyncio.Task[None] | None = None

        setup_handlers(self._bot.labeler, container, self._api, settings)

    async def run_polling(self) -> None:
        """Start VK Long Poll in a background asyncio task."""
        self._polling_task = asyncio.create_task(self._polling_loop())
        self._daily_card_task = asyncio.create_task(self._daily_card_loop())
        logger.info("VK bot started in polling mode")

    async def stop_polling(self) -> None:
        """Cancel all background tasks."""
        for task in (self._polling_task, self._daily_card_task):
            if task is not None and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        logger.info("VK bot stopped")

    async def _polling_loop(self) -> None:
        """Run vkbottle Long Poll indefinitely inside the existing event loop.

        Uses exponential backoff on consecutive failures (5s → 10s → … → 5m).
        pending is kept outside the retry loop so in-flight tasks survive a
        transient polling crash and can still be cancelled on shutdown.
        """
        retry_delay = 5
        max_retry_delay = 300
        pending: set[asyncio.Task] = set()
        while True:
            try:
                async for event in self._bot.polling.listen():
                    for update in event.get("updates", []):
                        task = asyncio.create_task(
                            self._bot.router.route(update, self._bot.polling.api)
                        )
                        pending.add(task)
                        task.add_done_callback(pending.discard)
                retry_delay = 5
            except asyncio.CancelledError:
                for t in pending:
                    t.cancel()
                raise
            except Exception:
                logger.exception("VK polling crashed, restarting in %ds", retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

    # ── Daily card ────────────────────────────────────────────────────────────

    async def _daily_card_loop(self) -> None:
        """Run daily card delivery at configured Moscow time."""
        tz = ZoneInfo(self._settings.daily_card_timezone)
        target_hour = min(max(self._settings.daily_card_hour_msk, 0), 23)
        while True:
            delay = self._seconds_until_next_run(tz=tz, target_hour=target_hour)
            await asyncio.sleep(delay)
            try:
                await self._broadcaster.broadcast()
            except Exception:
                logger.exception("VK daily card broadcast failed")

    def _seconds_until_next_run(self, tz: ZoneInfo, target_hour: int) -> float:
        now = datetime.now(tz)
        run_at = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
        if run_at <= now:
            run_at += timedelta(days=1)
        return max((run_at - now).total_seconds(), 1.0)
