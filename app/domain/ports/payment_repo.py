from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from app.domain.entities.payment import Payment


class IPaymentRepository(Protocol):
    """Persistence contract for Payment aggregates."""

    async def create(
        self,
        user_id: int,
        amount: Decimal,
        currency: str,
        provider: str,
    ) -> Payment:
        """Persist a new pending payment and return it with the assigned id.

        Implementations must flush the session so the caller gets a real
        ``id`` before the outer transaction is committed.
        """
        ...

    async def get_by_id(self, payment_id: int) -> Payment | None:
        """Return payment by internal id, or ``None``."""
        ...

    async def get_by_provider_id(self, provider_payment_id: str) -> Payment | None:
        """Return payment by the provider's transaction id, or ``None``.

        Used when the provider pushes a webhook with their own identifier
        (e.g. a YooKassa payment id).
        """
        ...

    async def set_provider_id(self, payment_id: int, provider_payment_id: str) -> None:
        """Store the provider's transaction id on a pending payment.

        Called after invoice creation for providers that assign an id upfront
        (e.g. YooKassa).  Does not change the payment status.
        """
        ...

    async def confirm(self, payment_id: int, provider_payment_id: str) -> None:
        """Atomically set status='confirmed' and record the provider charge id."""
        ...
