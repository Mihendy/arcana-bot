"""Telegram presentation helpers for tarot reading results."""

from __future__ import annotations

from io import BytesIO

from telegram import Message

from app.application.dto.reading import ReadingResult
from app.bot.utils import build_reading_text, split_text_by_sentences

_TEXT_LIMIT = 4000
_CAPTION_LIMIT = 1024


async def send_reading_result(message: Message, result: ReadingResult) -> None:
    """Send a reading result to the user, with or without an image.

    Raises ``telegram.error.TimedOut`` on photo upload failure so the caller
    can decide whether to refund the reading slot.
    """
    text = build_reading_text(result)

    if result.image_bytes or result.image_url:
        chunks = split_text_by_sentences(text, _CAPTION_LIMIT)
        if result.image_bytes:
            photo: BytesIO | str = BytesIO(result.image_bytes)
            photo.name = "reading.png"  # type: ignore[attr-defined]
        else:
            photo = result.image_url  # type: ignore[assignment]
        await message.reply_photo(photo=photo, caption=chunks[0])
        for chunk in chunks[1:]:
            await message.reply_text(chunk)
    else:
        for chunk in split_text_by_sentences(text, _TEXT_LIMIT):
            await message.reply_text(chunk)
