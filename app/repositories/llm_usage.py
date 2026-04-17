"""Repository for LLM usage analytics events."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage import LLMUsageEvent


class LLMUsageRepository:
    """CRUD operations for LLM usage events."""

    def __init__(self, session: AsyncSession) -> None:
        """Store session dependency.

        Args:
            session: Active SQLAlchemy async session.
        """
        self.session = session

    async def create_event(
        self,
        user_tg_id: int,
        status: str,
        total_tokens: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> LLMUsageEvent:
        """Persist one LLM usage analytics event.

        Args:
            user_tg_id: Telegram user ID that initiated the LLM request.
            status: Call result status (for example: ``success`` or ``timeout``).
            total_tokens: Full token count returned by provider.
            prompt_tokens: Prompt token count returned by provider.
            completion_tokens: Completion token count returned by provider.

        Returns:
            LLMUsageEvent: Persisted usage event.
        """
        event = LLMUsageEvent(
            user_tg_id=user_tg_id,
            status=status,
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event
