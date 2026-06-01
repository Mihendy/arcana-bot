"""Application-layer business exceptions."""

from __future__ import annotations


class InsufficientLimitsError(Exception):
    """Raised when a user has exhausted both daily_limit and bonus_balance."""


class InjectionBlockedError(Exception):
    """Raised when the user's question contains a prompt-injection attempt."""
