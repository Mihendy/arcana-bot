"""Python Telegram Bot initialization helpers."""

import logging

from telegram import BotCommand
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application
from telegram.request import HTTPXRequest

from app.bot.handlers import get_handlers
from app.core.config import settings

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT_SECONDS = 20.0
DEFAULT_BOT_COMMANDS = [
    BotCommand(command="start", description="Начать работу с ботом"),
]


def configure_logging() -> None:
    """Configure project-wide default logging."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _create_telegram_app() -> Application:
    """Create telegram application with polling handlers."""
    request_kwargs: dict[str, object] = {
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
    for handler in get_handlers():
        app.add_handler(handler)
    return app


async def set_bot_commands(application: Application) -> None:
    """Register bot command menu entries after startup."""
    await application.bot.set_my_commands(DEFAULT_BOT_COMMANDS)


class TelegramPollingService:
    """Encapsulates telegram polling startup/shutdown lifecycle."""

    def __init__(self) -> None:
        self.app = _create_telegram_app()
        self.app.add_error_handler(self._on_handler_error)

    async def _on_handler_error(
        self,
        update: object | None,
        context,
    ) -> None:
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
        logger.info("Bot started in polling mode")

    async def stop_polling(self) -> None:
        """Stop polling and shutdown telegram app."""
        if self.app.updater is not None:
            await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        logger.info("Bot stopped")
