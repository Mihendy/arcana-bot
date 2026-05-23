from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserProfileDTO:
    """Output of GetUserProfileUseCase — pure profile data, no platform types."""

    daily_limit: int
    bonus_balance: int
    referrals_count: int
    premium_price_stars: int
    premium_price_rub: int
    subscription_tier: str | None
    premium_expires_at: datetime | None
