"""Daily batch auto-apply (review-then-send).

build_batch(): discover from a saved search -> drop jobs already applied to -> split into
auto-submittable ATS-direct jobs vs manual (you-click) jobs -> tailor the top N (the daily cap)
into PENDING_APPROVAL applications tagged with a batch id. Each job is prepared in its own
SAVEPOINT, so one flaky posting can't discard the whole batch.

send_batch(): the one-click "send all" — submits every pending application in the batch using the
truthful identity (from the master profile) + the saved answers. Enforces the monthly apply cap per
submission. Jobs that hit a CAPTCHA/login land in handoff.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import models
from app.services.apply import orchestrator, runner
from app.services.apply.orchestrator import ApplicationState
from app.services.billing import usage
from app.services.discovery.aggregator import discover
from app.services.matching.matcher import match
from app.services.resume.models import MasterProfile

DEFAULT_AUTO_VENDORS = ("greenhouse", "lever", "ashby")


def _applied_keys(db: Session, tenant_id: str, profile_id: str) -> set[str]:
    rows = (
        db.query(models.Job)
        .join(models.Application, models.Application.job_id == models.Job.id)
        .filter(models.Application.tenant_id == tenant_id,
                models.Application.profile_id == profile_id)
        .all()
    )
    return {f"{(j.company or '').lower().strip()}::{(j.title or '').lower().strip()}" for j in rows}


def build_batch(db: Session, tenant_id: str, search: models.SavedSearch,
                profile: MasterProfile, resume_path: str) -> dict:
    auto_vendors = set(search.vendor_allowlist or DEFAULT_AUTO_VENDORS)
    seen = _applied_keys(db, tenant_id, search.profile_id)

    postings = discover(search.source_specs or [])
    fresh = [p for p in postings if p.dedup_key not in seen]
    auto = [p for p in fresh if p.ats_vendor in auto_vendors]
    manual = [p for p in fresh if p.ats_vendor not in auto_vendors]

    # Score each posting once (don't re-embed the long tail), best first.
    scored = sorted(((match(profile, p.description, p.title).score, p) for p in auto),
                    key=lambda t: t[0], reverse=True)

    batch_id = uuid.uuid4().hex
    prepared: list[dict] = []
    skipped = 0
    for _score, p in scored[: search.daily_cap]:
        try:
            # Per-job SAVEPOINT: a failure here rolls back only this job (incl. its flushed Job row),
            # never the whole batch.
            with db.begin_nested():
                job = models.Job(
                    tenant_id=tenant_id, source=p.source, ats_vendor=p.ats_vendor,
                    external_id=str(p.external_id), company=p.company, title=p.title,
                    location=p.location, description=p.description, url=p.url,
                    posted_at=p.posted_at, skills=p.skills,
                )
                db.add(job)
                db.flush()
                draft = orchestrator.prepare(
                    profile, job_title=job.title, job_company=job.company,
                    job_description=job.description, job_url=job.url, ats_vendor=job.ats_vendor,
                    source_doc_path=resume_path,
                )
                app = models.Application(
                    tenant_id=tenant_id, profile_id=search.profile_id, job_id=job.id,
                    state=draft.state.value, batch_id=batch_id, match_score=draft.match.score,
                    edit_set=draft.edit_set.to_dict(), ats_report=draft.ats_report,
                    tailored_doc_path=draft.tailored_doc_path, notes=draft.notes,
                )
                db.add(app)
                db.flush()
            usage.record(db, tenant_id, "tailor")
            prepared.append({"application_id": app.id, "title": job.title, "company": job.company,
                             "fit": draft.match.score, "url": job.url, "ats_vendor": job.ats_vendor})
        except Exception:  # noqa: BLE001 — one bad posting costs one skipped job, not the batch
            skipped += 1
            continue

    search.last_run_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "batch_id": batch_id,
        "prepared_count": len(prepared),
        "prepared": prepared,
        "skipped": skipped,
        "manual_count": len(manual),
        "manual": [{"title": p.title, "company": p.company, "location": p.location,
                    "url": p.url, "source": p.source} for p in manual[:50]],
    }


def send_batch(db: Session, tenant_id: str, batch_id: str, identity: dict, answers: dict) -> dict:
    """One-click 'send all' for a reviewed batch. Identity is the user's TRUTHFUL master-profile
    identity (passed by the route); answers come from the saved Answer Profile. Enforces the
    monthly apply cap per submission."""
    apps = (
        db.query(models.Application)
        .filter(models.Application.tenant_id == tenant_id,
                models.Application.batch_id == batch_id,
                models.Application.state == ApplicationState.PENDING_APPROVAL.value)
        .all()
    )
    counts = {"submitted": 0, "human_handoff_required": 0, "failed": 0, "blocked_host": 0,
              "skipped_cap": 0}
    for app in apps:
        job = db.get(models.Job, app.job_id)
        if not job:
            continue
        try:
            usage.check_cap(db, tenant_id, "apply")     # mirror the single-apply route's enforcement
        except HTTPException:
            app.notes = list(app.notes or []) + ["Skipped: monthly apply cap reached"]
            counts["skipped_cap"] += 1
            db.commit()
            continue
        app.approved_at = datetime.now(timezone.utc)    # batch consent timestamp
        draft = runner.run_submission(db, app, job, identity, answers)
        counts[draft.state.value] = counts.get(draft.state.value, 0) + 1
        db.commit()   # commit per app so the next check_cap sees usage recorded on success
    return {"batch_id": batch_id, "processed": len(apps), "counts": counts}
