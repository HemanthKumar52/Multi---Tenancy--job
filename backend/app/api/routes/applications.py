from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import current_tenant_id, get_job_row, load_master_profile
from app.config import settings
from app.db import models
from app.db.base import get_db
from app.schemas import ApproveRequest, PrepareRequest
from app.services.apply import orchestrator
from app.services.apply.orchestrator import ApplicationDraft, ApplicationState
from app.services.matching.matcher import MatchResult
from app.services.notify import notifier
from app.services.resume.models import Edit, EditSet

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("/prepare")
def prepare(
    req: PrepareRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    """Match -> tailor -> render the tailored doc. Stops at PENDING_APPROVAL (never auto-submits)."""
    profile, resume = load_master_profile(db, tenant_id, req.profile_id)
    job = get_job_row(db, tenant_id, req.job_id)

    # Dedupe: one application per (tenant, profile, job). A SKIPPED/FAILED prior attempt may be
    # re-tried, but an active/submitted one must not be duplicated (never spam a company).
    _terminal = {ApplicationState.SKIPPED.value, ApplicationState.FAILED.value,
                 ApplicationState.BLOCKED_HOST.value}
    existing = (
        db.query(models.Application)
        .filter(models.Application.tenant_id == tenant_id,
                models.Application.profile_id == req.profile_id,
                models.Application.job_id == req.job_id,
                models.Application.state.notin_(_terminal))
        .first()
    )
    if existing:
        raise HTTPException(409, f"An application for this job already exists ({existing.state}).")

    draft = orchestrator.prepare(
        profile,
        job_title=job.title,
        job_company=job.company,
        job_description=job.description,
        job_url=job.url,
        ats_vendor=job.ats_vendor,
        source_doc_path=resume.path,
    )

    app_row = models.Application(
        tenant_id=tenant_id,
        profile_id=req.profile_id,
        job_id=req.job_id,
        state=draft.state.value,
        match_score=draft.match.score,
        edit_set=draft.edit_set.to_dict(),
        ats_report=draft.ats_report,
        tailored_doc_path=draft.tailored_doc_path,
        notes=draft.notes,
    )
    db.add(app_row)
    db.commit()
    return {"application_id": app_row.id, **draft.to_dict()}


@router.post("/{application_id}/approve")
def approve(
    application_id: str,
    req: ApproveRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    """Explicit human approval -> drive the vendor apply flow. This is the consent record."""
    app_row = (
        db.query(models.Application)
        .filter(models.Application.id == application_id, models.Application.tenant_id == tenant_id)
        .first()
    )
    if not app_row:
        raise HTTPException(404, "Application not found")
    if not req.confirm:
        raise HTTPException(400, "Approval requires confirm=true")
    # Idempotency: only a pending application may be approved — never re-submit an already
    # submitted/in-flight/terminal one.
    if app_row.state != ApplicationState.PENDING_APPROVAL.value:
        raise HTTPException(409, f"Application is '{app_row.state}', not pending approval.")

    job = get_job_row(db, tenant_id, app_row.job_id)
    approved_at = datetime.now(timezone.utc)
    app_row.approved_at = approved_at

    # Identity comes from the user's own master profile (truthful — never fabricated).
    profile, _ = load_master_profile(db, tenant_id, app_row.profile_id)
    name_parts = profile.name.split()
    identity = {
        "first_name": name_parts[0] if name_parts else "",
        "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
        "email": profile.email,
        "phone": profile.phone,
    }

    # Rebuild a lightweight draft to submit.
    draft = ApplicationDraft(
        job_title=job.title,
        job_company=job.company,
        job_url=job.url,
        ats_vendor=job.ats_vendor,
        match=MatchResult(score=app_row.match_score),
        edit_set=EditSet(edits=[Edit(**e) for e in app_row.edit_set.get("edits", [])]),
        ats_report=app_row.ats_report,
        tailored_doc_path=app_row.tailored_doc_path,
        notes=list(app_row.notes or []),
        state=ApplicationState.PENDING_APPROVAL,
    )

    draft = orchestrator.approve_and_submit(draft, identity=identity, answers=req.answers)

    app_row.state = draft.state.value
    app_row.notes = draft.notes
    if draft.state == ApplicationState.SUBMITTED:
        app_row.submitted_at = datetime.now(timezone.utc)

    # Persist an audit/consent record. Store answer *labels* only (not values) + a resume hash;
    # never raw resume bytes or sensitive answer values.
    app_row.audit = {
        **(draft.audit or {}),
        "approved_at": approved_at.isoformat(),
        "user_agent": settings.user_agent,
        "company": job.company,
        "role": job.title,
        "ats_vendor": job.ats_vendor,
        "apply_url": job.url,
        "answered_question_labels": sorted((req.answers or {}).keys()),
        "consented_via": "approve route, confirm=true",
    }

    note = "; ".join(n for n in draft.notes if n) or draft.state.value
    db.add(models.Notification(
        tenant_id=tenant_id,
        title=f"Application {draft.state.value}: {job.title} @ {job.company}",
        body=note,
    ))
    notifier.notify(None, f"Application {draft.state.value}", note)
    db.commit()
    return {"application_id": app_row.id, "state": app_row.state, "notes": app_row.notes}


@router.post("/{application_id}/skip")
def skip(
    application_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    app_row = (
        db.query(models.Application)
        .filter(models.Application.id == application_id, models.Application.tenant_id == tenant_id)
        .first()
    )
    if not app_row:
        raise HTTPException(404, "Application not found")
    app_row.state = ApplicationState.SKIPPED.value
    db.commit()
    return {"application_id": app_row.id, "state": app_row.state}


@router.get("")
def list_applications(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    rows = (
        db.query(models.Application)
        .filter(models.Application.tenant_id == tenant_id)
        .order_by(models.Application.created_at.desc())
        .all()
    )
    return {"applications": [{
        "application_id": r.id, "job_id": r.job_id, "profile_id": r.profile_id,
        "state": r.state, "match_score": r.match_score,
        "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
    } for r in rows]}


@router.get("/{application_id}")
def get_application(
    application_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    r = (
        db.query(models.Application)
        .filter(models.Application.id == application_id, models.Application.tenant_id == tenant_id)
        .first()
    )
    if not r:
        raise HTTPException(404, "Application not found")
    return {
        "application_id": r.id, "job_id": r.job_id, "profile_id": r.profile_id, "state": r.state,
        "match_score": r.match_score, "edit_set": r.edit_set, "ats_report": r.ats_report,
        "tailored_doc_path": r.tailored_doc_path, "notes": r.notes, "audit": r.audit,
        "approved_at": r.approved_at.isoformat() if r.approved_at else None,
        "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
    }


@router.get("/{application_id}/document")
def download_document(
    application_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
):
    r = (
        db.query(models.Application)
        .filter(models.Application.id == application_id, models.Application.tenant_id == tenant_id)
        .first()
    )
    if not r or not r.tailored_doc_path or not Path(r.tailored_doc_path).exists():
        raise HTTPException(404, "Tailored document not available")
    return FileResponse(
        r.tailored_doc_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=Path(r.tailored_doc_path).name,
    )
