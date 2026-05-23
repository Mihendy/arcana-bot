from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Payment:
    """Domain entity for a single payment attempt."""

    id: int               # 0 before persistence
    user_id: int
    amount: Decimal
    currency: str         # 'RUB' | 'XTR'
    provider: str         # 'yookassa' | 'tg_stars'
    status: str           # 'pending' | 'confirmed' | 'failed'
    provider_payment_id: str | None
    created_at: datetime
    updated_at: datetime
