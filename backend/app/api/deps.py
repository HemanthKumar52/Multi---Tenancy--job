"""Request dependencies: tenancy resolution + profile reconstruction.

Tenancy is resolved from the ``X-Tenant-Id`` header (dev defaults to a seeded tenant). For
operations that need the live unit/location map (tailoring, apply writeback), we re-parse the
stored resume file — the file is the single source of truth, so paragraph ordinals stay valid.
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import decode_access_token
from app.db import models
from app.db.base import get_db
from app.services.resume.models import MasterProfile
from app.services.resume.parser import parse_resume

DEV_TENANT_ID = "devtenant"


def _claims_from_header(authorization: str | None) -> dict | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        return decode_access_token(token)
    except Exception as exc:  # invalid / expired
        raise HTTPException(401, "Invalid or expired token") from exc


def current_tenant_id(
    authorization: str | None = Header(default=None),
    x_tenant_id: str = Header(default=DEV_TENANT_ID),
) -> str:
    """Resolve tenant from a JWT when present; otherwise dev fallback (unless auth is required)."""
    claims = _claims_from_header(authorization)
    if claims:
        return claims["tid"]
    # The unauthenticated X-Tenant-Id fallback is a DEV-ONLY convenience. In any other env a
    # token is required — otherwise the header would let anyone read/write any tenant's data.
    if settings.auth_required or settings.app_env != "dev":
        raise HTTPException(401, "Authentication required")
    return x_tenant_id


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    """Require a valid token and return the authenticated user (for account/settings routes)."""
    claims = _claims_from_header(authorization)
    if not claims:
        raise HTTPException(401, "Authentication required")
    user = db.get(models.User, claims["sub"])
    if not user:
        raise HTTPException(401, "User not found")
    return user


def get_profile_row(db: Session, tenant_id: str, profile_id: str) -> models.Profile:
    row = (
        db.query(models.Profile)
        .filter(models.Profile.id == profile_id, models.Profile.tenant_id == tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Profile not found")
    return row


def load_master_profile(db: Session, tenant_id: str, profile_id: str) -> tuple[MasterProfile, models.Resume]:
    profile_row = get_profile_row(db, tenant_id, profile_id)
    resume = db.get(models.Resume, profile_row.resume_id)
    if not resume:
        raise HTTPException(404, "Resume file missing")
    mp = parse_resume(resume.path)   # re-parse for fresh, location-mapped units
    return mp, resume


def get_job_row(db: Session, tenant_id: str, job_id: str) -> models.Job:
    row = (
        db.query(models.Job)
        .filter(models.Job.id == job_id, models.Job.tenant_id == tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Job not found")
    return row


# convenience aliases for FastAPI signatures
DbDep = Depends(get_db)
TenantDep = Depends(current_tenant_id)
