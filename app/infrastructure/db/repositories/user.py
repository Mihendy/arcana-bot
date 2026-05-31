from __future__ import annotations

from datetime import date

from sqlalchemy import Date, case, cast, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import PlatformIdentity, User
from app.infrastructure.db.models.platform_identity import PlatformIdentityORM
from app.infrastructure.db.models.user import UserORM


class PostgresUserRepository:
    """Implements IUserRepository against PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_platform_id(self, platform: str, external_id: str) -> User | None:
        """Return the user linked to a platform identity, or ``None``."""
        result = await self._session.execute(
            select(UserORM)
            .join(PlatformIdentityORM, PlatformIdentityORM.user_id == UserORM.id)
            .where(
                PlatformIdentityORM.platform == platform,
                PlatformIdentityORM.external_id == external_id,
            )
        )
        row = result.scalar_one_or_none()
        return _user_to_entity(row) if row else None

    async def get_or_create(
        self,
        platform: str,
        external_id: str,
        display_name: str,
    ) -> tuple[User, bool]:
        """Return existing user or atomically create a new one.

        Uses a PostgreSQL SAVEPOINT (``begin_nested``) so that a concurrent
        INSERT from another task racing on the same (platform, external_id)
        only rolls back the savepoint, not the outer transaction.  This
        eliminates the race condition: the second task catches IntegrityError
        and re-reads the row committed by the first task.
        """
        existing = await self.get_by_platform_id(platform, external_id)
        if existing:
            return existing, False

        try:
            async with self._session.begin_nested():  # SAVEPOINT
                user_orm = UserORM()
                self._session.add(user_orm)
                await self._session.flush()  # populate user_orm.id

                identity_orm = PlatformIdentityORM(
                    user_id=user_orm.id,
                    platform=platform,
                    external_id=external_id,
                    display_name=display_name,
                )
                self._session.add(identity_orm)
                await self._session.flush()  # may raise IntegrityError

            return _user_to_entity(user_orm), True

        except IntegrityError:
            # Another concurrent task committed the same identity first.
            # The savepoint was rolled back automatically; the outer
            # transaction is clean — we can SELECT immediately.
            user = await self.get_by_platform_id(platform, external_id)
            if user is None:
                raise  # Unexpected: constraint fired but row not found
            return user, False

    async def count_all(self) -> int:
        """Return total number of registered users."""
        from sqlalchemy import func
        result = await self._session.execute(
            select(func.count(UserORM.id))
        )
        return int(result.scalar() or 0)

    async def list_platform_identities(self, platform: str) -> list[PlatformIdentity]:
        """Return active (non-blocked) identities for a platform."""
        result = await self._session.execute(
            select(PlatformIdentityORM)
            .join(UserORM, UserORM.id == PlatformIdentityORM.user_id)
            .where(
                PlatformIdentityORM.platform == platform,
                PlatformIdentityORM.blocked_at.is_(None),
            )
            .order_by(UserORM.id.asc())
        )
        return [_identity_to_entity(row) for row in result.scalars().all()]

    async def mark_blocked_many(self, external_ids: list[str]) -> None:
        """Set blocked_at = now() for the given Telegram external IDs.

        Idempotent — rows already marked are skipped by the WHERE clause.
        """
        if not external_ids:
            return
        await self._session.execute(
            update(PlatformIdentityORM)
            .where(
                PlatformIdentityORM.platform == "telegram",
                PlatformIdentityORM.external_id.in_(external_ids),
                PlatformIdentityORM.blocked_at.is_(None),
            )
            .values(blocked_at=func.now())
        )


    async def decrement_limits(self, user_id: int) -> None:
        """Atomically consume one reading slot via a single CASE UPDATE.

        Priority: daily_limit first, bonus_balance as fallback.
        A single round-trip eliminates the read-modify-write race.
        """
        await self._session.execute(
            update(UserORM)
            .where(UserORM.id == user_id)
            .values(
                daily_limit=case(
                    (UserORM.daily_limit > 0, UserORM.daily_limit - 1),
                    else_=UserORM.daily_limit,
                ),
                bonus_balance=case(
                    (
                        (UserORM.daily_limit <= 0) & (UserORM.bonus_balance > 0),
                        UserORM.bonus_balance - 1,
                    ),
                    else_=UserORM.bonus_balance,
                ),
            )
        )

    async def set_referrer(self, user_id: int, referrer_user_id: int) -> None:
        """Set referrer_id for a newly created user."""
        await self._session.execute(
            update(UserORM)
            .where(UserORM.id == user_id)
            .values(referrer_id=referrer_user_id)
        )

    async def add_bonus_balance(self, user_id: int, amount: int) -> None:
        """Atomically increment bonus_balance; safe under concurrent writes."""
        await self._session.execute(
            update(UserORM)
            .where(UserORM.id == user_id)
            .values(bonus_balance=UserORM.bonus_balance + amount)
        )

    async def count_referrals(self, user_id: int) -> int:
        """Return count of users whose referrer_id equals user_id."""
        result = await self._session.execute(
            select(func.count(UserORM.id)).where(UserORM.referrer_id == user_id)
        )
        return int(result.scalar() or 0)

    async def get_identity_by_user_id(
        self, user_id: int, platform: str
    ) -> PlatformIdentity | None:
        """Return the first platform identity matching user_id + platform."""
        result = await self._session.execute(
            select(PlatformIdentityORM).where(
                PlatformIdentityORM.user_id == user_id,
                PlatformIdentityORM.platform == platform,
            )
        )
        row = result.scalar_one_or_none()
        return _identity_to_entity(row) if row else None

    async def maybe_reset_daily_limit(self, user_id: int, msk_today: date) -> bool:
        """Reset daily_limit = 3 if last_reset_at is before today (MSK).

        Single atomic UPDATE — safe under concurrent requests.
        Returns True when the reset was applied.
        """
        result = await self._session.execute(
            update(UserORM)
            .where(UserORM.id == user_id)
            .where(
                cast(
                    func.timezone("Europe/Moscow", UserORM.last_reset_at),
                    Date,
                ) < msk_today
            )
            .values(daily_limit=3, last_reset_at=func.now())
        )
        return result.rowcount > 0  # type: ignore[return-value]

    async def extend_or_set_premium(self, user_id: int, days: int = 30) -> None:
        """Activate or extend premium subscription in a single atomic UPDATE.

        Stacks on an existing active subscription; starts fresh otherwise.
        """
        interval = text(f"INTERVAL '{days} days'")
        await self._session.execute(
            update(UserORM)
            .where(UserORM.id == user_id)
            .values(
                premium_expires_at=case(
                    (
                        UserORM.premium_expires_at > func.now(),
                        UserORM.premium_expires_at + interval,
                    ),
                    else_=func.now() + interval,
                ),
                subscription_tier="monthly",
            )
        )


def _user_to_entity(row: UserORM) -> User:
    return User(
        id=row.id,
        created_at=row.created_at,
        daily_limit=row.daily_limit,
        bonus_balance=row.bonus_balance,
        premium_expires_at=row.premium_expires_at,
        subscription_tier=row.subscription_tier,
        last_reset_at=row.last_reset_at,
    )


def _identity_to_entity(row: PlatformIdentityORM) -> PlatformIdentity:
    return PlatformIdentity(
        user_id=row.user_id,
        platform=row.platform,
        external_id=row.external_id,
        display_name=row.display_name,
    )
