from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_tenant_id
from app.db import models
from app.db.base import get_db
from app.schemas import InboundEmailRequest
from app.services.inbox import prep_generator
from app.services.inbox.classifier import EmailCategory, classify
from app.services.notify import notifier

router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.post("/inbound")
def inbound(
    req: InboundEmailRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    """Webhook for the forwarding-alias provider (Postmark/SendGrid inbound)."""
    result = classify(req.subject, req.body)

    event = models.InboxEvent(
        tenant_id=tenant_id,
        from_addr=req.from_addr,
        subject=req.subject,
        body=req.body,
        category=result.category.value,
        confidence=result.confidence,
        application_id=req.application_id,
    )
    db.add(event)

    response: dict = {"classification": result.to_dict()}

    # On an interview invite, auto-generate a prep plan and notify the user.
    if result.category is EmailCategory.INTERVIEW_INVITE:
        job_desc, company, role = "", "", ""
        if req.application_id:
            app_row = db.get(models.Application, req.application_id)
            if app_row:
                job = db.get(models.Job, app_row.job_id)
                if job:
                    job_desc, company, role = job.description, job.company, job.title
        plan = prep_generator.generate(company, role, req.body, job_desc)
        db.add(models.InterviewPrep(tenant_id=tenant_id, application_id=req.application_id,
                                    plan=plan.to_dict()))
        title = f"Interview invite — prep ready ({company or 'company'})"
        body = "Topics: " + ", ".join(plan.topics[:6])
        db.add(models.Notification(tenant_id=tenant_id, title=title, body=body))
        notifier.notify(None, title, body)
        response["prep_plan"] = plan.to_dict()
    else:
        title = f"New update: {result.category.value}"
        db.add(models.Notification(tenant_id=tenant_id, title=title, body=req.subject))

    db.commit()
    response["event_id"] = event.id
    return response


@router.get("")
def list_events(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    rows = (
        db.query(models.InboxEvent)
        .filter(models.InboxEvent.tenant_id == tenant_id)
        .order_by(models.InboxEvent.created_at.desc())
        .all()
    )
    return {"events": [{"id": r.id, "from": r.from_addr, "subject": r.subject,
                        "category": r.category, "confidence": r.confidence,
                        "application_id": r.application_id} for r in rows]}
