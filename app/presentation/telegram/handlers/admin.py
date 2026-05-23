"""Thin admin stats handler."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from app.application.use_cases.get_admin_stats import GetAdminStatsUseCase
from app.core.config import settings
from app.presentation.telegram.di import get_container

logger = logging.getLogger(__name__)

_ACCESS_DENIED = "Команда доступна только администратору."


async def admin_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return platform analytics to the authorised admin user.

    Guards by ``settings.admin_tg_id`` — all other callers receive an
    access-denied reply without touching the DB.
    """
    message = update.effective_message
    tg_user = update.effective_user
    if message is None or tg_user is None:
        return

    if tg_user.id != settings.admin_tg_id:
        await message.reply_text(_ACCESS_DENIED)
        return

    try:
        async with get_container(context)() as di:
            use_case: GetAdminStatsUseCase = await di.get(GetAdminStatsUseCase)
            stats = await use_case.execute()
    except Exception:
        logger.exception("admin_stats failed tg_id=%s", tg_user.id)
        await message.reply_text("Не удалось получить статистику. Попробуй позже.")
        return

    await message.reply_text(
        "Admin stats\n"
        f"Users total: {stats.total_users}\n"
        f"Readings today: {stats.readings_today}\n"
        f"Readings this month: {stats.readings_this_month}\n"
        f"LLM successful calls: {stats.llm_success_calls}\n"
        f"LLM total tokens: {stats.llm_total_tokens}"
    )


def get_admin_handlers() -> list:
    """Return the handler list for admin commands."""
    return [CommandHandler("admin_stats", admin_stats_handler)]
