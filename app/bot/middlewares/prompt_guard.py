"""Input guardrails against prompt injection attempts."""

from __future__ import annotations

STOP_PHRASES = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "system prompt",
    "reveal system prompt",
    "show system prompt",
    "developer mode",
    "jailbreak",
    "данные системного промпта",
    "покажи системный промпт",
    "раскрой системный промпт",
    "режим разработчика",
    "игнорируй предыдущие инструкции",
)


def find_injection_phrase(text: str) -> str | None:
    """Find blocked phrase in user text.

    Args:
        text: User-provided question text.

    Returns:
        str | None: Matched blocked phrase or ``None`` when safe.
    """
    normalized = text.lower()
    for phrase in STOP_PHRASES:
        if phrase in normalized:
            return phrase
    return None
