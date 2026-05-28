"""Python Telegram Bot initialization helpers."""

import asyncio
import logging
import sys
from contextlib import suppress
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dishka import AsyncContainer, make_async_container
from loguru import logger as loguru_logger
from telegram import BotCommand, Update
from telegram.error import TelegramError
from telegram.ext import Application
from telegram.request import HTTPXRequest

from app.core.config import settings
from app.domain.ports.user_repo import IUserRepository
from app.infrastructure.di.providers import InfraProvider, SessionProvider
from app.presentation.telegram.di import store_container
from app.presentation.telegram.handlers.daily_card import DailyCardBroadcaster
from app.presentation.telegram.handlers.router import get_handlers

logger = logging.getLogger(__name__)
DEFAULT_BOT_COMMANDS = [
    BotCommand(command="start", description="Начать работу с ботом"),
    BotCommand(command="admin_stats", description="Админ-метрики"),
]

# File that persists the MSK date of the last successful limits reset.
# Survives bot restarts so we never double-reset within the same calendar day.
_LAST_RESET_FILE: Path = settings.output_dir_path.parent / "last_daily_reset.txt"


class InterceptHandler(logging.Handler):
    """Redirect standard logging records to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        loguru_logger.opt(exception=record.exc_info, depth=6).log(level, record.getMessage())


def configure_logging() -> None:
    """Configure application logging sinks and interception."""
    loguru_logger.remove()
    loguru_logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format="{time:YYYY-MM-DD HH:mm:ss,SSS} | {level} | {name} | {message}",
    )

    intercept_handler = InterceptHandler()
    logging.root.handlers = [intercept_handler]
    logging.root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    for logger_name in ("uvicorn", "uvicorn.error", "telegram"):
        logging.getLogger(logger_name).handlers = [intercept_handler]
        logging.getLogger(logger_name).propagate = False

    # Suppress per-request noise: long-polling getUpdates and HTTP access logs.
    for noisy in ("httpx", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
        logging.getLogger(noisy).handlers = [intercept_handler]
        logging.getLogger(noisy).propagate = False


def build_container() -> AsyncContainer:
    """Create and return the application-level DI container."""
    return make_async_container(InfraProvider(), SessionProvider())


def _create_telegram_app(container: AsyncContainer) -> Application:
    """Build and configure the PTB Application with the DI container wired in."""
    request_kwargs: dict[str, Any] = {
        "connect_timeout": 20.0,
        "read_timeout": 20.0,
        "write_timeout": 20.0,
        "media_write_timeout": 20.0,
    }
    if settings.telegram_proxy:
        request_kwargs["proxy"] = settings.telegram_proxy

    request = HTTPXRequest(**request_kwargs)
    get_updates_request = HTTPXRequest(**request_kwargs)
    app = (
        Application.builder()
        .token(settings.bot_token)
        .request(request)
        .get_updates_request(get_updates_request)
        .post_init(set_bot_commands)
        .build()
    )
    store_container(app.bot_data, container)
    for handler in get_handlers():
        app.add_handler(handler)
    return app


async def set_bot_commands(application: Application) -> None:
    """Register default command list in Telegram client menu."""
    await application.bot.set_my_commands(DEFAULT_BOT_COMMANDS)


def _read_last_reset_date() -> date | None:
    """Return the date written by the last successful reset, or None."""
    try:
        return date.fromisoformat(_LAST_RESET_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def _write_last_reset_date(d: date) -> None:
    """Persist today's reset date so restarts don't double-reset."""
    _LAST_RESET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LAST_RESET_FILE.write_text(d.isoformat())


class TelegramPollingService:
    """Encapsulates telegram polling startup/shutdown lifecycle."""

    def __init__(self, container: AsyncContainer) -> None:
        self._container = container
        self._broadcaster = DailyCardBroadcaster(container, settings)
        self.app = _create_telegram_app(container)
        self.app.add_error_handler(self._on_handler_error)
        self._daily_card_task: asyncio.Task[None] | None = None
        self._reset_limits_task: asyncio.Task[None] | None = None

    async def _on_handler_error(self, update: object | None, context: Any) -> None:
        logger.exception("Telegram handler error. update=%s", update, exc_info=context.error)

    def _on_polling_error(self, error: TelegramError) -> None:
        logger.exception("Telegram polling error: %s", error, exc_info=error)

    async def run_polling(self) -> None:
        """Initialize telegram app and start polling updates."""
        await self.app.initialize()
        if self.app.updater is None:
            raise RuntimeError("Telegram updater is not initialized.")
        await self.app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            error_callback=self._on_polling_error,
        )
        await self.app.start()
        self._start_daily_card_schedule()
        self._start_reset_limits_schedule()
        logger.info("Bot started in polling mode")

    async def stop_polling(self) -> None:
        """Stop polling loop, shutdown the PTB app, and close the DI container."""
        await self._stop_daily_card_schedule()
        await self._stop_reset_limits_schedule()
        if self.app.updater is not None:
            await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        await self._container.close()  # disposes AsyncEngine + all APP-scoped resources
        logger.info("Bot stopped")

    # ── Daily card ────────────────────────────────────────────────────────────

    def _start_daily_card_schedule(self) -> None:
        if self._daily_card_task is not None and not self._daily_card_task.done():
            return
        self._daily_card_task = asyncio.create_task(self._daily_card_loop())

    async def _stop_daily_card_schedule(self) -> None:
        if self._daily_card_task is None:
            return
        self._daily_card_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._daily_card_task
        self._daily_card_task = None

    async def _daily_card_loop(self) -> None:
        """Run daily card delivery loop at configured Moscow time."""
        tz = ZoneInfo(settings.daily_card_timezone)
        target_hour = min(max(settings.daily_card_hour_msk, 0), 23)
        while True:
            delay = self._seconds_until_next_run(tz=tz, target_hour=target_hour)
            await asyncio.sleep(delay)
            try:
                await self._broadcaster.broadcast(self.app)
            except Exception:
                logger.exception("Failed to send daily card broadcast.")

    # ── Daily limits reset ────────────────────────────────────────────────────

    def _start_reset_limits_schedule(self) -> None:
        if self._reset_limits_task is not None and not self._reset_limits_task.done():
            return
        self._reset_limits_task = asyncio.create_task(self._reset_limits_loop())

    async def _stop_reset_limits_schedule(self) -> None:
        if self._reset_limits_task is None:
            return
        self._reset_limits_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._reset_limits_task
        self._reset_limits_task = None

    async def _reset_limits_loop(self) -> None:
        """Reset daily_limit = 3 for all users at midnight MSK.

        Startup protection: on first run, checks whether today's reset was
        already persisted to disk. If not — runs immediately so a bot restart
        around midnight never leaves users with 0 slots.
        """
        tz = ZoneInfo(settings.daily_card_timezone)

        # Startup check: run immediately if today's reset hasn't happened yet.
        today = datetime.now(tz).date()
        if _read_last_reset_date() != today:
            await self._run_limits_reset(tz)

        while True:
            # Sleep until the next midnight MSK (hour=0).
            delay = self._seconds_until_next_run(tz=tz, target_hour=0)
            await asyncio.sleep(delay)
            await self._run_limits_reset(tz)

    async def _run_limits_reset(self, tz: ZoneInfo) -> None:
        try:
            async with self._container() as di:
                user_repo: IUserRepository = await di.get(IUserRepository)
                count = await user_repo.reset_daily_limits()
            today = datetime.now(tz).date()
            _write_last_reset_date(today)
            logger.info("daily_limits reset: %d rows updated", count)
        except Exception:
            logger.exception("Failed to reset daily limits")

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _seconds_until_next_run(self, tz: ZoneInfo, target_hour: int) -> float:
        now = datetime.now(tz)
        run_at = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
        if run_at <= now:
            run_at = run_at + timedelta(days=1)
        return max((run_at - now).total_seconds(), 1.0)
