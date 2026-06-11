"""Usage metering + plan caps.

Meters the variable-cost actions (tailor, apply) per tenant per calendar month and enforces
per-plan ceilings. Plans work fully offline; Stripe (see routes/billing.py) just flips the plan.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import models

# Monthly caps per plan. Tune freely.
PLANS: dict[str, dict[str, int]] = {
    "free": {"tailor": 20, "apply": 10},
    "pro": {"tailor": 1000, "apply": 500},
}
KINDS = ("tailor", "apply")


def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def tenant_plan(db: Session, tenant_id: str) -> str:
    tenant = db.get(models.Tenant, tenant_id)
    return tenant.plan if tenant else "free"


def caps(plan: str) -> dict[str, int]:
    return PLANS.get(plan, PLANS["free"])


def usage_count(db: Session, tenant_id: str, kind: str) -> int:
    return (
        db.query(models.UsageEvent)
        .filter(models.UsageEvent.tenant_id == tenant_id,
                models.UsageEvent.kind == kind,
                models.UsageEvent.created_at >= _month_start())
        .count()
    )


def check_cap(db: Session, tenant_id: str, kind: str) -> dict:
    """Enforce the monthly cap WITHOUT recording usage. Raises 402 when at/over the limit.

    NOTE: count-then-check is not atomic — under high concurrency two requests could both pass
    near the boundary (TOCTOU). For strict enforcement on Postgres, move to a per-(tenant,month,
    kind) counter row updated with a conditional atomic UPDATE. Acceptable for current scale.
    """
    plan = tenant_plan(db, tenant_id)
    cap = caps(plan).get(kind, 0)
    used = usage_count(db, tenant_id, kind)
    if used >= cap:
        raise HTTPException(
            402, f"Monthly {kind} limit reached on the '{plan}' plan ({used}/{cap}). "
                 f"Upgrade to continue.")
    return {"plan": plan, "kind": kind, "used": used, "cap": cap}


def record(db: Session, tenant_id: str, kind: str) -> None:
    """Record one usage event (does not commit — the caller owns the transaction)."""
    db.add(models.UsageEvent(tenant_id=tenant_id, kind=kind))


def check_and_record(db: Session, tenant_id: str, kind: str) -> dict:
    """Enforce + record in one step (used where the action always proceeds, e.g. tailoring)."""
    info = check_cap(db, tenant_id, kind)
    record(db, tenant_id, kind)
    return {**info, "used": info["used"] + 1}


def summary(db: Session, tenant_id: str) -> dict:
    plan = tenant_plan(db, tenant_id)
    cap = caps(plan)
    return {
        "plan": plan,
        "usage": {k: {"used": usage_count(db, tenant_id, k), "cap": cap[k]} for k in KINDS},
        "plans": PLANS,
    }
