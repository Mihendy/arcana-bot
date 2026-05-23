"""YooKassa payment gateway adapter."""

from __future__ import annotations

import uuid

import httpx

from app.core.config import Settings

_API_URL = "https://api.yookassa.ru/v3/payments"


class YookassaPaymentGateway:
    """Calls the YooKassa REST API to create a redirect-based payment page.

    Basic Auth uses (shop_id, secret_key) from Settings.
    The YooKassa payment id is returned alongside the redirect URL so the
    caller can store it for webhook-based fallback lookups.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def create_invoice(
        self,
        payment_db_id: int,
        amount: int,
        currency: str,
    ) -> tuple[str, str | None]:
        """Create a YooKassa payment and return (confirmation_url, yookassa_id).

        Args:
            payment_db_id: Our internal DB payment id, stored in metadata.
            amount: Amount in rubles (integer, e.g. 159 for 159 ₽).
            currency: Ignored — YooKassa always uses RUB.

        Returns:
            tuple: ``(confirmation_url, yookassa_payment_id)``
        """
        payload = {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": self._settings.bot_public_url,
            },
            "metadata": {"payment_id": str(payment_db_id)},
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                _API_URL,
                json=payload,
                auth=(self._settings.yookassa_shop_id, self._settings.yookassa_secret_key),
                headers={"Idempotence-Key": str(uuid.uuid4())},
            )
            response.raise_for_status()
            data = response.json()

        yookassa_id: str = data["id"]
        confirmation_url: str = data["confirmation"]["confirmation_url"]
        return confirmation_url, yookassa_id
