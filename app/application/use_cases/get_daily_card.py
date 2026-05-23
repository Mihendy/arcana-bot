"""GetDailyCardUseCase — generate the daily card payload for broadcast."""

from __future__ import annotations

import logging

from app.application.dto.daily_card import DailyCardResult
from app.domain.entities.tarot import SpreadType
from app.domain.ports.image_renderer import IImageRenderer
from app.domain.ports.llm_port import ILLMProvider
from app.domain.ports.storage_port import IStoragePort
from app.domain.services.spread_factory import SpreadFactory

logger = logging.getLogger(__name__)


class GetDailyCardUseCase:
    """Generates the card-of-the-day payload.

    Deliberately stateless with respect to the database — it draws a card,
    generates a prediction, renders an image, uploads it, and returns pure
    data.  No Telegram-specific URLs (Mini App share links, widget URLs)
    are constructed here; that is the presentation layer's responsibility.

    The same result can be formatted differently for Telegram Stories, a
    web widget, a push notification, or any other delivery channel.
    """

    def __init__(
        self,
        llm: ILLMProvider,
        storage: IStoragePort,
        image_renderer: IImageRenderer,
        spread_factory: SpreadFactory,
    ) -> None:
        self._llm = llm
        self._storage = storage
        self._image_renderer = image_renderer
        self._spread_factory = spread_factory

    async def execute(self) -> DailyCardResult:
        """Draw one card, get a prediction, render and upload its image.

        Returns:
            DailyCardResult: Pure data DTO with card info, prediction text,
                and a public image URL.

        Raises:
            RuntimeError: If the LLM call or S3 upload fails.
        """
        # Draw a single non-reversed card (reversed makes no sense for
        # an inspirational daily card).
        spread = self._spread_factory.build(
            SpreadType.ONE_CARD, allow_reversed=False
        )
        card = spread.cards[0]

        logger.info("daily_card drawing card=%s", card.name)

        # LLM prediction (let errors propagate — caller handles retry)
        llm_result = await self._llm.get_daily_card_prediction(card=card)

        # Render + upload (fatal here — a daily card without an image
        # is not useful for the broadcast use case)
        image_buf = self._image_renderer.render(spread)
        stored = await self._storage.save(image_buf, suffix=".png")

        logger.info("daily_card card=%s image_url=%s", card.name, stored.public_url)

        return DailyCardResult(
            card_name=card.name,
            card_slug=card.slug,
            interpretation=llm_result.interpretation,
            image_url=stored.public_url,
            image_bytes=image_buf.getvalue(),
        )
