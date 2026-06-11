from __future__ import annotations

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_enabled": settings.llm_enabled,
        "database": "postgres" if settings.database_url else "sqlite",
        "env": settings.app_env,
    }
