"""Input validation against prompt-injection attempts.

Lives in the application layer so any entrypoint (Telegram, FastAPI, CLI)
can import it without pulling in messenger-specific dependencies.
"""

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
    """Return the first blocked phrase found in ``text``, or ``None`` if safe.

    Args:
        text: Raw user-supplied question.

    Returns:
        str | None: The matched phrase (useful for logging) or ``None``.
    """
    normalized = text.lower()
    for phrase in STOP_PHRASES:
        if phrase in normalized:
            return phrase
    return None
