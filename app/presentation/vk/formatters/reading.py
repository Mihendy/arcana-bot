"""VK reading result formatter."""

from __future__ import annotations

from io import BytesIO

from vkbottle.bot import Message

from app.application.dto.reading import ReadingResult
from app.bot.utils import _split_text_by_sentences
from app.infrastructure.vk.photo_uploader import VKPhotoUploader

_VK_MESSAGE_LIMIT = 4096


def build_reading_text(result: ReadingResult) -> str:
    """Combine cards summary and interpretation into one message body."""
    return f"Выпавшие карты: {result.cards_summary}\n\n{result.interpretation}"


async def send_reading_result(
    message: Message,
    result: ReadingResult,
    uploader: VKPhotoUploader,
) -> None:
    """Send reading result to a VK user, with photo when available.

    VK requires images to be pre-uploaded to their servers, so we use
    ``VKPhotoUploader`` to get a valid attachment string before sending.

    Args:
        message: Incoming vkbottle Message to reply to.
        result: Platform-agnostic reading result.
        uploader: VK photo uploader for the current group.
    """
    text = build_reading_text(result)
    chunks = _split_text_by_sentences(text, _VK_MESSAGE_LIMIT)

    attachment: str | None = None
    if result.image_bytes:
        try:
            buf = BytesIO(result.image_bytes)
            attachment = await uploader.upload_message_photo(buf, "reading.png")
        except Exception:
            pass  # send without photo rather than failing entirely

    first_chunk = chunks[0]
    await message.answer(first_chunk, attachment=attachment)

    for chunk in chunks[1:]:
        await message.answer(chunk)
