"""Image generation utilities for tarot spreads."""

from __future__ import annotations

import math
from io import BytesIO
from collections.abc import Sequence
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.infrastructure.assets.tarot_data import tarot_data_service

CARD_SIZE = (320, 560)
CARD_GAP = 40
CANVAS_MARGIN = 80
PENTAGRAM_FULL_CANVAS_SIZE = (1600, 1600)
PENTAGRAM_CARD_SIZE = (256, 448)
PENTAGRAM_POSITION_CENTERS: dict[int, tuple[int, int]] = {
    1: (800, 260),
    2: (1040, 1320),
    3: (420, 760),
    4: (1180, 760),
    5: (560, 1320),
}
WATERMARK_TEXT = "@arcana_r_bot"
WATERMARK_MARGIN = 42
BACKGROUND_COLOR = (20, 17, 35)
WATERMARK_COLOR = (220, 220, 220, 180)
WATERMARK_SHADOW_COLOR = (0, 0, 0, 130)
CARD_CORNER_RADIUS = 18


class TarotCardLike(Protocol):
    """Minimal card interface required for rendering."""

    slug: str
    is_reversed: bool
    position: int


class ImageService:
    """Creates tarot spread images from card assets."""

    def create_spread_image(self, cards: Sequence[TarotCardLike]) -> BytesIO:
        """Render spread image with dynamic canvas based on card count.

        Args:
            cards: One, three, or five cards for linear layout.

        Returns:
            BytesIO: In-memory PNG image stream ready for Telegram upload.

        Raises:
            ValueError: If card count is unsupported.
            FileNotFoundError: If one of card images is missing.
        """
        count = len(cards)
        if count not in {1, 3, 5}:
            raise ValueError("create_spread_image supports only 1, 3, or 5 cards.")

        canvas = self._create_canvas(count)
        self._paste_cards(canvas, cards, count)
        self._draw_watermark(canvas, count)

        output = BytesIO()
        canvas.convert("RGB").save(output, format="PNG")
        output.seek(0)
        return output

    def create_pentagram_image(self, cards: Sequence[TarotCardLike]) -> BytesIO:
        """Create single 1600x1600 image for pentagram spread.

        Args:
            cards: Five cards of pentagram spread.

        Returns:
            BytesIO: Rendered pentagram image as PNG bytes.

        Raises:
            ValueError: If card count is not five.
        """
        if len(cards) != 5:
            raise ValueError("create_pentagram_image expects exactly 5 cards.")
        cards_by_position = {card.position: card for card in cards}
        full_canvas = Image.new("RGBA", PENTAGRAM_FULL_CANVAS_SIZE, BACKGROUND_COLOR)
        self._paste_pentagram_cards(full_canvas, cards_by_position)
        self._draw_watermark(full_canvas, count=5, centered=True)
        return self._to_png_bytes(full_canvas)

    def _create_canvas(self, count: int) -> Image.Image:
        """Create background canvas for requested cards count."""
        if count == 1:
            width = CARD_SIZE[0] + CANVAS_MARGIN * 2
            height = CARD_SIZE[1] + CANVAS_MARGIN * 2
        else:
            width = CARD_SIZE[0] * count + CARD_GAP * (count - 1) + CANVAS_MARGIN * 2
            height = CARD_SIZE[1] + CANVAS_MARGIN * 2
        return Image.new("RGBA", (width, height), BACKGROUND_COLOR)

    def _paste_cards(self, canvas: Image.Image, cards: Sequence[TarotCardLike], count: int) -> None:
        """Paste resized card images onto the canvas."""
        total_width = CARD_SIZE[0] * count + CARD_GAP * (count - 1)
        start_x = (canvas.width - total_width) // 2
        start_y = (canvas.height - CARD_SIZE[1]) // 2

        for idx, card in enumerate(cards):
            card_img = self._load_card_image(card.slug, CARD_SIZE)
            if card.is_reversed:
                card_img = card_img.rotate(180)
            x = start_x + idx * (CARD_SIZE[0] + CARD_GAP)
            canvas.paste(card_img, (x, start_y), card_img)

    def _paste_pentagram_cards(self, canvas: Image.Image, cards_by_position: dict[int, TarotCardLike]) -> None:
        """Paste pentagram cards at fixed position centers."""
        for position, (center_x, center_y) in PENTAGRAM_POSITION_CENTERS.items():
            card = cards_by_position.get(position)
            if card is None:
                continue

            card_img = self._load_card_image(card.slug, PENTAGRAM_CARD_SIZE)
            if card.is_reversed:
                card_img = card_img.rotate(180)
            x = center_x - PENTAGRAM_CARD_SIZE[0] // 2
            y = center_y - PENTAGRAM_CARD_SIZE[1] // 2
            canvas.paste(card_img, (x, y), card_img)

    def _load_card_image(self, slug: str, size: tuple[int, int]) -> Image.Image:
        """Load and resize one card image by slug."""
        path = tarot_data_service.get_card_asset_path(slug)
        with Image.open(path) as image:
            resized = image.convert("RGBA").resize(size, Image.Resampling.LANCZOS)
            return self._apply_rounded_corners(resized, CARD_CORNER_RADIUS)

    def _draw_watermark(self, canvas: Image.Image, count: int, centered: bool = False) -> None:
        """Draw brand watermark on the generated canvas."""
        draw = ImageDraw.Draw(canvas, "RGBA")
        font = self._load_font(canvas.width, count)
        text_bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]

        x = (canvas.width - text_w) // 2
        y = (canvas.height - text_h) // 2 if centered else canvas.height - text_h - WATERMARK_MARGIN

        draw.text((x + 2, y + 2), WATERMARK_TEXT, font=font, fill=WATERMARK_SHADOW_COLOR)
        draw.text((x, y), WATERMARK_TEXT, font=font, fill=WATERMARK_COLOR)

    def _load_font(self, canvas_width: int, count: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Load first available custom font or fallback default font."""
        dynamic_size = max(24, min(64, math.floor(canvas_width / 28)))
        if count == 1:
            dynamic_size = max(24, dynamic_size - 8)
        if settings.fonts_assets_path.exists():
            for ext in ("*.ttf", "*.otf"):
                fonts = sorted(settings.fonts_assets_path.glob(ext))
                if fonts:
                    return ImageFont.truetype(str(fonts[0]), dynamic_size)
        return ImageFont.load_default()

    def _to_png_bytes(self, image: Image.Image) -> BytesIO:
        """Serialize PIL image to in-memory PNG bytes."""
        output = BytesIO()
        image.convert("RGB").save(output, format="PNG")
        output.seek(0)
        return output

    def _apply_rounded_corners(self, image: Image.Image, radius: int) -> Image.Image:
        """Apply rounded corners mask to a card image."""
        mask = Image.new("L", image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, image.width, image.height), radius=radius, fill=255)
        rounded = image.copy()
        rounded.putalpha(mask)
        return rounded


image_service = ImageService()
