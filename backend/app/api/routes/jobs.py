from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_tenant_id, get_job_row
from app.db import models
from app.db.base import get_db
from app.schemas import DiscoverRequest, ManualJobRequest
from app.services.discovery.aggregator import discover

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _store_job(db: Session, tenant_id: str, p: dict) -> models.Job:
    job = models.Job(
        tenant_id=tenant_id,
        source=p.get("source", "manual"),
        ats_vendor=p.get("ats_vendor", "external"),
        external_id=str(p.get("external_id", "")),
        company=p.get("company", ""),
        title=p.get("title", ""),
        location=p.get("location", ""),
        description=p.get("description", ""),
        url=p.get("url", ""),
        posted_at=p.get("posted_at"),
        skills=p.get("skills", []),
    )
    db.add(job)
    return job


@router.post("/discover")
def discover_jobs(
    req: DiscoverRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    postings = discover(req.source_specs)
    stored = [_store_job(db, tenant_id, p.to_dict()) for p in postings]
    db.commit()
    return {
        "count": len(stored),
        "jobs": [{"id": j.id, "company": j.company, "title": j.title,
                  "location": j.location, "ats_vendor": j.ats_vendor, "url": j.url} for j in stored],
    }


@router.post("")
def add_job(
    req: ManualJobRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    job = _store_job(db, tenant_id, req.model_dump() | {"source": "manual"})
    db.commit()
    return {"id": job.id, "title": job.title, "company": job.company}


@router.get("")
def list_jobs(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    rows = db.query(models.Job).filter(models.Job.tenant_id == tenant_id).all()
    return {"jobs": [{"id": j.id, "company": j.company, "title": j.title,
                      "location": j.location, "ats_vendor": j.ats_vendor,
                      "skills": j.skills, "url": j.url} for j in rows]}


@router.get("/{job_id}")
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    j = get_job_row(db, tenant_id, job_id)
    return {"id": j.id, "company": j.company, "title": j.title, "location": j.location,
            "description": j.description, "ats_vendor": j.ats_vendor, "skills": j.skills, "url": j.url}
