from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_tenant_id, get_job_row, load_master_profile
from app.db.base import get_db
from app.schemas import TailorRequest
from app.services.matching.matcher import match
from app.services.tailoring import tailor

router = APIRouter(prefix="/tailor", tags=["tailor"])


@router.post("/preview")
def preview(
    req: TailorRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    """Compute the tailoring diff WITHOUT writing a file. The user reviews this before applying."""
    profile, resume = load_master_profile(db, tenant_id, req.profile_id)
    job = get_job_row(db, tenant_id, req.job_id)

    edit_set = tailor.generate_edit_set(profile, job.description, job.title)
    m = match(profile, job.description, job.title)

    diff = []
    for e in edit_set.edits:
        unit = profile.unit_by_id(e.unit_id)
        diff.append({
            "unit_id": e.unit_id,
            "section": unit.section.value if unit else None,
            "role": unit.role.value if unit else None,
            "original": e.original_text,
            "new": e.new_text,
            "reason": e.reason,
            "tier": e.tier,
        })

    return {
        "profile_id": req.profile_id,
        "job_id": req.job_id,
        "source_format": resume.source_format,
        "match": m.to_dict(),
        "edits": diff,
        "edit_count": len(diff),
        "truthful": True,  # every edit already passed the truthfulness guard
        "note": (
            "Edits are applied in-place into your original DOCX layout — no new template is "
            "created. Approve to render the tailored file and queue the application."
        ),
    }
