"""Analytics service backed by SQL aggregates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import Select, func, select

from app.core.db import SessionLocal
from app.models.llm_usage import LLMUsageEvent
from app.models.reading import Reading
from app.models.user import User


class AnalyticsService:
    """Provides lightweight analytics metrics for admin insights."""

    async def get_total_users(self) -> int:
        """Count all users registered in the system.

        Returns:
            int: Total user count.
        """
        async with SessionLocal() as session:
            stmt: Select[tuple[int]] = select(func.count(User.id))
            result = await session.execute(stmt)
            return int(result.scalar() or 0)

    async def get_readings_count(self, period: Literal["day", "month"] = "day") -> int:
        """Count readings created in selected period.

        Args:
            period: Aggregation period, either ``day`` or ``month``.

        Returns:
            int: Number of readings in selected time range.
        """
        now = datetime.now(timezone.utc)
        if period == "month":
            start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        else:
            start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

        async with SessionLocal() as session:
            stmt: Select[tuple[int]] = select(func.count(Reading.id)).where(Reading.created_at >= start)
            result = await session.execute(stmt)
            return int(result.scalar() or 0)

    async def get_llm_usage_stats(self) -> dict[str, int]:
        """Return aggregated LLM usage metrics.

        Returns:
            dict[str, int]: Dictionary with ``success_calls`` and ``total_tokens``.
        """
        try:
            async with SessionLocal() as session:
                base_stmt = select(func.count(LLMUsageEvent.id)).where(LLMUsageEvent.status == "success")
                success_calls = int((await session.execute(base_stmt)).scalar() or 0)

                tokens_stmt = select(func.coalesce(func.sum(LLMUsageEvent.total_tokens), 0)).where(
                    LLMUsageEvent.status == "success"
                )
                total_tokens = int((await session.execute(tokens_stmt)).scalar() or 0)
        except Exception:
            success_calls = 0
            total_tokens = 0

        return {
            "success_calls": success_calls,
            "total_tokens": total_tokens,
        }


analytics_service = AnalyticsService()
