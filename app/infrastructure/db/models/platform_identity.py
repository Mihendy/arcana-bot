from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.models.base import InfraBase

if TYPE_CHECKING:
    from app.infrastructure.db.models.user import UserORM


class PlatformIdentityORM(InfraBase):
    """Maps a user to a platform-specific account (Telegram, Web3, OAuth, …).

    The composite unique constraint at the DB level prevents duplicates even
    under concurrent inserts racing to register the same external account.
    """

    __tablename__ = "platform_identities"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_platform_external_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    blocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[UserORM] = relationship(back_populates="platform_identities")
