"""Storage utilities for generated files."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from app.core.config import settings


class StorageService:
    """Simple local storage helper for generated artifacts."""

    def save_bytesio_temp(self, payload: BytesIO, suffix: str = ".png") -> Path:
        """Save in-memory payload to output directory with UUID filename.

        Args:
            payload: Binary stream with file contents.
            suffix: File extension to use for generated file name.

        Returns:
            Path: Absolute path to saved file.
        """
        settings.output_dir_path.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4().hex}{suffix}"
        target = settings.output_dir_path / filename
        target.write_bytes(payload.getvalue())
        return target

    def save_many_bytesio_temp(self, payloads: list[BytesIO], suffix: str = ".png") -> list[Path]:
        """Persist multiple in-memory payloads and return their paths.

        Args:
            payloads: List of binary streams with file contents.
            suffix: File extension to use for generated file names.

        Returns:
            list[Path]: Absolute paths to saved files.
        """
        return [self.save_bytesio_temp(payload, suffix=suffix) for payload in payloads]


storage_service = StorageService()
