from __future__ import annotations

from typing import Protocol


class ILLMUsageRepository(Protocol):
    """Abstract persistence contract for LLM call analytics events."""

    async def create_event(
        self,
        user_id: int,
        status: str,
        total_tokens: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> None:
        """Persist one LLM usage event.

        ``user_id`` is the internal domain user id, not a platform-specific id.
        Infrastructure adapters are responsible for any platform-id mapping.
        """
        ...

    async def get_stats(self) -> dict[str, int]:
        """Return aggregated usage counters.

        Returns:
            dict with keys ``success_calls`` and ``total_tokens``.
        """
        ...
