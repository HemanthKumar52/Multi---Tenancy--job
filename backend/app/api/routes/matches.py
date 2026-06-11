from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_tenant_id, get_job_row, load_master_profile
from app.db import models
from app.db.base import get_db
from app.schemas import MatchRequest
from app.services.matching.matcher import match

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("")
def match_one(
    req: MatchRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    profile, _ = load_master_profile(db, tenant_id, req.profile_id)
    job = get_job_row(db, tenant_id, req.job_id)
    result = match(profile, job.description, job.title)
    return {"job_id": job.id, "title": job.title, "company": job.company, **result.to_dict()}


@router.get("/ranked/{profile_id}")
def ranked_for_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    """Score the profile against every stored job, best first."""
    profile, _ = load_master_profile(db, tenant_id, profile_id)
    jobs = db.query(models.Job).filter(models.Job.tenant_id == tenant_id).all()
    scored = []
    for job in jobs:
        r = match(profile, job.description, job.title)
        scored.append({"job_id": job.id, "title": job.title, "company": job.company,
                       "ats_vendor": job.ats_vendor, **r.to_dict()})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"matches": scored}
