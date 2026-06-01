from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.entities.tarot import SpreadType, TarotCard


@dataclass(frozen=True)
class LLMResult:
    """Structured response from any LLM provider."""

    interpretation: str
    status: str                       # "success" | "guardrail_blocked" | "timeout" | ...
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ILLMProvider(Protocol):
    """Abstract contract for LLM interpretation backends.

    Swap OpenRouter for Anthropic, local Ollama, or a stub in tests
    by providing a different implementation — the use case never changes.
    """

    async def get_interpretation(
        self,
        question: str,
        cards: list[TarotCard],
        spread_type: SpreadType,
    ) -> LLMResult:
        """Generate a tarot reading interpretation for the given spread."""
        ...

    async def get_daily_card_prediction(
        self,
        card: TarotCard,
    ) -> LLMResult:
        """Generate a short daily prediction for a single card."""
        ...
