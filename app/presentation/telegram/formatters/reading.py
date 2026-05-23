"""Telegram presentation helpers for tarot reading results."""

from __future__ import annotations
from io import BytesIO

from telegram import Message

from app.application.dto.reading import ReadingResult
from app.bot.utils import TELEGRAM_CAPTION_LIMIT, TELEGRAM_TEXT_LIMIT, _split_text_by_sentences


def build_reading_text(result: ReadingResult) -> str:
    """Combine cards summary and interpretation into one message body."""
    return f"Выпавшие карты: {result.cards_summary}\n\n{result.interpretation}"


async def send_reading_result(message: Message, result: ReadingResult) -> None:
    """Send a reading result to the user, with or without an image.

    If the image upload succeeded the interpretation is sent as a photo
    caption (split across multiple messages when too long).  Without an
    image, plain text chunks are used.

    Args:
        message: The incoming user message to reply to.
        result: Platform-agnostic reading result from ``PerformReadingUseCase``.
    """
    text = build_reading_text(result)

    if result.image_bytes or result.image_url:
        chunks = _split_text_by_sentences(text, TELEGRAM_CAPTION_LIMIT)
        if result.image_bytes:
            photo: BytesIO | str = BytesIO(result.image_bytes)
            photo.name = "reading.png"  # type: ignore[attr-defined]
        else:
            photo = result.image_url  # type: ignore[assignment]
        await message.reply_photo(photo=photo, caption=chunks[0])
        for chunk in chunks[1:]:
            await message.reply_text(chunk)
    else:
        for chunk in _split_text_by_sentences(text, TELEGRAM_TEXT_LIMIT):
            await message.reply_text(chunk)
