"""RegisterUserUseCase — upsert a platform identity and commit."""

from __future__ import annotations

import logging

from app.application.dto.registration import RegistrationResult
from app.domain.ports.unit_of_work import IUnitOfWork
from app.domain.ports.user_repo import IUserRepository

logger = logging.getLogger(__name__)

_REFERRAL_BONUS = 3


class RegisterUserUseCase:
    """Idempotently register a user from any platform entry point.

    Owns exactly one commit.  Returns a ``RegistrationResult`` so the
    presentation layer knows whether to show a "welcome" greeting and
    whether to push a notification to the referrer.

    Referral logic fires only for genuinely new users.  If the caller
    supplies a ``referrer_external_id``, the referrer's ``bonus_balance``
    is incremented by ``_REFERRAL_BONUS`` in the same transaction.
    """

    def __init__(self, user_repo: IUserRepository, uow: IUnitOfWork) -> None:
        self._user_repo = user_repo
        self._uow = uow

    async def execute(
        self,
        platform: str,
        external_id: str,
        display_name: str,
        referrer_external_id: str | None = None,
    ) -> RegistrationResult:
        """Get-or-create a user, apply referral bonus for new users, then commit.

        Args:
            platform: Platform identifier, e.g. ``"telegram"``.
            external_id: Platform-native user id as a string.
            display_name: Human-readable name for the platform identity.
            referrer_external_id: The platform-native id of the referring user,
                or ``None`` if no referral link was present.

        Returns:
            RegistrationResult with flags the handler uses to drive UX.
        """
        user, created = await self._user_repo.get_or_create(
            platform=platform,
            external_id=external_id,
            display_name=display_name,
        )

        confirmed_referrer_external_id: str | None = None

        if created and referrer_external_id and referrer_external_id != external_id:
            referrer = await self._user_repo.get_by_platform_id(platform, referrer_external_id)
            if referrer is not None:
                await self._user_repo.set_referrer(user.id, referrer.id)
                await self._user_repo.add_bonus_balance(referrer.id, _REFERRAL_BONUS)
                confirmed_referrer_external_id = referrer_external_id
                logger.info(
                    "referral registered new_user_id=%d referrer_id=%d bonus=%d",
                    user.id,
                    referrer.id,
                    _REFERRAL_BONUS,
                )

        await self._uow.commit()
        return RegistrationResult(
            is_new_user=created,
            has_referrer=confirmed_referrer_external_id is not None,
            referrer_external_id=confirmed_referrer_external_id,
        )
