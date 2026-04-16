"""Aiogram bot initialization and lifecycle helpers."""

import logging
from typing import Literal

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.core.config import settings

BOT_MODE_POLLING: Literal["polling"] = "polling"
BOT_MODE_WEBHOOK: Literal["webhook"] = "webhook"

bot_router = Router(name="base")
logger = logging.getLogger(__name__)


@bot_router.message(CommandStart())
async def start_handler(message: Message) -> None:
    """Basic /start command handler."""
    await message.answer("Bot is running.")


def configure_logging() -> None:
    """Configure project-wide default logging."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def create_bot() -> Bot:
    """Create aiogram Bot instance."""
    return Bot(token=settings.bot_token)


def create_dispatcher() -> Dispatcher:
    """Create Dispatcher and attach base routers."""
    dispatcher = Dispatcher()
    dispatcher.include_router(bot_router)
    return dispatcher


async def setup_webhook(bot: Bot) -> None:
    """Register webhook in Telegram for production mode."""
    await bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.webhook_secret_token or None,
        drop_pending_updates=True,
    )
    logger.info("Webhook configured: %s", settings.webhook_url)


async def remove_webhook(bot: Bot) -> None:
    """Remove webhook in Telegram."""
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Webhook removed")
