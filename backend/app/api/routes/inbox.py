from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_tenant_id
from app.db import models
from app.db.base import get_db
from app.schemas import InboundEmailRequest
from app.services.inbox.ingest import ingest_email

router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.post("/inbound")
def inbound(
    req: InboundEmailRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    """Webhook for the forwarding-alias provider (Postmark/SendGrid inbound)."""
    return ingest_email(db, tenant_id, from_addr=req.from_addr, subject=req.subject,
                        body=req.body, application_id=req.application_id)


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
