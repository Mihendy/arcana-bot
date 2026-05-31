from __future__ import annotations

from typing import Protocol


class IPaymentGateway(Protocol):
    """Abstract payment provider.

    Every concrete adapter (Telegram Stars, YooKassa, …) must satisfy this
    interface.  ``create_invoice`` returns a URL the user opens to complete
    the payment — a Stars invoice link or a YooKassa checkout page.
    """

    async def create_invoice(
        self,
        payment_db_id: int,
        amount: int,
        currency: str,
    ) -> tuple[str, str | None]:
        """Create a hosted payment page and return (url, provider_payment_id).

        Args:
            payment_db_id: Our internal payment row id, embedded as the
                invoice payload so we can match the confirmation callback.
            amount: Amount in the currency unit used by the provider.
            currency: ISO-style currency code ('XTR' or 'RUB').

        Returns:
            tuple: ``(url, provider_payment_id)`` where ``provider_payment_id``
            is ``None`` when the provider does not assign an id at invoice
            creation time (e.g. Telegram Stars — the charge id only arrives
            in the SuccessfulPayment event).
        """
        ...
