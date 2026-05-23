"""FastAPI application entrypoint with polling telegram lifecycle."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.payments import router as payments_router
from app.api.router import router as api_router
from app.bot.main import TelegramPollingService, build_container, configure_logging
from app.core.config import settings
from app.domain.ports.storage_port import IStoragePort
from app.services.tarot_data import tarot_data_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup/shutdown lifecycle."""
    configure_logging()
    settings.output_dir_path.mkdir(parents=True, exist_ok=True)
    tarot_data_service.verify_assets()

    container = build_container()
    app.state.container = container

    # Resolve the S3 adapter (APP-scoped singleton) and warm up the bucket.
    # The same instance is stored in app.state for the media-proxy endpoint.
    storage: IStoragePort = await container.get(IStoragePort)
    await storage.ensure_bucket_exists()
    app.state.storage = storage

    telegram_service = TelegramPollingService(container)
    app.state.telegram_service = telegram_service
    await telegram_service.run_polling()

    try:
        yield
    finally:
        # stop_polling() also calls container.close() which disposes the engine.
        await telegram_service.stop_polling()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api_router)
app.include_router(payments_router)
app.mount(
    "/miniapp",
    StaticFiles(directory=str((Path(__file__).resolve().parent / "miniapp").resolve()), html=True),
    name="miniapp",
)
