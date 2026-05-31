"""VK handler registry — wires all handlers onto the bot labeler."""

from __future__ import annotations

from dishka import AsyncContainer
from vkbottle import API
from vkbottle.bot import BotLabeler

from app.core.config import Settings
from app.infrastructure.vk.photo_uploader import VKPhotoUploader
from app.presentation.vk.handlers import profile, reading, start


def setup_handlers(
    labeler: BotLabeler,
    container: AsyncContainer,
    api: API,
    settings: Settings,
) -> None:
    """Register all VK handlers.

    ``spread_store`` is a shared in-memory dict that persists the selected
    spread type per user between the spread-selection callback and the
    subsequent question message.  It lives for the duration of the process.
    """
    spread_store: dict[int, str] = {}
    uploader = VKPhotoUploader(api, settings.vk_group_id)

    # Registration must happen BEFORE the catch-all question handler so
    # "start" text is matched first.
    start.register(labeler, container, settings, spread_store)
    profile.register(labeler, container, settings)
    reading.register(labeler, container, settings, spread_store, uploader)
