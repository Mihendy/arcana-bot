from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.models.base import InfraBase

if TYPE_CHECKING:
    from app.infrastructure.db.models.payment import PaymentORM
    from app.infrastructure.db.models.platform_identity import PlatformIdentityORM
    from app.infrastructure.db.models.reading import ReadingORM


class UserORM(InfraBase):
    """Platform-agnostic user row. Messenger-specific IDs live in platform_identities."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    daily_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("3")
    )
    bonus_balance: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    referrer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    premium_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    subscription_tier: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # None = free, 'monthly' = active subscription
    last_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("'2000-01-01 00:00:00+00'"),
    )

    # Self-referential: the user who referred this user (many-to-one)
    referrer: Mapped["UserORM | None"] = relationship(
        "UserORM",
        back_populates="referrals",
        foreign_keys=[referrer_id],
        remote_side=[id],
        lazy="select",
    )
    # Self-referential: users this user has referred (one-to-many)
    referrals: Mapped[list["UserORM"]] = relationship(
        "UserORM",
        back_populates="referrer",
        foreign_keys=[referrer_id],
        lazy="select",
    )

    platform_identities: Mapped[list[PlatformIdentityORM]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="select"
    )
    readings: Mapped[list[ReadingORM]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="select"
    )
    payments: Mapped[list[PaymentORM]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="select"
    )
