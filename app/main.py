"""FastAPI application entrypoint — runs Telegram and VK bots simultaneously."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.payments import router as payments_router
from app.api.router import router as api_router
from app.bot.main import TelegramPollingService, build_container, configure_logging
from app.bot.vk_main import VKPollingService
from app.core.config import settings
from app.domain.ports.storage_port import IStoragePort
from app.infrastructure.assets.tarot_data import tarot_data_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup/shutdown lifecycle for both bots."""
    configure_logging()
    settings.output_dir_path.mkdir(parents=True, exist_ok=True)
    tarot_data_service.verify_assets()

    container = build_container()
    app.state.container = container

    storage: IStoragePort = await container.get(IStoragePort)
    await storage.ensure_bucket_exists()
    app.state.storage = storage

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_service = TelegramPollingService(container)
    app.state.telegram_service = telegram_service
    await telegram_service.run_polling()

    # ── VK — only started when token is configured ────────────────────────────
    vk_service: VKPollingService | None = None
    if settings.vk_group_token:
        vk_service = VKPollingService(container, settings)
        app.state.vk_service = vk_service
        await vk_service.run_polling()

    try:
        yield
    finally:
        if vk_service is not None:
            await vk_service.stop_polling()
        # stop_polling() also calls container.close() — must run last.
        await telegram_service.stop_polling()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api_router)
app.include_router(payments_router)
app.mount(
    "/miniapp",
    StaticFiles(directory=str((Path(__file__).resolve().parent / "miniapp").resolve()), html=True),
    name="miniapp",
)
