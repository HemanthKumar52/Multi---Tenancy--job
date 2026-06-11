from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_tenant_id, get_profile_row
from app.db.base import get_db
from app.services.templates import finder
from app.services.templates.catalog import CATALOG

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("")
def list_templates() -> dict:
    return {"templates": CATALOG}


@router.get("/recommend/{profile_id}")
def recommend(
    profile_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    """Profile-aware ATS-safe template suggestions. Optional — format-preserving is the default."""
    row = get_profile_row(db, tenant_id, profile_id)
    return finder.recommend(row.data or {}, row.ats_report or {})
