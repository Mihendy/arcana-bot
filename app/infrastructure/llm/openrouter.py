"""OpenRouter LLM adapter — implements ILLMProvider."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.domain.entities.tarot import SpreadType, TarotCard
from app.domain.ports.llm_port import LLMResult
from app.infrastructure.llm.prompts import (
    DAILY_CARD_SYSTEM_PROMPT,
    GUARDRAIL_FALLBACK_RESPONSE,
    OUTPUT_GUARDRAIL_PHRASES,
    SPREAD_PROMPT_HINTS,
    SPREAD_TITLES,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class OpenRouterLLMAdapter:
    """Calls the OpenRouter /chat/completions endpoint.

    The duplicated HTTP boilerplate from the original ``LLMService`` is
    consolidated in ``_call_api``.  Both public methods delegate request
    execution there and only differ in the messages they build.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    # ------------------------------------------------------------------
    # ILLMProvider implementation
    # ------------------------------------------------------------------

    async def get_interpretation(
        self,
        question: str,
        cards: list[TarotCard],
        spread_type: SpreadType,
    ) -> LLMResult:
        """Generate a tarot reading interpretation for the given spread."""
        if not self._api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")

        char_limit = _calculate_char_limit(spread_type, len(cards))
        user_prompt = _build_interpretation_prompt(question, cards, spread_type, char_limit)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        payload = await self._call_api(messages, log_tag=f"interpretation/{spread_type.value}")
        usage = _extract_usage(payload)
        content = _extract_content(payload)

        if _contains_guardrail_leak(content):
            logger.warning("llm guardrail leak detected; returning fallback")
            return LLMResult(
                interpretation=GUARDRAIL_FALLBACK_RESPONSE,
                status="guardrail_blocked",
                **usage,
            )

        content = _enforce_card_paragraphs(content, cards)
        return LLMResult(interpretation=content, status="success", **usage)

    async def get_daily_card_prediction(self, card: TarotCard) -> LLMResult:
        """Generate a short daily prediction for a single card."""
        if not self._api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")

        user_prompt = (
            "Сформируй предсказание на сегодня по карте.\n"
            f"Карта: {card.name}\n"
            "Положение: прямая\n"
            "Формат: 1-2 предложения, без markdown."
        )
        messages = [
            {"role": "system", "content": DAILY_CARD_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        payload = await self._call_api(messages, log_tag="daily_card")
        usage = _extract_usage(payload)
        content = _extract_content(payload)
        content = _limit_to_two_sentences(content)
        return LLMResult(interpretation=content, status="success", **usage)

    # ------------------------------------------------------------------
    # Shared HTTP transport (single point of truth for auth + error handling)
    # ------------------------------------------------------------------

    async def _call_api(self, messages: list[dict], log_tag: str) -> dict[str, Any]:
        """Execute one /chat/completions call with unified error handling.

        Centralises: header construction, timeout wrapping, HTTP status checks,
        and structured logging.  Both public methods delegate here so changes
        to retry logic, auth headers, or error mapping only need to happen once.

        Args:
            messages: OpenAI-compatible messages list.
            log_tag:  Short identifier used in log lines (e.g. ``"daily_card"``).

        Returns:
            Parsed JSON response body as a dict.

        Raises:
            RuntimeError: On timeout, network error, or non-2xx HTTP status.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.8,
        }

        logger.info("llm_%s status=started", log_tag)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout)) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=body,
                )
        except httpx.TimeoutException as exc:
            logger.warning("llm_%s status=timeout", log_tag)
            raise RuntimeError("LLM request timed out. Please try again.") from exc
        except httpx.RequestError as exc:
            logger.warning("llm_%s status=network_error", log_tag)
            raise RuntimeError(f"LLM network error: {exc}") from exc

        if response.status_code in (401, 403):
            logger.warning("llm_%s status=invalid_key", log_tag)
            raise RuntimeError("Invalid OpenRouter API key.")
        if response.status_code >= 400:
            logger.warning("llm_%s status=api_error code=%s", log_tag, response.status_code)
            raise RuntimeError(f"LLM API error: {response.status_code} {response.text}")

        logger.info("llm_%s status=success", log_tag)
        return response.json()  # type: ignore[no-any-return]


# ------------------------------------------------------------------
# Module-level pure functions (no adapter state needed)
# ------------------------------------------------------------------

def _build_interpretation_prompt(
    question: str,
    cards: list[TarotCard],
    spread_type: SpreadType,
    char_limit: int,
) -> str:
    spread_title = SPREAD_TITLES.get(spread_type, spread_type.value)
    spread_hint = SPREAD_PROMPT_HINTS.get(spread_type, "Сформируй интерпретацию расклада.")
    cards_block = "\n".join(
        f"{c.position}. {c.name} "
        f"({'перевернутая' if c.is_reversed else 'прямая'}, "
        f"arcana={c.arcana.value}, id={c.id})"
        for c in cards
    )
    return (
        f"Тип расклада: {spread_title} ({spread_type.value})\n"
        f"Вопрос пользователя: {question.strip()}\n\n"
        f"Выпавшие карты:\n{cards_block}\n\n"
        f"Инструкция по интерпретации: {spread_hint}\n"
        "Соблюдай системные правила формата и безопасности.\n"
        f"Рекомендуемая длина: не более {char_limit} символов."
    )


def _calculate_char_limit(spread_type: SpreadType, cards_count: int) -> int:
    total = 260 + cards_count * 220
    if spread_type == SpreadType.PENTAGRAM:
        total += 140
    return max(500, min(2400, total))


def _extract_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LLM API returned invalid response format: choices missing.")
    content = choices[0].get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM API returned empty interpretation.")
    return content.strip()


def _extract_usage(payload: dict[str, Any]) -> dict[str, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    return {
        "prompt_tokens": _to_int(usage.get("prompt_tokens")),
        "completion_tokens": _to_int(usage.get("completion_tokens")),
        "total_tokens": _to_int(usage.get("total_tokens")),
    }


def _to_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _contains_guardrail_leak(text: str) -> bool:
    normalized = text.lower()
    return any(phrase in normalized for phrase in OUTPUT_GUARDRAIL_PHRASES)


def _enforce_card_paragraphs(text: str, cards: list[TarotCard]) -> str:
    """Ensure the model output has one paragraph per card."""
    required = len(cards)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(paragraphs) >= required:
        return "\n\n".join(paragraphs)

    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s.strip()]
    if len(sentences) < required:
        return text

    blocks: list[str] = []
    total = len(sentences)
    start = 0
    for idx, card in enumerate(cards):
        end = round((idx + 1) * total / required)
        end = max(end, start + 1)
        chunk = " ".join(sentences[start:end]).strip()
        start = end
        label = card.position_name or f"Карта {card.position}"
        blocks.append(chunk if chunk.lower().startswith(f"{label.lower()}:") else f"{label}: {chunk}")
    return "\n\n".join(blocks)


def _limit_to_two_sentences(text: str) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s.strip()]
    return text.strip() if len(sentences) <= 2 else " ".join(sentences[:2])
