"""Shared submission runner — used by both the synchronous approve path and the async worker.

Builds the apply draft from a stored Application + Job, drives the vendor flow through the
orchestrator, and writes the result back (state, notes, submitted_at, audit, notification).
Does not commit — the caller owns the transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.db import models
from app.services.apply import orchestrator
from app.services.apply.orchestrator import ApplicationDraft, ApplicationState
from app.services.billing import usage
from app.services.matching.matcher import MatchResult
from app.services.notify import notifier
from app.services.resume.models import Edit, EditSet


def run_submission(db: Session, app_row: models.Application, job: models.Job,
                   identity: dict, answers: dict) -> ApplicationDraft:
    draft = ApplicationDraft(
        job_title=job.title, job_company=job.company, job_url=job.url,
        ats_vendor=job.ats_vendor, match=MatchResult(score=app_row.match_score),
        edit_set=EditSet(edits=[Edit(**e) for e in (app_row.edit_set or {}).get("edits", [])]),
        ats_report=app_row.ats_report, tailored_doc_path=app_row.tailored_doc_path,
        notes=list(app_row.notes or []), state=ApplicationState.PENDING_APPROVAL,
    )
    draft = orchestrator.approve_and_submit(draft, identity=identity, answers=answers)

    app_row.state = draft.state.value
    app_row.notes = draft.notes
    app_row.queued_payload = {}            # consumed
    if draft.state == ApplicationState.SUBMITTED:
        app_row.submitted_at = datetime.now(timezone.utc)
        usage.record(db, app_row.tenant_id, "apply")   # only a real submission consumes quota

    app_row.audit = {
        **(draft.audit or {}),
        "approved_at": app_row.approved_at.isoformat() if app_row.approved_at else None,
        "user_agent": settings.user_agent,
        "company": job.company, "role": job.title, "ats_vendor": job.ats_vendor,
        "apply_url": job.url,
        "answered_question_labels": sorted((answers or {}).keys()),
        "consented_via": "approve route, confirm=true",
    }

    note = "; ".join(n for n in draft.notes if n) or draft.state.value
    db.add(models.Notification(
        tenant_id=app_row.tenant_id,
        title=f"Application {draft.state.value}: {job.title} @ {job.company}", body=note))
    notifier.notify(None, f"Application {draft.state.value}", note)
    return draft
