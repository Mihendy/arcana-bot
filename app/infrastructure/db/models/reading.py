from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.models.base import InfraBase

if TYPE_CHECKING:
    from app.infrastructure.db.models.user import UserORM


class ReadingORM(InfraBase):
    """Persisted tarot reading.

    ``image_url`` (legacy scalar) is intentionally absent — all image references
    are stored in the ``image_urls`` JSONB array. A single-image reading is
    represented as a one-element list.
    """

    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    spread_type: Mapped[str] = mapped_column(String(64), nullable=False)
    layout: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_urls: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[UserORM] = relationship(back_populates="readings")
