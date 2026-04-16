"""Start command and onboarding handlers."""

import logging

from telegram import Message, Update
from telegram.constants import ChatAction
from telegram.ext import (
    BaseHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot.states import TarotState
from app.core.db import SessionLocal
from app.schemas.tarot import SpreadCard
from app.repositories.reading import ReadingRepository
from app.repositories.user import UserRepository
from app.services.image_service import image_service
from app.services.llm_service import llm_service
from app.services.storage_service import storage_service
from app.services.tarot_service import tarot_service

STATE_KEY = "tarot_state"
logger = logging.getLogger(__name__)
GREETING_NEW_USER = "Привет! Добро пожаловать в Arcana Bot."
GREETING_RETURNING_USER = "Привет! Рад тебя видеть снова."
PROMPT_QUESTION = "Напиши свой вопрос для расклада."
PROMPT_START_FIRST = "Чтобы начать, нажми /start."
PROFILE_MISSING = "Не удалось найти твой профиль. Нажми /start еще раз."
UNKNOWN_COMMAND = "Неизвестная команда. Используй /start."
INTERPRETATION_FAILED = (
    "Не удалось получить трактовку прямо сейчас. Попробуй задать вопрос еще раз чуть позже."
)
TELEGRAM_TEXT_LIMIT = 4000
TELEGRAM_CAPTION_LIMIT = 1024


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register user and ask for question."""
    tg_user = update.effective_user
    message = update.effective_message
    if tg_user is None or message is None:
        return

    async with SessionLocal() as session:
        user_repo = UserRepository(session=session)
        _, created = await user_repo.get_or_create(
            tg_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
        )

    greeting = GREETING_NEW_USER if created else GREETING_RETURNING_USER

    await message.reply_text(greeting)
    await message.reply_text(PROMPT_QUESTION)
    context.user_data[STATE_KEY] = TarotState.WAITING_FOR_QUESTION
    logger.info("Handled /start for tg_id=%s", tg_user.id)


async def question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate spread, ask LLM for interpretation, and persist result."""
    message = update.effective_message
    if message is None:
        return

    if context.user_data.get(STATE_KEY) != TarotState.WAITING_FOR_QUESTION:
        await message.reply_text(PROMPT_START_FIRST)
        return

    tg_user = update.effective_user
    if tg_user is None or message.text is None:
        return

    question = message.text.strip()
    spread = await tarot_service.generate_spread(3)
    spread_prompt = _build_spread_prompt(spread)
    llm_question = f"{question}\n\nКонтекст расклада:\n{spread_prompt}"

    # Show typing while waiting for the LLM response.
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
    try:
        interpretation = await llm_service.get_interpretation(question=llm_question, cards=spread)
    except Exception:
        logger.exception("Failed to generate interpretation for tg_id=%s", tg_user.id)
        await message.reply_text(INTERPRETATION_FAILED)
        return

    layout_payload = {
        "cards": [
            {"id": card.id, "is_reversed": card.is_reversed}
            for card in spread
        ]
    }
    image_path = None
    try:
        image_bytes = image_service.create_spread_image(spread)
        image_path = storage_service.save_bytesio_temp(image_bytes, suffix=".png")
    except Exception:
        logger.exception("Failed to generate spread image for tg_id=%s", tg_user.id)

    async with SessionLocal() as session:
        user_repo = UserRepository(session=session)
        user = await user_repo.get_by_tg_id(tg_user.id)
        if user is None:
            await message.reply_text(PROFILE_MISSING)
            return

        reading_repo = ReadingRepository(session=session)
        await reading_repo.create_reading(
            user_id=user.id,
            question=question,
            layout=layout_payload,
            interpretation=interpretation,
            image_url=str(image_path) if image_path else None,
        )

    context.user_data.pop(STATE_KEY, None)
    cards_line = _format_cards_for_user(spread)
    caption = _build_photo_caption(cards_line, interpretation)
    if image_path is not None:
        with image_path.open("rb") as image_file:
            await message.reply_photo(photo=image_file, caption=caption)
    else:
        await _reply_long_text(message, caption)


async def unknown_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to unknown commands and guide user to /start."""
    del context
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(UNKNOWN_COMMAND)


def _build_spread_prompt(spread: list[SpreadCard]) -> str:
    lines = []
    for card in spread:
        orientation = "перевернутая" if card.is_reversed else "прямая"
        lines.append(f"{card.position}. {card.name} ({orientation})")
    return "\n".join(lines)


def _format_cards_for_user(spread: list[SpreadCard]) -> str:
    parts = []
    for card in spread:
        orientation = "перевернутая" if card.is_reversed else "прямая"
        parts.append(f"{card.name} ({orientation})")
    return ", ".join(parts)


def _build_photo_caption(cards_line: str, interpretation: str) -> str:
    caption = f"Выпавшие карты: {cards_line}\n\n{interpretation}"
    if len(caption) <= TELEGRAM_CAPTION_LIMIT:
        return caption
    trimmed = caption[: TELEGRAM_CAPTION_LIMIT - 3].rstrip()
    return f"{trimmed}..."


async def _reply_long_text(message: Message, text: str) -> None:
    chunks = _split_text(text, TELEGRAM_TEXT_LIMIT)
    for chunk in chunks:
        await message.reply_text(chunk)


def _split_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def get_start_handlers() -> list[BaseHandler]:
    """Build handlers for start/onboarding flow."""
    return [
        CommandHandler("start", start_handler),
        MessageHandler(filters.TEXT & ~filters.COMMAND, question_handler),
        MessageHandler(filters.COMMAND, unknown_command_handler),
    ]
