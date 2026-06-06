"""VK handler registry — wires all handlers onto the bot labeler."""

from __future__ import annotations

from dishka import AsyncContainer
from vkbottle import API
from vkbottle.bot import BotLabeler

from app.bot.spread_store import VKSessionStore
from app.core.config import Settings
from app.infrastructure.vk.photo_uploader import VKPhotoUploader
from app.presentation.vk.handlers import admin, profile, reading, start


def setup_handlers(
    labeler: BotLabeler,
    container: AsyncContainer,
    api: API,
    settings: Settings,
) -> None:
    """Register all VK handlers."""
    store = VKSessionStore()
    uploader = VKPhotoUploader(api, settings.vk_group_id)

    # Registration must happen BEFORE the catch-all question handler so
    # "start" text is matched first.
    admin.register(labeler, container, api, settings)
    start.register(labeler, container, settings, store)
    profile.register(labeler, container, settings)
    reading.register(labeler, container, settings, store, uploader)
