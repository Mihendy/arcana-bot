from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from urllib.parse import quote, urlparse
from uuid import uuid4

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from app.domain.ports.storage_port import StoredObject

logger = logging.getLogger(__name__)


class S3StorageAdapter:
    """Implements IStoragePort using a boto3 S3-compatible client.

    Memory safety: ``save`` reads the input stream to plain ``bytes`` and
    discards the BytesIO reference before returning.  Only the public URL
    string is propagated back to callers, preventing large image buffers
    from living longer than the upload operation.

    Thread safety: boto3 is synchronous; all blocking calls are delegated
    to ``asyncio.to_thread`` so the event loop is never stalled.
    """

    def __init__(
        self,
        client: object,
        bucket: str,
        endpoint_url: str,
        use_ssl: bool,
        public_base_url: str,
        api_proxy_base_url: str,
    ) -> None:
        self._client = client
        self._bucket = bucket
        self._endpoint_url = endpoint_url.rstrip("/")
        self._use_ssl = use_ssl
        self._public_base_url = public_base_url.strip()
        self._api_proxy_base_url = api_proxy_base_url.rstrip("/")

    # ------------------------------------------------------------------
    # IStoragePort implementation
    # ------------------------------------------------------------------

    async def save(self, data: BytesIO, suffix: str = ".png") -> StoredObject:
        """Upload binary payload to S3 and return only the storage descriptor.

        The ``data`` stream is consumed here.  No BytesIO is kept in memory
        after the upload completes — only the ``object_key`` string and the
        resolved public URL are retained.
        """
        object_key = f"readings/{uuid4().hex}{suffix}"
        raw = data.read()  # consume stream; reference to large buffer released below
        content_type = _guess_content_type(suffix)

        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=object_key,
            Body=raw,
            ContentType=content_type,
        )
        del raw  # explicit: large buffer is no longer needed

        public_url = self._build_public_url(object_key)
        logger.debug("s3_upload key=%s url=%s", object_key, public_url)
        return StoredObject(object_key=object_key, public_url=public_url)

    async def get_bytes(self, object_key: str) -> tuple[bytes, str]:
        """Load raw bytes and MIME type for a stored object."""
        try:
            response = await asyncio.to_thread(
                self._client.get_object,
                Bucket=self._bucket,
                Key=object_key,
            )
        except ClientError as exc:
            raise FileNotFoundError(f"Media object not found: {object_key}") from exc

        body: bytes = response["Body"].read()
        content_type: str = response.get("ContentType") or "application/octet-stream"
        return body, content_type

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    async def ensure_bucket_exists(self) -> None:
        """Create the S3 bucket if it does not yet exist."""
        try:
            await asyncio.to_thread(self._client.head_bucket, Bucket=self._bucket)
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code not in {"404", "NoSuchBucket", "NotFound"}:
                raise RuntimeError(f"S3 init failed: {exc}") from exc
            create_kwargs: dict[str, object] = {"Bucket": self._bucket}
            region = getattr(self, "_region", None)
            if region and region != "us-east-1":
                create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
            try:
                await asyncio.to_thread(self._client.create_bucket, **create_kwargs)
            except ClientError as create_exc:
                raise RuntimeError(f"S3 bucket creation failed: {create_exc}") from create_exc

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls, settings: object) -> S3StorageAdapter:
        """Construct adapter from application settings."""
        endpoint_url: str = getattr(settings, "s3_endpoint_url", "") or ""
        if endpoint_url and "://" not in endpoint_url:
            scheme = "https" if getattr(settings, "s3_use_ssl", False) else "http"
            endpoint_url = f"{scheme}://{endpoint_url}"
        endpoint_url = endpoint_url.rstrip("/")

        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=getattr(settings, "s3_access_key", None),
            aws_secret_access_key=getattr(settings, "s3_secret_key", None),
            region_name=getattr(settings, "s3_region", "us-east-1"),
        )
        adapter = cls(
            client=client,
            bucket=getattr(settings, "s3_bucket", "arcana-media"),
            endpoint_url=endpoint_url,
            use_ssl=getattr(settings, "s3_use_ssl", False),
            public_base_url=getattr(settings, "s3_public_base_url", ""),
            api_proxy_base_url=getattr(settings, "api_public_base_url", ""),
        )
        adapter._region = getattr(settings, "s3_region", "us-east-1")
        return adapter

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_public_url(self, object_key: str) -> str:
        """Resolve public URL for an object key."""
        if self._is_non_local_endpoint():
            return self._build_s3_url(object_key)
        return f"{self._api_proxy_base_url}/public/media/{quote(object_key, safe='/')}"

    def _is_non_local_endpoint(self) -> bool:
        if not self._endpoint_url:
            return False
        host = (urlparse(self._endpoint_url).hostname or "").lower()
        return host not in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}

    def _build_s3_url(self, object_key: str) -> str:
        if self._public_base_url:
            return f"{self._public_base_url}/{quote(object_key, safe='/')}"
        parsed = urlparse(self._endpoint_url)
        scheme = parsed.scheme or ("https" if self._use_ssl else "http")
        host = parsed.hostname or ""
        bucket_host = host if host.startswith(f"{self._bucket}.") else f"{self._bucket}.{host}"
        port = f":{parsed.port}" if parsed.port else ""
        return f"{scheme}://{bucket_host}{port}/{quote(object_key, safe='/')}"


def _guess_content_type(suffix: str) -> str:
    lowered = suffix.lower()
    if lowered in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if lowered == ".webp":
        return "image/webp"
    return "image/png"
