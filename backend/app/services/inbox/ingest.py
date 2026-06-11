"""Shared inbound-email pipeline: classify -> persist -> (interview) prep + notify.

One entry point used by the forwarding-alias webhook AND the native connectors (IMAP/Gmail), so
every channel behaves identically.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import models
from app.services.inbox import prep_generator
from app.services.inbox.classifier import EmailCategory, classify
from app.services.notify import notifier


def ingest_email(db: Session, tenant_id: str, *, from_addr: str, subject: str, body: str,
                 application_id: str | None = None, commit: bool = True) -> dict:
    result = classify(subject, body)
    event = models.InboxEvent(
        tenant_id=tenant_id, from_addr=from_addr, subject=subject, body=body,
        category=result.category.value, confidence=result.confidence,
        application_id=application_id,
    )
    db.add(event)

    response: dict = {"classification": result.to_dict()}

    if result.category is EmailCategory.INTERVIEW_INVITE:
        job_desc, company, role = "", "", ""
        if application_id:
            # Tenant-scoped: never dereference another tenant's application/job.
            app_row = (
                db.query(models.Application)
                .filter(models.Application.id == application_id,
                        models.Application.tenant_id == tenant_id)
                .first()
            )
            if app_row:
                job = db.get(models.Job, app_row.job_id)
                if job:
                    job_desc, company, role = job.description, job.company, job.title
            else:
                application_id = None   # drop an unknown/foreign linkage
        plan = prep_generator.generate(company, role, body, job_desc)
        db.add(models.InterviewPrep(tenant_id=tenant_id, application_id=application_id,
                                    plan=plan.to_dict()))
        title = f"Interview invite — prep ready ({company or 'company'})"
        note = "Topics: " + ", ".join(plan.topics[:6])
        db.add(models.Notification(tenant_id=tenant_id, title=title, body=note))
        notifier.notify(None, title, note)
        response["prep_plan"] = plan.to_dict()
    else:
        db.add(models.Notification(tenant_id=tenant_id,
                                   title=f"New update: {result.category.value}", body=subject))

    if commit:
        db.commit()
    response["event_id"] = event.id
    return response
