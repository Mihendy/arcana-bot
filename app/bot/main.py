"""Python Telegram Bot initialization helpers."""

import logging
import sys
from typing import Any

from loguru import logger as loguru_logger
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
    BotCommand(command="admin_stats", description="Админ-метрики"),
]


class InterceptHandler(logging.Handler):
    """Redirect standard logging records to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Forward standard ``logging`` records to Loguru.

        Args:
            record: Python logging record.
        """
        try:
            level: str | int = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        loguru_logger.opt(exception=record.exc_info, depth=6).log(level, record.getMessage())


def configure_logging() -> None:
    """Configure application logging sinks and interception.

    Returns:
        None: This function configures global logging state in-place.
    """
    settings.logs_dir_path.mkdir(parents=True, exist_ok=True)
    loguru_logger.remove()
    loguru_logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format="{time:YYYY-MM-DD HH:mm:ss,SSS} | {level} | {name} | {message}",
    )
    loguru_logger.add(
        settings.logs_dir_path / "bot.log",
        level=settings.log_level.upper(),
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss,SSS} | {level} | {name} | {message}",
    )

    intercept_handler = InterceptHandler()
    logging.root.handlers = [intercept_handler]
    logging.root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "telegram", "httpx"):
        logging.getLogger(logger_name).handlers = [intercept_handler]
        logging.getLogger(logger_name).propagate = False


def _create_telegram_app() -> Application:
    """Build Telegram ``Application`` instance for polling mode.

    Returns:
        Application: Configured telegram application with handlers.
    """
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
    for handler in get_handlers():
        app.add_handler(handler)
    return app


async def set_bot_commands(application: Application) -> None:
    """Register default command list in Telegram client menu.

    Args:
        application: Initialized Telegram application instance.
    """
    await application.bot.set_my_commands(DEFAULT_BOT_COMMANDS)


class TelegramPollingService:
    """Encapsulates telegram polling startup/shutdown lifecycle."""

    def __init__(self) -> None:
        """Create polling service with error handlers pre-registered."""
        self.app = _create_telegram_app()
        self.app.add_error_handler(self._on_handler_error)

    async def _on_handler_error(
        self,
        update: object | None,
        context: Any,
    ) -> None:
        """Log unhandled exceptions raised by telegram handlers.

        Args:
            update: Telegram update that caused the failure.
            context: PTB callback context containing the error object.
        """
        logger.exception("Telegram handler error. update=%s", update, exc_info=context.error)

    def _on_polling_error(self, error: TelegramError) -> None:
        """Log polling-level transport errors.

        Args:
            error: Telegram polling exception object.
        """
        logger.exception("Telegram polling error: %s", error, exc_info=error)

    async def run_polling(self) -> None:
        """Initialize telegram app and start polling updates.

        Raises:
            RuntimeError: If internal PTB updater is unavailable.
        """
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
        """Stop polling loop and gracefully shutdown telegram app."""
        if self.app.updater is not None:
            await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        logger.info("Bot stopped")
