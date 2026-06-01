from __future__ import annotations

from io import BytesIO
from typing import Protocol

from app.domain.entities.tarot import SpreadResult


class IImageRenderer(Protocol):
    """Abstract contract for tarot spread image generation.

    Keeping this as a synchronous protocol is intentional: image rendering
    is CPU-bound (PIL/Pillow), so use cases call it synchronously and offload
    to a thread pool when needed via ``asyncio.to_thread``.

    Swap Pillow for a remote rendering service or a stub that returns a blank
    image in tests — the use case and handlers never import Pillow directly.
    """

    def render(self, spread: SpreadResult) -> BytesIO:
        """Render ``spread`` as an in-memory PNG image stream."""
        ...
