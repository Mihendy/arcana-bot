"""API router definitions."""

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.core.db import check_db_health

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    """Return API and database health status.

    Returns:
        dict[str, str]: Service status payload for monitoring checks.

    Raises:
        HTTPException: If database connectivity check fails.
    """
    is_db_healthy = await check_db_health()
    if not is_db_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        )
    return {"status": "ok", "env": settings.app_env, "db": "ok"}
