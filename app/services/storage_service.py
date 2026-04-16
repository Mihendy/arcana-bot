"""Storage utilities for generated files."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from app.core.config import settings


class StorageService:
    """Simple local storage helper for generated artifacts."""

    def save_bytesio_temp(self, payload: BytesIO, suffix: str = ".png") -> Path:
        """Save BytesIO to output directory with UUID filename."""
        settings.output_dir_path.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4().hex}{suffix}"
        target = settings.output_dir_path / filename
        target.write_bytes(payload.getvalue())
        return target


storage_service = StorageService()
