"""Prompt-safety middleware utilities for bot handlers."""

from app.bot.middlewares.prompt_guard import find_injection_phrase

__all__ = ["find_injection_phrase"]
