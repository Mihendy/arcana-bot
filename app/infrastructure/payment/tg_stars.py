"""Telegram Stars payment gateway adapter."""

from __future__ import annotations

from telegram import Bot, LabeledPrice


class TelegramStarsPaymentGateway:
    """Wraps ``bot.create_invoice_link`` to satisfy ``IPaymentGateway``.

    Telegram Stars invoices use ``provider_token=""`` and currency ``"XTR"``.
    The ``payload`` is set to ``str(payment_db_id)`` so the
    ``successful_payment`` handler can look up our record without a DB query
    by provider transaction id.
    """

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def create_invoice(
        self,
        payment_db_id: int,
        amount: int,
        currency: str,
    ) -> tuple[str, str | None]:
        """Return (invoice_url, None) — Telegram Stars has no upfront charge id."""
        url = await self._bot.create_invoice_link(
            title="Подписка на 1 месяц",
            description="Безлимитные расклады Arcana на 30 дней",
            payload=str(payment_db_id),
            provider_token="",  # empty string is required for Telegram Stars
            currency="XTR",
            prices=[LabeledPrice(label="Подписка Arcana", amount=amount)],
        )
        return url, None
