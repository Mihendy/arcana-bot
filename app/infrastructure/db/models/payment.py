from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.models.base import InfraBase

if TYPE_CHECKING:
    from app.infrastructure.db.models.user import UserORM


class PaymentORM(InfraBase):
    """Persistent log of every payment attempt.

    A row is created when the user initiates a purchase and updated when
    the provider webhook arrives.  ``provider_payment_id`` is the lookup
    key for that webhook.
    """

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Decimal for YooKassa (fractional rubles); integer Stars fit fine too.
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)   # 'RUB' | 'XTR'
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # 'yookassa' | 'tg_stars'
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )                                                                   # 'pending' | 'confirmed' | 'failed'
    # Set by the provider on confirmation; used to match incoming webhooks.
    provider_payment_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[UserORM] = relationship(back_populates="payments")
