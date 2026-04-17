"""FastAPI application entrypoint with polling telegram lifecycle."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.router import router as api_router
from app.bot.main import TelegramPollingService, configure_logging
from app.core.config import settings
from app.services.tarot_data import tarot_data_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup/shutdown lifecycle.

    Args:
        app: FastAPI application instance.

    Yields:
        None: Control is yielded to FastAPI runtime while app is running.

    Raises:
        FileNotFoundError: If tarot card assets are missing.
        RuntimeError: If Telegram polling service fails to start.
    """
    configure_logging()
    settings.output_dir_path.mkdir(parents=True, exist_ok=True)
    tarot_data_service.verify_assets()
    telegram_service = TelegramPollingService()
    app.state.telegram_service = telegram_service
    await telegram_service.run_polling()

    try:
        yield
    finally:
        await telegram_service.stop_polling()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api_router)
