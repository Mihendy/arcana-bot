"""Start command and onboarding handlers."""

import logging
import re
from pathlib import Path
from typing import Any, cast

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message, Update
from telegram.constants import ChatAction
from telegram.ext import (
    BaseHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot.states import TarotState
from app.bot.middlewares import find_injection_phrase
from app.core.config import settings
from app.core.db import SessionLocal
from app.repositories.llm_usage import LLMUsageRepository
from app.schemas.tarot import SpreadCard, SpreadResult, SpreadType
from app.repositories.reading import ReadingRepository
from app.repositories.user import UserRepository
from app.services.analytics_service import analytics_service
from app.services.image_service import image_service
from app.services.llm_service import llm_service
from app.services.storage_service import storage_service
from app.services.tarot_service import tarot_service

STATE_KEY = "tarot_state"
SPREAD_TYPE_KEY = "spread_type"
logger = logging.getLogger(__name__)
GREETING_NEW_USER = "Привет! Добро пожаловать в Arcana Bot."
GREETING_RETURNING_USER = "Привет! Рад тебя видеть снова."
PROMPT_QUESTION = "Напиши свой вопрос для расклада."
PROMPT_QUESTION_AGAIN = "Если есть ещё вопросы, задавай."
PROMPT_SPREAD_CHOOSE = "Выбери тип расклада кнопками:"
START_MESSAGE_TEMPLATE = "{greeting}\n\nНапиши свой вопрос для расклада."
PROMPT_START_FIRST = "Чтобы начать, нажми /start."
PROFILE_MISSING = "Не удалось найти твой профиль. Нажми /start еще раз."
UNKNOWN_COMMAND = "Неизвестная команда. Используй /start."
ACCESS_DENIED = "Команда доступна только администратору."
INTERPRETATION_FAILED = (
    "Не удалось получить трактовку прямо сейчас. Попробуй задать вопрос еще раз чуть позже."
)
INJECTION_BLOCKED = "Карты туманны для такого запроса. Сформулируй вопрос проще и без служебных инструкций."
TELEGRAM_TEXT_LIMIT = 4000
TELEGRAM_CAPTION_LIMIT = 1024
DEFAULT_SPREAD_TYPE: SpreadType = "3_cards"
SUPPORTED_SPREAD_TYPES: set[SpreadType] = {"1_card", "3_cards", "5_cards_line", "pentagram"}
SPREAD_LABELS: dict[SpreadType, str] = {
    "1_card": "1 карта",
    "3_cards": "3 карты",
    "5_cards_line": "5 карт",
    "pentagram": "Пентаграмма",
}


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``/start`` command and initialize question flow state.

    Args:
        update: Incoming Telegram update.
        context: PTB callback context with per-user storage.
    """
    tg_user = update.effective_user
    message = update.effective_message
    user_data = context.user_data
    if tg_user is None or message is None or user_data is None:
        return

    async with SessionLocal() as session:
        user_repo = UserRepository(session=session)
        _, created = await user_repo.get_or_create(
            tg_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
        )

    greeting = GREETING_NEW_USER if created else GREETING_RETURNING_USER
    current_spread_type = _resolve_spread_type(user_data)

    user_data[STATE_KEY] = TarotState.WAITING_FOR_QUESTION
    user_data[SPREAD_TYPE_KEY] = current_spread_type
    await message.reply_text(
        START_MESSAGE_TEMPLATE.format(greeting=greeting),
        reply_markup=_build_spread_keyboard(current_spread_type),
    )
    logger.info("Handled /start for tg_id=%s", tg_user.id)


async def question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process user question and deliver tarot reading.

    Args:
        update: Incoming Telegram update with user message.
        context: PTB callback context with bot and user-scoped state.
    """
    message = update.effective_message
    user_data = context.user_data
    if message is None or user_data is None:
        return

    if user_data.get(STATE_KEY) != TarotState.WAITING_FOR_QUESTION:
        await message.reply_text(PROMPT_START_FIRST)
        return

    tg_user = update.effective_user
    if tg_user is None or message.text is None:
        return

    question = message.text.strip()
    blocked_phrase = find_injection_phrase(question)
    if blocked_phrase is not None:
        logger.warning("Prompt injection blocked for tg_id=%s phrase=%s", tg_user.id, blocked_phrase)
        await message.reply_text(INJECTION_BLOCKED)
        return

    spread_type = _resolve_spread_type(user_data)
    spread_result = await tarot_service.generate_spread(spread_type=spread_type)
    spread_prompt = _build_spread_prompt(spread_result.cards)
    llm_question = f"{question}\n\nКонтекст расклада:\n{spread_prompt}"

    # Show typing while waiting for the LLM response.
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
    try:
        llm_result = await llm_service.get_interpretation(
            question=llm_question,
            cards=spread_result.cards,
            user_tg_id=tg_user.id,
            spread_type=spread_result.spread_type,
            spread_metadata=spread_result.metadata,
        )
        interpretation = llm_result.interpretation
    except Exception as exc:
        await _record_llm_usage_event(user_tg_id=tg_user.id, status=_map_llm_error_to_status(exc))
        logger.exception("Failed to generate interpretation for tg_id=%s", tg_user.id)
        await message.reply_text(INTERPRETATION_FAILED)
        return
    else:
        await _record_llm_usage_event(
            user_tg_id=tg_user.id,
            status=llm_result.status,
            total_tokens=llm_result.total_tokens,
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
        )

    layout_payload = _build_layout_payload(spread_result)
    image_paths: list[Path] = []
    try:
        if spread_result.spread_type == "pentagram":
            image_bytes = image_service.create_pentagram_image(spread_result.cards)
            image_paths = [storage_service.save_bytesio_temp(image_bytes, suffix=".png")]
        else:
            image_bytes = image_service.create_spread_image(spread_result.cards)
            image_paths = [storage_service.save_bytesio_temp(image_bytes, suffix=".png")]
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
            spread_type=spread_result.spread_type,
            layout=layout_payload,
            interpretation=interpretation,
            image_url=str(image_paths[0]) if image_paths else None,
            image_urls=[str(path) for path in image_paths] if image_paths else None,
        )

    cards_line = _format_cards_for_user(spread_result.cards)
    result_text = _build_result_text(cards_line, interpretation)
    if image_paths:
        await _send_result_images(
            message=message,
            image_paths=image_paths,
            result_text=result_text,
        )
    else:
        await _reply_long_text(message, result_text)
    user_data[STATE_KEY] = TarotState.WAITING_FOR_QUESTION
    await message.reply_text(
        f"{PROMPT_QUESTION_AGAIN}\n{PROMPT_SPREAD_CHOOSE}",
        reply_markup=_build_spread_keyboard(_resolve_spread_type(user_data)),
    )


async def spread_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle spread type selection from inline keyboard.

    Args:
        update: Incoming Telegram update.
        context: PTB callback context.
    """
    query = update.callback_query
    user_data = context.user_data
    if query is None or user_data is None:
        return

    await query.answer()
    callback_data = query.data or ""
    if not callback_data.startswith("spread:"):
        return

    candidate = callback_data.split(":", 1)[1]
    if candidate not in SUPPORTED_SPREAD_TYPES:
        await query.answer("Неизвестный тип расклада.", show_alert=True)
        return

    spread_type = cast(SpreadType, candidate)
    user_data[SPREAD_TYPE_KEY] = spread_type
    if query.message is not None:
        await query.edit_message_reply_markup(
            reply_markup=_build_spread_keyboard(spread_type),
        )


async def unknown_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to unknown commands and guide user to ``/start``.

    Args:
        update: Incoming Telegram update.
        context: PTB callback context.
    """
    del context
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(UNKNOWN_COMMAND)


async def admin_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return admin analytics metrics for authorized user only.

    Args:
        update: Incoming Telegram update.
        context: PTB callback context.
    """
    del context
    message = update.effective_message
    tg_user = update.effective_user
    if message is None or tg_user is None:
        return

    if tg_user.id != settings.admin_tg_id:
        await message.reply_text(ACCESS_DENIED)
        return

    total_users = await analytics_service.get_total_users()
    readings_day = await analytics_service.get_readings_count(period="day")
    readings_month = await analytics_service.get_readings_count(period="month")
    llm_stats = await analytics_service.get_llm_usage_stats()

    await message.reply_text(
        "Admin stats\n"
        f"Users total: {total_users}\n"
        f"Readings today: {readings_day}\n"
        f"Readings this month: {readings_month}\n"
        f"LLM successful calls: {llm_stats['success_calls']}\n"
        f"LLM total tokens: {llm_stats['total_tokens']}"
    )


def _build_spread_prompt(spread: list[SpreadCard]) -> str:
    """Build compact spread text block for LLM prompt.

    Args:
        spread: Generated spread cards.

    Returns:
        str: Multiline string with card positions and orientations.
    """
    lines = []
    for card in spread:
        orientation = "перевернутая" if card.is_reversed else "прямая"
        if card.position_name:
            lines.append(f"{card.position}. {card.position_name}: {card.name} ({orientation})")
        else:
            lines.append(f"{card.position}. {card.name} ({orientation})")
    return "\n".join(lines)


def _format_cards_for_user(spread: list[SpreadCard]) -> str:
    """Format spread cards into one user-facing line.

    Args:
        spread: Generated spread cards.

    Returns:
        str: Comma-separated card names and orientations.
    """
    parts = []
    for card in spread:
        orientation = "перевернутая" if card.is_reversed else "прямая"
        if card.position_name:
            parts.append(f"{card.position_name}: {card.name} ({orientation})")
        else:
            parts.append(f"{card.name} ({orientation})")
    return ", ".join(parts)


def _build_result_text(cards_line: str, interpretation: str) -> str:
    """Build full text payload for reading response.

    Args:
        cards_line: Human-readable cards summary.
        interpretation: LLM interpretation text.

    Returns:
        str: Combined cards summary and interpretation text.
    """
    return f"Выпавшие карты: {cards_line}\n\n{interpretation}"


async def _reply_long_text(message: Message, text: str) -> None:
    """Send text in multiple Telegram messages when it is too long.

    Args:
        message: Telegram message used as reply anchor.
        text: Full text to send in chunks.
    """
    chunks = _split_text_by_sentences(text, TELEGRAM_TEXT_LIMIT)
    for chunk in chunks:
        await message.reply_text(chunk)


async def _send_result_images(message: Message, image_paths: list[Path], result_text: str) -> None:
    """Send one image or media group and then tail text chunks.

    Args:
        message: Telegram message used for reply.
        image_paths: Saved image files for one reading.
        result_text: Full textual interpretation payload.
    """
    chunks = _split_text_by_sentences(result_text, TELEGRAM_CAPTION_LIMIT)
    if len(image_paths) == 1:
        with image_paths[0].open("rb") as image_file:
            await message.reply_photo(photo=image_file, caption=chunks[0])
        for chunk in chunks[1:]:
            await message.reply_text(chunk)
        return

    image_files = [path.open("rb") for path in image_paths]
    try:
        media = [
            InputMediaPhoto(
                media=image_files[index],
                caption=chunks[0] if index == 0 else None,
            )
            for index in range(len(image_files))
        ]
        await message.reply_media_group(media=media)
    finally:
        for image_file in image_files:
            image_file.close()

    for chunk in chunks[1:]:
        await message.reply_text(chunk)


def _split_text_by_sentences(text: str, limit: int) -> list[str]:
    """Split text into chunks preserving paragraph boundaries.

    Args:
        text: Source text.
        limit: Maximum chunk size.

    Returns:
        list[str]: Ordered text chunks suitable for Telegram messages.
    """
    if len(text) <= limit:
        return [text]

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text.strip()) if part.strip()]
    if not paragraphs:
        return _split_hard(text, limit)

    chunks: list[str] = []
    current_chunk = ""
    for paragraph in paragraphs:
        paragraph_chunks = _split_paragraph_by_sentences(paragraph, limit)
        for paragraph_chunk in paragraph_chunks:
            candidate = paragraph_chunk if not current_chunk else f"{current_chunk}\n\n{paragraph_chunk}"
            if len(candidate) <= limit:
                current_chunk = candidate
                continue

            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = paragraph_chunk

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _split_hard(text: str, limit: int) -> list[str]:
    """Split text by strict character limit when sentence split is impossible.

    Args:
        text: Source text chunk.
        limit: Maximum allowed chunk size.

    Returns:
        list[str]: Hard-split chunks by size.
    """
    normalized = text.strip()
    if not normalized:
        return []
    return [normalized[i : i + limit] for i in range(0, len(normalized), limit)]


def _split_paragraph_by_sentences(paragraph: str, limit: int) -> list[str]:
    """Split one paragraph by sentence boundaries.

    Args:
        paragraph: Source paragraph without blank lines.
        limit: Maximum chunk size.

    Returns:
        list[str]: Paragraph parts that fit message length limits.
    """
    if len(paragraph) <= limit:
        return [paragraph]

    sentences = [part.strip() for part in re.split(r"(?<=[.!?…])\s+", paragraph) if part.strip()]
    if not sentences:
        return _split_hard(paragraph, limit)

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = sentence if not current else f"{current} {sentence}"
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(sentence) <= limit:
            current = sentence
            continue

        chunks.extend(_split_hard(sentence, limit))

    if current:
        chunks.append(current)
    return chunks


def _resolve_spread_type(user_data: dict[str, Any]) -> SpreadType:
    """Resolve spread type from user state with safe fallback.

    Args:
        user_data: PTB user state dictionary.

    Returns:
        SpreadType: Active spread type.
    """
    value = user_data.get(SPREAD_TYPE_KEY, DEFAULT_SPREAD_TYPE)
    if isinstance(value, str) and value in SUPPORTED_SPREAD_TYPES:
        return cast(SpreadType, value)
    return DEFAULT_SPREAD_TYPE


def _build_layout_payload(spread_result: SpreadResult) -> dict[str, Any]:
    """Build reading layout payload for persistence.

    Args:
        spread_result: Generated spread result.

    Returns:
        dict[str, Any]: JSON-serializable layout payload.
    """
    return {
        "spread_type": spread_result.spread_type,
        "cards": [
            {
                "id": card.id,
                "position": card.position,
                "position_name": card.position_name,
                "is_reversed": card.is_reversed,
            }
            for card in spread_result.cards
        ],
        "image_groups": spread_result.image_groups,
        "metadata": spread_result.metadata,
    }


def _build_spread_keyboard(current_spread_type: SpreadType) -> InlineKeyboardMarkup:
    """Build inline keyboard with spread type options.

    Args:
        current_spread_type: Currently selected spread type.

    Returns:
        InlineKeyboardMarkup: Keyboard for spread type selection.
    """
    def _label(spread_type: SpreadType) -> str:
        prefix = "✅ " if spread_type == current_spread_type else ""
        return f"{prefix}{SPREAD_LABELS[spread_type]}"

    rows = [
        [
            InlineKeyboardButton(_label("1_card"), callback_data="spread:1_card"),
            InlineKeyboardButton(_label("3_cards"), callback_data="spread:3_cards"),
        ],
        [
            InlineKeyboardButton(_label("5_cards_line"), callback_data="spread:5_cards_line"),
            InlineKeyboardButton(_label("pentagram"), callback_data="spread:pentagram"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def get_start_handlers() -> list[BaseHandler]:
    """Build handlers for question flow and admin command.

    Returns:
        list[BaseHandler]: Ordered handler chain for bot application.
    """
    return [
        CommandHandler("start", start_handler),
        CallbackQueryHandler(spread_callback_handler, pattern=r"^spread:"),
        CommandHandler("admin_stats", admin_stats_handler),
        MessageHandler(filters.TEXT & ~filters.COMMAND, question_handler),
        MessageHandler(filters.COMMAND, unknown_command_handler),
    ]


async def _record_llm_usage_event(
    user_tg_id: int,
    status: str,
    total_tokens: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> None:
    """Persist one LLM usage event to analytics storage.

    Args:
        user_tg_id: Telegram user identifier.
        status: LLM request status string.
        total_tokens: Optional total token count.
        prompt_tokens: Optional prompt token count.
        completion_tokens: Optional completion token count.
    """
    try:
        async with SessionLocal() as session:
            repo = LLMUsageRepository(session=session)
            await repo.create_event(
                user_tg_id=user_tg_id,
                status=status,
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
    except Exception:
        logger.exception("Failed to persist LLM usage event user_tg_id=%s status=%s", user_tg_id, status)


def _map_llm_error_to_status(error: Exception) -> str:
    """Map runtime LLM exception to normalized status code.

    Args:
        error: Captured exception from LLM call.

    Returns:
        str: Normalized short status code for analytics.
    """
    text = str(error).lower()
    if "timed out" in text:
        return "timeout"
    if "invalid openrouter api key" in text:
        return "invalid_key"
    if "llm api error" in text:
        return "api_error"
    if "network error" in text:
        return "network_error"
    return "error"
