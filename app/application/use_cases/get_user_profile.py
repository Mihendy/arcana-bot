"""GetUserProfileUseCase — collect profile data for a platform user."""

from __future__ import annotations

from app.application.dto.profile import UserProfileDTO
from app.core.config import Settings
from app.domain.ports.user_repo import IUserRepository


class GetUserProfileUseCase:
    """Fetch limits and referral count for a single user.

    Read-only: no commit needed.
    """

    def __init__(self, user_repo: IUserRepository, settings: Settings) -> None:
        self._user_repo = user_repo
        self._settings = settings

    async def execute(self, platform: str, external_id: str) -> UserProfileDTO:
        """Return the user's profile data.

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
                daily_limit=3,
                bonus_balance=0,
                referrals_count=0,
                subscription_tier=None,
                premium_expires_at=None,
                **prices,
            )

        referrals_count = await self._user_repo.count_referrals(user.id)
        return UserProfileDTO(
            daily_limit=user.daily_limit,
            bonus_balance=user.bonus_balance,
            referrals_count=referrals_count,
            subscription_tier=user.subscription_tier,
            premium_expires_at=user.premium_expires_at,
            **prices,
        )
