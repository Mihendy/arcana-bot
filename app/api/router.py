"""API router definitions."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
