from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_tenant_id
from app.db import models
from app.db.base import get_db
from app.schemas import PrepRequest
from app.services.inbox import prep_generator

router = APIRouter(prefix="/prep", tags=["prep"])


@router.post("")
def generate_prep(
    req: PrepRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    company, role, job_desc = req.company, req.role, ""
    if req.job_id:
        job = (
            db.query(models.Job)
            .filter(models.Job.id == req.job_id, models.Job.tenant_id == tenant_id)
            .first()
        )
        if job:
            company = company or job.company
            role = role or job.title
            job_desc = job.description

    plan = prep_generator.generate(company, role, req.email_body, job_desc)
    row = models.InterviewPrep(tenant_id=tenant_id, application_id=req.application_id,
                               plan=plan.to_dict())
    db.add(row)
    db.commit()
    return {"prep_id": row.id, "plan": plan.to_dict()}


@router.get("")
def list_preps(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    rows = db.query(models.InterviewPrep).filter(models.InterviewPrep.tenant_id == tenant_id).all()
    return {"preps": [{"prep_id": r.id, "application_id": r.application_id, "plan": r.plan}
                      for r in rows]}
