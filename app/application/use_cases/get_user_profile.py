"""GetUserProfileUseCase — collect profile data for a platform user."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.application.dto.profile import UserProfileDTO
from app.core.config import Settings
from app.domain.ports.unit_of_work import IUnitOfWork
from app.domain.ports.user_repo import IUserRepository

_DAILY_LIMIT_DEFAULT = 3


class GetUserProfileUseCase:
    """Fetch limits and referral count for a single user.

    Applies the same lazy daily-limit reset as PerformReadingUseCase so the
    profile always reflects today's allowance even when the user hasn't done
    a reading yet.
    """

    def __init__(
        self,
        user_repo: IUserRepository,
        uow: IUnitOfWork,
        settings: Settings,
    ) -> None:
        self._user_repo = user_repo
        self._uow = uow
        self._tz = ZoneInfo(settings.daily_card_timezone)
        self._settings = settings

    async def execute(self, platform: str, external_id: str) -> UserProfileDTO:
        """Return the user's profile data, resetting daily limit if needed.

        Falls back to zero-state defaults when the user is not yet registered
        (e.g. they send /profile before /start).

        Args:
            platform: Platform identifier, e.g. ``"telegram"``.
            external_id: Platform-native user id as a string.

        Returns:
            UserProfileDTO with current limits, referral count, and prices.
        """
        user = await self._user_repo.get_by_platform_id(platform, external_id)
        prices = dict(
            premium_price_stars=self._settings.premium_price_stars,
            premium_price_rub=self._settings.premium_price_rub,
        )
        if user is None:
            return UserProfileDTO(
                daily_limit=_DAILY_LIMIT_DEFAULT,
                bonus_balance=0,
                referrals_count=0,
                subscription_tier=None,
                premium_expires_at=None,
                **prices,
            )

        msk_today = datetime.now(self._tz).date()
        reset = await self._user_repo.maybe_reset_daily_limit(user.id, msk_today)
        if reset:
            await self._uow.commit()

        daily_limit = _DAILY_LIMIT_DEFAULT if reset else user.daily_limit
        referrals_count = await self._user_repo.count_referrals(user.id)
        return UserProfileDTO(
            daily_limit=daily_limit,
            bonus_balance=user.bonus_balance,
            referrals_count=referrals_count,
            subscription_tier=user.subscription_tier,
            premium_expires_at=user.premium_expires_at,
            **prices,
        )
