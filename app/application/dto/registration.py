from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegistrationResult:
    """Output of RegisterUserUseCase.execute."""

    is_new_user: bool
    has_referrer: bool
    referrer_external_id: str | None  # platform-native id; None when no referrer
