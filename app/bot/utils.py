"""Utility functions for bot text processing."""

import re

TELEGRAM_TEXT_LIMIT = 4000
TELEGRAM_CAPTION_LIMIT = 1024


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

