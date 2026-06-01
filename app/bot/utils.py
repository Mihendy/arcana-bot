"""Shared bot utilities — platform-agnostic helpers used by Telegram and VK."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.application.dto.profile import UserProfileDTO
from app.application.dto.reading import ReadingResult

_MSK = ZoneInfo("Europe/Moscow")


def time_until_midnight_msk() -> str:
    """Return human-readable time remaining until midnight Moscow time (≥ 1 мин.)."""
    now = datetime.now(_MSK)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    total_minutes = max(1, int((midnight - now).total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours} ч. {minutes} мин." if hours else f"{minutes} мин."


def build_reading_text(result: ReadingResult) -> str:
    """Combine cards summary and interpretation into one display string."""
    return f"Выпавшие карты: {result.cards_summary}\n\n{result.interpretation}"


def subscription_line(profile: UserProfileDTO) -> str:
    """Return one-line subscription status string for profile display."""
    now = datetime.now(tz=timezone.utc)
    if profile.premium_expires_at and profile.premium_expires_at > now:
        until = profile.premium_expires_at.strftime("%d.%m.%Y")
        return f"💎 Подписка: Премиум (до {until})"
    return "📦 Подписка: Базовый"


def split_text_by_sentences(text: str, limit: int) -> list[str]:
    """Split text into chunks preserving paragraph/sentence boundaries."""
    if len(text) <= limit:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text.strip()) if p.strip()]
    if not paragraphs:
        return _split_hard(text, limit)

    chunks: list[str] = []
    current_chunk = ""
    for paragraph in paragraphs:
        for paragraph_chunk in _split_paragraph_by_sentences(paragraph, limit):
            candidate = paragraph_chunk if not current_chunk else f"{current_chunk}\n\n{paragraph_chunk}"
            if len(candidate) <= limit:
                current_chunk = candidate
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = paragraph_chunk

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def _split_hard(text: str, limit: int) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    return [normalized[i: i + limit] for i in range(0, len(normalized), limit)]


def _split_paragraph_by_sentences(paragraph: str, limit: int) -> list[str]:
    if len(paragraph) <= limit:
        return [paragraph]

    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", paragraph) if s.strip()]
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
        else:
            chunks.extend(_split_hard(sentence, limit))

    if current:
        chunks.append(current)
    return chunks
