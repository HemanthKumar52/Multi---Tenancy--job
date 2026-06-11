from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import current_tenant_id, get_profile_row
from app.config import settings
from app.db import models
from app.db.base import get_db
from app.services.resume import ats as ats_mod
from app.services.resume.parser import parse_resume

router = APIRouter(prefix="/profiles", tags=["profiles"])

_ALLOWED = {".docx", ".pdf"}


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED:
        raise HTTPException(400, f"Unsupported file type {suffix!r}; upload .docx or .pdf")

    dest = settings.uploads_path / f"{uuid.uuid4().hex}{suffix}"
    dest.write_bytes(await file.read())

    profile = parse_resume(dest)
    report = ats_mod.analyze(dest, profile)

    resume = models.Resume(
        tenant_id=tenant_id,
        filename=file.filename or dest.name,
        path=str(dest),
        source_format=profile.source_format,
    )
    db.add(resume)
    db.flush()

    profile_row = models.Profile(
        tenant_id=tenant_id,
        resume_id=resume.id,
        data=profile.to_dict(),
        ats_report=report.to_dict(),
    )
    db.add(profile_row)
    db.commit()

    warnings: list[str] = []
    if profile.source_format == "pdf":
        warnings.append(
            "PDF uploaded: parsing and tailoring work, but producing a tailored *file* requires "
            "converting to DOCX first (layout fidelity may vary). Upload DOCX for best results."
        )

    return {
        "profile_id": profile_row.id,
        "resume_id": resume.id,
        "source_format": profile.source_format,
        "profile": profile.to_dict(),
        "ats_report": report.to_dict(),
        "warnings": warnings,
    }


@router.get("/{profile_id}")
def get_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    row = get_profile_row(db, tenant_id, profile_id)
    return {"profile_id": row.id, "profile": row.data, "ats_report": row.ats_report}


@router.get("")
def list_profiles(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    rows = db.query(models.Profile).filter(models.Profile.tenant_id == tenant_id).all()
    return {
        "profiles": [
            {"profile_id": r.id, "name": (r.data or {}).get("name", ""),
             "ats_score": (r.ats_report or {}).get("score")}
            for r in rows
        ]
    }
