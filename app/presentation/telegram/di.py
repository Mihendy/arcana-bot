"""DI container accessor for PTB handlers.

The ``AsyncContainer`` is stored in ``application.bot_data`` during startup
so every handler can open a request scope without knowing where the container
lives.
"""

from __future__ import annotations

from dishka import AsyncContainer
from telegram.ext import ContextTypes

_BOT_DATA_KEY = "di_container"


def get_container(context: ContextTypes.DEFAULT_TYPE) -> AsyncContainer:
    """Extract the DI container from PTB bot_data.

    Args:
        context: PTB handler context.

    Returns:
        AsyncContainer: The application-level dishka container.

    Raises:
        KeyError: If the container was not stored during startup.
    """
    return context.bot_data[_BOT_DATA_KEY]  # type: ignore[return-value]


def store_container(bot_data: dict, container: AsyncContainer) -> None:
    """Store container in bot_data during application startup."""
    bot_data[_BOT_DATA_KEY] = container
