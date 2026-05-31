"""PerformReadingUseCase — the core business scenario of the application."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.application.dto.reading import PerformReadingCommand, ReadingResult
from app.application.exceptions import InsufficientLimitsError
from app.application.security.prompt_guard import find_injection_phrase
from app.core.config import Settings
from app.domain.ports.image_renderer import IImageRenderer
from app.domain.ports.llm_port import ILLMProvider
from app.domain.ports.llm_usage_repo import ILLMUsageRepository
from app.domain.ports.reading_repo import IReadingRepository
from app.domain.ports.storage_port import IStoragePort, StoredObject
from app.domain.ports.unit_of_work import IUnitOfWork
from app.domain.ports.user_repo import IUserRepository
from app.domain.services.spread_factory import SpreadFactory

logger = logging.getLogger(__name__)


class InjectionBlockedError(Exception):
    """Raised when the user's question contains a prompt-injection attempt."""


class PerformReadingUseCase:
    """Orchestrates a full tarot reading from question to persisted result.

    Dependency graph (all injected, none imported concretely):

        IUserRepository ─────────────┐
        IReadingRepository ───────────┤
        ILLMUsageRepository ──────────┤─► execute() ──► ReadingResult
        ILLMProvider ────────────────┤
        IStoragePort ────────────────┤
        IImageRenderer ──────────────┤
        SpreadFactory ───────────────┘
        IUnitOfWork (for single commit)

    Transaction contract
    --------------------
    All DB writes (user, reading, llm_usage) happen inside a single
    ``try`` block.  A single ``await self._uow.commit()`` is called only
    on success.  Any exception triggers ``await self._uow.rollback()``
    before re-raising, so the outer session context manager always gets a
    clean connection back.

    External I/O ordering
    ---------------------
    LLM and S3 calls happen *before* the DB session is written to.  This
    means a timeout or network error never leaves a half-written transaction
    open — the DB block is only entered when all external calls have
    already returned.
    """

    def __init__(
        self,
        uow: IUnitOfWork,
        user_repo: IUserRepository,
        reading_repo: IReadingRepository,
        llm_usage_repo: ILLMUsageRepository,
        llm: ILLMProvider,
        storage: IStoragePort,
        image_renderer: IImageRenderer,
        spread_factory: SpreadFactory,
        settings: Settings,
    ) -> None:
        self._uow = uow
        self._user_repo = user_repo
        self._reading_repo = reading_repo
        self._llm_usage_repo = llm_usage_repo
        self._llm = llm
        self._storage = storage
        self._image_renderer = image_renderer
        self._spread_factory = spread_factory
        self._tz = ZoneInfo(settings.daily_card_timezone)

    async def execute(self, cmd: PerformReadingCommand) -> ReadingResult:
        """Run the full reading scenario.

        Args:
            cmd: Platform-agnostic reading command from any entrypoint.

        Returns:
            ReadingResult: Pure data DTO — no messenger types inside.

        Raises:
            InjectionBlockedError: When the question contains a blocked phrase.
            RuntimeError: When the LLM call fails (timeout, auth, network).
        """
        # ── 1. Input guard (pure, no I/O) ─────────────────────────────
        blocked = find_injection_phrase(cmd.question)
        if blocked:
            logger.warning("injection blocked platform=%s phrase=%r", cmd.platform, blocked)
            raise InjectionBlockedError(blocked)

        # ── 1b. Lazy reset + limit pre-check (fast fail before expensive I/O) ─
        # For existing users: reset daily_limit to 3 if it's a new MSK day,
        # then reject if both counters are still zero.
        # New users (None) pass through — get_or_create gives them limit=3.
        existing_user = await self._user_repo.get_by_platform_id(
            cmd.platform, cmd.external_user_id
        )
        if existing_user is not None:
            msk_today = datetime.now(self._tz).date()
            reset = await self._user_repo.maybe_reset_daily_limit(
                existing_user.id, msk_today
            )
            if reset:
                await self._uow.commit()
            elif existing_user.daily_limit <= 0 and existing_user.bonus_balance <= 0:
                raise InsufficientLimitsError()

        # ── 2. Domain: assemble spread (pure, no I/O) ─────────────────
        spread = self._spread_factory.build(cmd.spread_type)

        # ── 3. External I/O: LLM ──────────────────────────────────────
        # Failures propagate as RuntimeError — the caller decides the UX.
        llm_result = await self._llm.get_interpretation(
            question=cmd.question,
            cards=spread.cards,
            spread_type=spread.spread_type,
        )

        # ── 4. CPU-bound: render image ────────────────────────────────
        image_buf = self._image_renderer.render(spread)

        # ── 5. External I/O: S3 upload (non-fatal) ───────────────────
        # A failed upload is logged and gracefully degraded — the reading
        # is still saved and returned, just without an attached image.
        stored: StoredObject | None = None
        try:
            stored = await self._storage.save(image_buf, suffix=".png")
        except Exception:
            logger.warning(
                "image upload failed for platform=%s user=%s; reading saved without image",
                cmd.platform,
                cmd.external_user_id,
            )

        # ── 6. DB transaction: single commit ─────────────────────────
        # Repos have already been configured with the same session as uow.
        try:
            user, _ = await self._user_repo.get_or_create(
                platform=cmd.platform,
                external_id=cmd.external_user_id,
                display_name=cmd.user_display_name,
            )
            await self._user_repo.decrement_limits(user.id)
            await self._reading_repo.create(
                user_id=user.id,
                question=cmd.question,
                spread=spread,
                interpretation=llm_result.interpretation,
                image_url=stored.public_url if stored else None,
            )
            await self._llm_usage_repo.create_event(
                user_id=user.id,
                status=llm_result.status,
                total_tokens=llm_result.total_tokens,
                prompt_tokens=llm_result.prompt_tokens,
                completion_tokens=llm_result.completion_tokens,
            )
            await self._uow.commit()  # ← the only commit in this use case
        except Exception:
            await self._uow.rollback()
            raise

        # ── 7. Return platform-agnostic result ───────────────────────
        return ReadingResult(
            cards_summary=_format_cards_summary(spread.cards),
            interpretation=llm_result.interpretation,
            image_url=stored.public_url if stored else None,
            llm_status=llm_result.status,
            llm_tokens=llm_result.total_tokens,
            image_bytes=image_buf.getvalue(),
        )


def _format_cards_summary(cards: list) -> str:
    """Build human-readable comma-separated summary of drawn cards."""
    parts = []
    for card in cards:
        orientation = "перевернутая" if card.is_reversed else "прямая"
        label = card.position_name or f"Карта {card.position}"
        parts.append(f"{label}: {card.name} ({orientation})")
    return ", ".join(parts)
