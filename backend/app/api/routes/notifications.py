from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_tenant_id
from app.db import models
from app.db.base import get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    rows = (
        db.query(models.Notification)
        .filter(models.Notification.tenant_id == tenant_id)
        .order_by(models.Notification.created_at.desc())
        .all()
    )
    return {"notifications": [{"id": r.id, "title": r.title, "body": r.body,
                              "channel": r.channel, "read": r.read,
                              "created_at": r.created_at.isoformat()} for r in rows]}
