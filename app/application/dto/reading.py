from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities.tarot import SpreadType


@dataclass(frozen=True)
class PerformReadingCommand:
    """Input for the PerformReadingUseCase.

    All fields are plain Python primitives or domain enums — no messenger
    types (Update, Message, etc.) or HTTP request objects.
    """

    platform: str           # "telegram" | "web" | "web3"
    external_user_id: str   # tg_id as str, wallet address, OAuth sub, …
    user_display_name: str  # shown name for get_or_create; may be empty
    question: str           # raw user question text
    spread_type: SpreadType


@dataclass(frozen=True)
class ReadingResult:
    """Output of PerformReadingUseCase.execute — platform-agnostic payload.

    The presentation layer (Telegram handler, FastAPI endpoint, …) is
    responsible for formatting this into messenger-specific messages.
    """

    cards_summary: str        # human-readable comma-separated card list
    interpretation: str       # LLM-generated reading text
    image_url: str | None     # public S3/proxy URL; None if upload failed
    llm_status: str           # "success" | "guardrail_blocked" | …
    llm_tokens: int | None    # total tokens consumed; None if unavailable
    image_bytes: bytes | None = None  # raw PNG bytes for direct upload; avoids Telegram fetching S3
