"""Image generation utilities for tarot spreads."""

from __future__ import annotations

from io import BytesIO
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.services.tarot_data import tarot_data_service

CANVAS_SIZE = (1200, 800)
CARD_SIZE = (320, 560)
CARD_GAP = 40
WATERMARK_TEXT = "@arcana_r_bot"
WATERMARK_MARGIN = 42
WATERMARK_FONT_SIZE = 54
BACKGROUND_COLOR = (20, 17, 35)
WATERMARK_COLOR = (220, 220, 220, 180)
WATERMARK_SHADOW_COLOR = (0, 0, 0, 130)


class TarotCardLike(Protocol):
    """Minimal card interface required for rendering."""

    slug: str
    is_reversed: bool


class ImageService:
    """Creates tarot spread images from card assets."""

    def create_spread_image(self, cards: list[TarotCardLike]) -> BytesIO:
        """Render 3-card spread image and return PNG bytes."""
        if len(cards) != 3:
            raise ValueError("create_spread_image expects exactly 3 cards.")

        canvas = Image.new("RGBA", CANVAS_SIZE, BACKGROUND_COLOR)
        self._paste_cards(canvas, cards)
        self._draw_watermark(canvas)

        output = BytesIO()
        canvas.convert("RGB").save(output, format="PNG")
        output.seek(0)
        return output

    def _paste_cards(self, canvas: Image.Image, cards: list[TarotCardLike]) -> None:
        total_width = CARD_SIZE[0] * 3 + CARD_GAP * 2
        start_x = (canvas.width - total_width) // 2
        start_y = (canvas.height - CARD_SIZE[1]) // 2

        for idx, card in enumerate(cards):
            card_img = self._load_card_image(card.slug)
            if card.is_reversed:
                card_img = card_img.rotate(180)
            x = start_x + idx * (CARD_SIZE[0] + CARD_GAP)
            canvas.paste(card_img, (x, start_y))

    def _load_card_image(self, slug: str) -> Image.Image:
        path = tarot_data_service.get_card_asset_path(slug)
        with Image.open(path) as image:
            return image.convert("RGB").resize(CARD_SIZE, Image.Resampling.LANCZOS)

    def _draw_watermark(self, canvas: Image.Image) -> None:
        draw = ImageDraw.Draw(canvas, "RGBA")
        font = self._load_font()
        text_bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]

        x = (canvas.width - text_w) // 2
        y = canvas.height - text_h - WATERMARK_MARGIN

        # Small shadow for better readability on bright cards.
        draw.text((x + 2, y + 2), WATERMARK_TEXT, font=font, fill=WATERMARK_SHADOW_COLOR)
        draw.text((x, y), WATERMARK_TEXT, font=font, fill=WATERMARK_COLOR)

    def _load_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        if settings.fonts_assets_path.exists():
            for ext in ("*.ttf", "*.otf"):
                fonts = sorted(settings.fonts_assets_path.glob(ext))
                if fonts:
                    return ImageFont.truetype(str(fonts[0]), WATERMARK_FONT_SIZE)
        return ImageFont.load_default()


image_service = ImageService()
