"""VK reading result formatter."""

from __future__ import annotations

import logging
from io import BytesIO

from vkbottle.bot import Message

from app.application.dto.reading import ReadingResult
from app.bot.utils import build_reading_text, split_text_by_sentences
from app.infrastructure.vk.photo_uploader import VKPhotoUploader

logger = logging.getLogger(__name__)

_VK_MESSAGE_LIMIT = 4096


async def send_reading_result(
    message: Message,
    result: ReadingResult,
    uploader: VKPhotoUploader,
) -> None:
    """Send reading result to a VK user, with photo when available."""
    text = build_reading_text(result)
    chunks = split_text_by_sentences(text, _VK_MESSAGE_LIMIT)

    attachment: str | None = None
    if result.image_bytes:
        try:
            buf = BytesIO(result.image_bytes)
            attachment = await uploader.upload_message_photo(buf, "reading.png")
        except Exception:
            logger.warning("vk photo upload failed, sending without image", exc_info=True)

    await message.answer(chunks[0], attachment=attachment)
    for chunk in chunks[1:]:
        await message.answer(chunk)
