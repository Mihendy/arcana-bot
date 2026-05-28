from __future__ import annotations

from typing import Protocol

from app.domain.entities.user import PlatformIdentity, User


class IUserRepository(Protocol):
    """Abstract persistence contract for User aggregates."""

    async def get_by_platform_id(self, platform: str, external_id: str) -> User | None:
        """Return user linked to the given platform identity, or ``None``."""
        ...

    async def get_or_create(
        self,
        platform: str,
        external_id: str,
        display_name: str,
    ) -> tuple[User, bool]:
        """Return existing user or create a new one.

        Returns:
            tuple[User, bool]: The user and ``True`` when newly created.
        """
        ...

    async def count_all(self) -> int:
        """Return total number of registered users."""
        ...

    async def list_platform_identities(self, platform: str) -> list[PlatformIdentity]:
        """Return all identities for a specific platform.

        Used by broadcast workflows (e.g. daily card) to resolve delivery targets
        without coupling the use case to Telegram-specific IDs.
        """
        ...

    async def decrement_limits(self, user_id: int) -> None:
        """Atomically consume one reading slot.

        Decrements ``daily_limit`` first; falls back to ``bonus_balance``
        when ``daily_limit`` is already zero.  Caller must have verified
        that at least one counter is positive before calling this.
        """
        ...

    async def set_referrer(self, user_id: int, referrer_user_id: int) -> None:
        """Set referrer_id for a user (called once at registration)."""
        ...

    async def add_bonus_balance(self, user_id: int, amount: int) -> None:
        """Atomically increment a user's bonus_balance by amount."""
        ...

    async def count_referrals(self, user_id: int) -> int:
        """Return the number of users who have this user as their referrer."""
        ...

    async def get_identity_by_user_id(
        self, user_id: int, platform: str
    ) -> PlatformIdentity | None:
        """Return the platform identity for a user, or ``None`` if not found."""
        ...

    async def extend_or_set_premium(self, user_id: int, days: int = 30) -> None:
        """Activate or extend premium subscription atomically.

        If ``premium_expires_at`` is already in the future, adds ``days``
        to it (stacking).  Otherwise sets it to ``now() + days``.
        Always sets ``subscription_tier = 'monthly'``.
        """
        ...

    async def reset_daily_limits(self) -> int:
        """Restore daily_limit = 3 for every user who has spent readings.

        Only touches rows where daily_limit < 3, so users who haven't used
        any slots today are unaffected.

        Returns:
            int: Number of rows updated.
        """
        ...
