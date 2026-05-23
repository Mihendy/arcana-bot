"""PillowImageRenderer — IImageRenderer adapter wrapping ImageService."""

from __future__ import annotations

from io import BytesIO

from app.domain.entities.tarot import SpreadResult, SpreadType
from app.services.image_service import ImageService


class PillowImageRenderer:
    """Delegates spread rendering to the Pillow-based ImageService.

    Domain ``TarotCard`` is structurally compatible with both
    ``TarotCardLike`` and ``SpreadCard`` — all required attributes
    (``slug``, ``is_reversed``, ``position``, …) are present on the
    dataclass, so no conversion is needed.
    """

    def __init__(self, image_service: ImageService) -> None:
        self._svc = image_service

    def render(self, spread: SpreadResult) -> BytesIO:
        """Render spread image.  Pentagram uses a dedicated 1600×1600 layout."""
        if spread.spread_type == SpreadType.PENTAGRAM:
            return self._svc.create_pentagram_image(spread.cards)
        return self._svc.create_spread_image(spread.cards)