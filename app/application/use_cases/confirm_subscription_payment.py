"""ConfirmSubscriptionPaymentUseCase — mark a payment as confirmed and activate premium."""

from __future__ import annotations

import logging

from app.domain.ports.payment_repo import IPaymentRepository
from app.domain.ports.unit_of_work import IUnitOfWork
from app.domain.ports.user_repo import IUserRepository

logger = logging.getLogger(__name__)


class PaymentNotFoundError(Exception):
    """Raised when the payment record cannot be found."""


class ConfirmSubscriptionPaymentUseCase:
    """Confirm a payment and activate/extend the user's premium subscription.

    Idempotent: calling with an already-confirmed ``payment_db_id`` is a
    no-op (safe for duplicate webhook deliveries or retry storms).

    Sequence:
    1. Load payment by internal id.
    2. Guard: if already ``confirmed`` → return immediately.
    3. ``payment_repo.confirm(...)`` — sets status + stores provider charge id.
    4. ``user_repo.extend_or_set_premium(user_id, days=30)`` — stacks on
       existing subscription or starts fresh, in one atomic UPDATE.
    5. Single ``uow.commit()``.
    """

    def __init__(
        self,
        payment_repo: IPaymentRepository,
        user_repo: IUserRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._payment_repo = payment_repo
        self._user_repo = user_repo
        self._uow = uow

    async def execute(self, payment_db_id: int, provider_charge_id: str) -> int:
        """Confirm the payment and extend the user's subscription.

        Args:
            payment_db_id: Our internal payment row id (from invoice payload).
            provider_charge_id: Provider's transaction id (stored for audits).

        Returns:
            int: The internal user_id of the subscriber (for post-commit
            notifications without reopening the transaction).

        Raises:
            PaymentNotFoundError: If no payment row matches ``payment_db_id``.
        """
        payment = await self._payment_repo.get_by_id(payment_db_id)
        if payment is None:
            raise PaymentNotFoundError(payment_db_id)

        if payment.status == "confirmed":
            logger.info("payment already confirmed payment_id=%d — skipping", payment_db_id)
            return payment.user_id

        await self._payment_repo.confirm(payment_db_id, provider_charge_id)
        await self._user_repo.extend_or_set_premium(payment.user_id, days=30)
        await self._uow.commit()

        logger.info(
            "payment confirmed payment_id=%d user_id=%d charge=%s",
            payment_db_id,
            payment.user_id,
            provider_charge_id,
        )
        return payment.user_id
