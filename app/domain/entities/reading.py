from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.entities.tarot import SpreadType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Reading:
    """A completed tarot reading belonging to a user.

    ``image_urls`` supersedes the legacy ``image_url`` scalar — a single
    public URL is represented as a one-element list.
    """

    id: int
    user_id: int
    question: str
    spread_type: SpreadType
    interpretation: str | None
    image_urls: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
