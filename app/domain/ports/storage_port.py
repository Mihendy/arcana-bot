from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    """Descriptor for an object persisted in storage."""

    object_key: str
    public_url: str


class IStoragePort(Protocol):
    """Abstract contract for binary object storage (S3, GCS, local disk, etc.).

    Implementations are responsible for making sync SDK calls async-safe
    (e.g. via ``asyncio.to_thread`` for boto3).
    """

    async def save(self, data: BytesIO, suffix: str = ".png") -> StoredObject:
        """Persist binary payload and return its storage descriptor."""
        ...

    async def get_bytes(self, object_key: str) -> tuple[bytes, str]:
        """Load raw bytes and MIME type for a stored object.

        Raises:
            FileNotFoundError: If the object does not exist.
        """
        ...