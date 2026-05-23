from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.llm_usage import LLMUsageEventORM


class PostgresLLMUsageRepository:
    """Implements ILLMUsageRepository against PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_event(
        self,
        user_id: int,
        status: str,
        total_tokens: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> None:
        """Persist one LLM usage event.

        No ``commit()`` — transaction ownership belongs to the calling use case.
        Fire-and-forget semantics: callers typically wrap this in a bare
        ``try/except Exception`` to avoid interrupting the main flow on failure.
        """
        event = LLMUsageEventORM(
            user_id=user_id,
            status=status,
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        self._session.add(event)
        await self._session.flush()

    async def get_stats(self) -> dict[str, int]:
        """Return aggregated LLM usage counters.

        Returns:
            dict with ``success_calls`` (count) and ``total_tokens`` (sum).
        """
        success_stmt = select(func.count(LLMUsageEventORM.id)).where(
            LLMUsageEventORM.status == "success"
        )
        tokens_stmt = select(
            func.coalesce(func.sum(LLMUsageEventORM.total_tokens), 0)
        ).where(LLMUsageEventORM.status == "success")

        success_calls = int((await self._session.execute(success_stmt)).scalar() or 0)
        total_tokens = int((await self._session.execute(tokens_stmt)).scalar() or 0)
        return {"success_calls": success_calls, "total_tokens": total_tokens}
