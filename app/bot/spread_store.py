"""In-process VK user session state.

Stores per-user ephemeral data (selected spread type, display name cache)
for the lifetime of the process.  Contains no VK-specific types — only
plain Python primitives so the backend can be swapped (e.g. Redis) without
touching handler code.
"""

from __future__ import annotations

from app.domain.entities.tarot import SpreadType


class VKSessionStore:
    def __init__(self) -> None:
        self._spreads: dict[int, str] = {}
        self._names: dict[int, str] = {}

    # ── Spread selection ──────────────────────────────────────────────────────

    def get_spread(self, user_id: int) -> SpreadType:
        raw = self._spreads.get(user_id, SpreadType.THREE_CARDS.value)
        try:
            return SpreadType(raw)
        except ValueError:
            return SpreadType.THREE_CARDS

    def set_spread(self, user_id: int, spread_type: SpreadType) -> None:
        self._spreads[user_id] = spread_type.value

    def has_user(self, user_id: int) -> bool:
        return user_id in self._spreads

    # ── Display name cache ────────────────────────────────────────────────────

    def get_name(self, user_id: int) -> str | None:
        """Return cached display name, or None if not yet resolved."""
        return self._names.get(user_id)

    def set_name(self, user_id: int, name: str) -> None:
        self._names[user_id] = name
