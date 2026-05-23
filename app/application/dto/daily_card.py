from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DailyCardResult:
    """Output of GetDailyCardUseCase.execute — pure data, no Telegram URLs.

    The presentation layer builds captions, share links, Mini App URLs and
    keyboards from these fields; none of that belongs in the use case.
    """

    card_name: str        # e.g. "The Fool"
    card_slug: str        # e.g. "the-fool" — for i18n or asset lookup
    interpretation: str   # short LLM prediction (1-2 sentences)
    image_url: str        # public S3/proxy URL of the rendered card image
    image_bytes: bytes | None = None  # raw PNG bytes for direct upload; avoids Telegram fetching S3
