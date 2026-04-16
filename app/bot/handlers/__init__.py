"""Bot handlers package."""

from telegram.ext import BaseHandler

from app.bot.handlers.start import get_start_handlers


def get_handlers() -> list[BaseHandler]:
    """Return all telegram handlers."""
    return get_start_handlers()


__all__ = ["get_handlers"]
