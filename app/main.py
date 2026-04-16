"""FastAPI application entrypoint with aiogram lifecycle."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator

from aiogram.types import Update
from fastapi import FastAPI, HTTPException, Request, status

from app.api.router import router as api_router
from app.bot.main import (
    BOT_MODE_POLLING,
    BOT_MODE_WEBHOOK,
    configure_logging,
    create_bot,
    create_dispatcher,
    remove_webhook,
    setup_webhook,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage bot startup and shutdown according to selected mode."""
    configure_logging()

    bot = create_bot()
    dispatcher = create_dispatcher()
    app.state.bot = bot
    app.state.dispatcher = dispatcher
    app.state.polling_task = None

    if settings.bot_mode == BOT_MODE_POLLING:
        app.state.polling_task = asyncio.create_task(
            dispatcher.start_polling(
                bot,
                allowed_updates=dispatcher.resolve_used_update_types(),
            )
        )
        logger.info("Bot started in polling mode")
    elif settings.bot_mode == BOT_MODE_WEBHOOK:
        await setup_webhook(bot)
        logger.info("Bot started in webhook mode")
    else:
        raise RuntimeError(f"Unsupported bot mode: {settings.bot_mode}")

    try:
        yield
    finally:
        polling_task = app.state.polling_task
        if polling_task is not None:
            polling_task.cancel()
            with suppress(asyncio.CancelledError):
                await polling_task

        if settings.bot_mode == BOT_MODE_WEBHOOK:
            await remove_webhook(bot)

        await bot.session.close()
        logger.info("Bot stopped")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api_router)


@app.post(settings.webhook_path, include_in_schema=False)
async def telegram_webhook(request: Request) -> dict[str, str]:
    """Receive Telegram updates in webhook mode."""
    if settings.bot_mode != BOT_MODE_WEBHOOK:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint is available only in webhook mode.",
        )

    if settings.webhook_secret_token:
        provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if provided_secret != settings.webhook_secret_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook secret token.",
            )

    payload = await request.json()
    update = Update.model_validate(payload)
    await request.app.state.dispatcher.feed_update(request.app.state.bot, update)

    return {"ok": "true"}
