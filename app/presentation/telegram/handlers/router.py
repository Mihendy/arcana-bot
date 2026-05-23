"""Handler registry — assembles all PTB BaseHandler instances."""

from __future__ import annotations

from telegram.ext import BaseHandler

from app.presentation.telegram.handlers.admin import get_admin_handlers
from app.presentation.telegram.handlers.payment import get_payment_handlers
from app.presentation.telegram.handlers.profile import get_profile_handlers
from app.presentation.telegram.handlers.start import get_start_handlers


def get_handlers() -> list[BaseHandler]:
    """Return all handlers in priority order.

    - Admin commands first (avoid being swallowed by catch-all text handler).
    - Payment handlers before profile/start: PreCheckoutQuery and
      SuccessfulPayment are structural PTB handlers that must register early.
    - Profile handlers before start so "👤 Профиль" text is matched before
      the catch-all question handler.
    """
    return [
        *get_admin_handlers(),
        *get_payment_handlers(),
        *get_profile_handlers(),
        *get_start_handlers(),
    ]
