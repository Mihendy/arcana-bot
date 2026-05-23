from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    """Platform-agnostic user entity. Contains no messenger-specific fields."""

    id: int
    created_at: datetime
    daily_limit: int = 3
    bonus_balance: int = 0
    premium_expires_at: datetime | None = None
    subscription_tier: str | None = None


@dataclass(frozen=True)
class PlatformIdentity:
    """Links a User to a specific messaging platform account.

    Supports Telegram, Web3 wallet, future platforms — one user may have many.
    """

    user_id: int
    platform: str        # "telegram" | "web" | "web3" | ...
    external_id: str     # tg_id as string, wallet address, OAuth sub, etc.
    display_name: str
