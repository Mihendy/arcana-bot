from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdminStatsResult:
    """Aggregated analytics payload for admin reporting."""

    total_users: int
    readings_today: int
    readings_this_month: int
    llm_success_calls: int
    llm_total_tokens: int
