"""GetAdminStatsUseCase — aggregate analytics for the admin command."""

from __future__ import annotations

from datetime import datetime, timezone

from app.application.dto.admin_stats import AdminStatsResult
from app.domain.ports.llm_usage_repo import ILLMUsageRepository
from app.domain.ports.reading_repo import IReadingRepository
from app.domain.ports.user_repo import IUserRepository


class GetAdminStatsUseCase:
    """Aggregates analytics data for the admin reporting command.

    Read-only: no commit needed.  The session is only used for queries,
    so the caller may share a read-only session or skip transaction setup.

    Replaces the old ``AnalyticsService`` which mixed repository queries
    with session management in a single class.
    """

    def __init__(
        self,
        user_repo: IUserRepository,
        reading_repo: IReadingRepository,
        llm_usage_repo: ILLMUsageRepository,
    ) -> None:
        self._user_repo = user_repo
        self._reading_repo = reading_repo
        self._llm_usage_repo = llm_usage_repo

    async def execute(self) -> AdminStatsResult:
        """Gather and return aggregated admin metrics.

        Returns:
            AdminStatsResult: Snapshot of current platform usage stats.
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total_users = await self._user_repo.count_all()
        readings_today = await self._reading_repo.count_since(today_start)
        readings_this_month = await self._reading_repo.count_since(month_start)
        llm_stats = await self._llm_usage_repo.get_stats()

        return AdminStatsResult(
            total_users=total_users,
            readings_today=readings_today,
            readings_this_month=readings_this_month,
            llm_success_calls=llm_stats["success_calls"],
            llm_total_tokens=llm_stats["total_tokens"],
        )
