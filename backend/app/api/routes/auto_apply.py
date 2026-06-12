"""Daily batch auto-apply API: save answers + a search policy, run the batch, review, send-all."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import current_tenant_id, get_profile_row, load_master_profile
from app.db import models
from app.db.base import get_db
from app.schemas import AnswerProfileRequest, SavedSearchRequest
from app.services.apply import auto_apply

router = APIRouter(prefix="/auto-apply", tags=["auto-apply"])


# ── Answer profile (saved once, reused for every application) ─────────────────
@router.post("/answers")
def save_answers(
    req: AnswerProfileRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    if req.profile_id:
        get_profile_row(db, tenant_id, req.profile_id)   # 404 unless the profile is this tenant's
    row = db.query(models.AnswerProfile).filter(models.AnswerProfile.tenant_id == tenant_id).first()
    if not row:
        row = models.AnswerProfile(tenant_id=tenant_id)
        db.add(row)
    row.profile_id = req.profile_id or row.profile_id
    row.identity = req.identity
    row.answers = req.answers
    row.meta = req.meta
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": row.id, "saved": True}


@router.get("/answers")
def get_answers(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    row = db.query(models.AnswerProfile).filter(models.AnswerProfile.tenant_id == tenant_id).first()
    if not row:
        return {"identity": {}, "answers": {}, "meta": {}}
    return {"id": row.id, "identity": row.identity, "answers": row.answers, "meta": row.meta}


# ── Saved search (the daily policy) ──────────────────────────────────────────
@router.post("/searches")
def create_search(
    req: SavedSearchRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    get_profile_row(db, tenant_id, req.profile_id)   # a search can't reference a foreign profile
    s = models.SavedSearch(
        tenant_id=tenant_id, profile_id=req.profile_id, name=req.name,
        source_specs=req.source_specs, daily_cap=req.daily_cap,
        vendor_allowlist=req.vendor_allowlist, review_mode=req.review_mode,
    )
    db.add(s)
    db.commit()
    return {"id": s.id, "name": s.name, "daily_cap": s.daily_cap}


@router.get("/searches")
def list_searches(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    rows = db.query(models.SavedSearch).filter(models.SavedSearch.tenant_id == tenant_id).all()
    return {"searches": [{"id": s.id, "name": s.name, "daily_cap": s.daily_cap,
                          "enabled": s.enabled, "review_mode": s.review_mode,
                          "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None}
                         for s in rows]}


@router.post("/searches/{search_id}/run")
def run_search(
    search_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    """Build today's batch: discover -> dedupe -> tailor the top N. (Daily cron calls this.)"""
    s = (db.query(models.SavedSearch)
         .filter(models.SavedSearch.id == search_id, models.SavedSearch.tenant_id == tenant_id)
         .first())
    if not s:
        raise HTTPException(404, "Saved search not found")
    profile, resume = load_master_profile(db, tenant_id, s.profile_id)
    return auto_apply.build_batch(db, tenant_id, s, profile, resume.path)


# ── Batch review + send-all ──────────────────────────────────────────────────
@router.get("/batches/{batch_id}")
def get_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    rows = (db.query(models.Application)
            .filter(models.Application.tenant_id == tenant_id,
                    models.Application.batch_id == batch_id).all())
    return {"batch_id": batch_id, "applications": [
        {"application_id": r.id, "job_id": r.job_id, "state": r.state,
         "match_score": r.match_score, "edit_set": r.edit_set,
         "tailored_doc_path": r.tailored_doc_path} for r in rows]}


@router.post("/batches/{batch_id}/send")
def send_batch(
    batch_id: str,
    confirm: bool = True,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    """One-click 'send all' for a reviewed batch (your batch consent)."""
    if not confirm:
        raise HTTPException(400, "Sending requires confirm=true")

    apps = (db.query(models.Application)
            .filter(models.Application.tenant_id == tenant_id,
                    models.Application.batch_id == batch_id).all())
    if not apps:
        raise HTTPException(404, "Batch not found")

    # Identity comes from the user's TRUTHFUL master profile (never free-form), same as /approve.
    profile, _ = load_master_profile(db, tenant_id, apps[0].profile_id)
    name_parts = profile.name.split()
    identity = {
        "first_name": name_parts[0] if name_parts else "",
        "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
        "email": profile.email, "phone": profile.phone,
    }
    ap = db.query(models.AnswerProfile).filter(models.AnswerProfile.tenant_id == tenant_id).first()
    answers = (ap.answers if ap else {}) or {}
    return auto_apply.send_batch(db, tenant_id, batch_id, identity, answers)
