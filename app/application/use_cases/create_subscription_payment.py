"""CreateSubscriptionPaymentUseCase — initiate a subscription purchase."""

from __future__ import annotations

import logging
from decimal import Decimal

from app.core.config import Settings
from app.domain.ports.payment_gateway import IPaymentGateway
from app.domain.ports.payment_repo import IPaymentRepository
from app.domain.ports.unit_of_work import IUnitOfWork

logger = logging.getLogger(__name__)

_PROVIDER_CURRENCIES: dict[str, str] = {
    "tg_stars": "XTR",
    "yookassa": "RUB",
}


class UnknownProviderError(ValueError):
    """Raised when an unsupported payment provider is requested."""


class CreateSubscriptionPaymentUseCase:
    """Create a pending payment record, obtain an invoice URL, then commit.

    Sequence:
    1. Create pending DB row → flush → get ``payment.id``.
    2. Call ``gateway.create_invoice(payment_db_id, ...)`` — embeds our id
       as the Telegram invoice payload so the confirmation handler can find
       the record without a provider-id lookup.
    3. Commit the pending record (single commit, no dangling transaction
       during the external API call because flush is used in step 1).
    4. Return the invoice URL to the handler.

    If the gateway call raises, the pending row is rolled back by the
    session context manager in the DI scope — no orphan records.
    """

    def __init__(
        self,
        gateway: IPaymentGateway,
        payment_repo: IPaymentRepository,
        uow: IUnitOfWork,
        settings: Settings,
    ) -> None:
        self._gateway = gateway
        self._payment_repo = payment_repo
        self._uow = uow
        self._settings = settings

    def _resolve_amount(self, provider_name: str) -> tuple[int, str]:
        """Return ``(amount, currency)`` for the given provider from settings."""
        if provider_name == "tg_stars":
            return self._settings.premium_price_stars, "XTR"
        if provider_name == "yookassa":
            return self._settings.premium_price_rub, "RUB"
        raise UnknownProviderError(provider_name)

    async def execute(self, user_id: int, provider_name: str) -> str:
        """Create a pending payment and return the hosted invoice URL.

        Args:
            user_id: Internal DB user id.
            provider_name: ``'tg_stars'`` (or ``'yookassa'`` in a later step).

        Returns:
            str: Invoice URL to show the user.

        Raises:
            UnknownProviderError: If ``provider_name`` is not supported.
        """
        if provider_name not in _PROVIDER_CURRENCIES:
            raise UnknownProviderError(provider_name)

        amount, currency = self._resolve_amount(provider_name)

        payment = await self._payment_repo.create(
            user_id=user_id,
            amount=Decimal(amount),
            currency=currency,
            provider=provider_name,
        )
        # payment.id is now valid (flush happened inside create())

        invoice_url, provider_payment_id = await self._gateway.create_invoice(
            payment_db_id=payment.id,
            amount=amount,
            currency=currency,
        )

        if provider_payment_id is not None:
            await self._payment_repo.set_provider_id(payment.id, provider_payment_id)

        await self._uow.commit()
        logger.info(
            "payment created user_id=%d provider=%s payment_id=%d",
            user_id,
            provider_name,
            payment.id,
        )
        return invoice_url
