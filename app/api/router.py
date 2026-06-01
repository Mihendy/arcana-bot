"""API router definitions."""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.ports.storage_port import IStoragePort

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck(request: Request) -> dict[str, str]:
    """Return API and database health status."""
    try:
        async with request.app.state.container() as di:
            session: AsyncSession = await di.get(AsyncSession)
            await session.execute(text("SELECT 1"))
        is_db_healthy = True
    except Exception:
        is_db_healthy = False

    if not is_db_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        )
    return {"status": "ok", "env": settings.app_env, "db": "ok"}


@router.get("/public/media/{object_key:path}")
async def get_public_media(request: Request, object_key: str) -> Response:
    """Serve media files from S3/MinIO via the public proxy endpoint.

    Args:
        request: FastAPI request — used to access ``app.state.storage``.
        object_key: Object key inside the configured S3 bucket.

    Returns:
        Response: Binary media payload with correct Content-Type.

    Raises:
        HTTPException: 404 when the object does not exist in storage.
    """
    storage: IStoragePort = request.app.state.storage
    try:
        data, content_type = await storage.get_bytes(object_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media not found."
        ) from exc
    return Response(content=data, media_type=content_type)
