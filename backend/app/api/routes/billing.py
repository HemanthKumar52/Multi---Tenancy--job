from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import current_tenant_id
from app.config import settings
from app.db import models
from app.db.base import get_db
from app.services.billing import usage

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plan")
def get_plan(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    return usage.summary(db, tenant_id)


@router.post("/checkout")
def checkout(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    """Create a Stripe Checkout session for the Pro plan (requires Stripe config)."""
    if not (settings.stripe_secret_key and settings.stripe_price_id_pro):
        raise HTTPException(501, "Billing is not configured (set STRIPE_SECRET_KEY + STRIPE_PRICE_ID_PRO).")
    import stripe

    stripe.api_key = settings.stripe_secret_key
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.stripe_price_id_pro, "quantity": 1}],
        success_url="http://localhost:3000/settings?upgraded=1",
        cancel_url="http://localhost:3000/settings",
        client_reference_id=tenant_id,
        metadata={"tenant_id": tenant_id},
    )
    return {"checkout_url": session.url}


def _resolve_tenant(db: Session, obj: dict) -> models.Tenant | None:
    tid = (obj.get("metadata") or {}).get("tenant_id") or obj.get("client_reference_id")
    if tid:
        t = db.get(models.Tenant, tid)
        if t:
            return t
    # subscription.* events carry no metadata — resolve by stored Stripe ids.
    for col, val in ((models.Tenant.stripe_subscription_id, obj.get("id")),
                     (models.Tenant.stripe_customer_id, obj.get("customer"))):
        if val:
            t = db.query(models.Tenant).filter(col == val).first()
            if t:
                return t
    return None


_PRO_STATUSES = {"active", "trialing"}


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Stripe webhook — adjusts a tenant's plan. Requires a verified signature outside dev."""
    if not settings.stripe_secret_key:
        raise HTTPException(501, "Billing not configured")
    import stripe

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if settings.stripe_webhook_secret:
        try:
            event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
        except Exception as exc:  # noqa: BLE001 — bad signature / malformed
            raise HTTPException(400, f"Invalid webhook signature: {exc}")
    elif settings.app_env == "dev":
        import json
        event = json.loads(payload)        # unsigned allowed ONLY in dev for local testing
    else:
        raise HTTPException(501, "Webhook secret not configured — refusing unsigned events")

    etype = event.get("type", "")
    obj = (event.get("data") or {}).get("object", {})
    tenant = _resolve_tenant(db, obj)
    if not tenant:
        return {"received": True, "matched": False}

    if etype in ("checkout.session.completed", "customer.subscription.created"):
        tenant.plan = "pro"
        tenant.stripe_customer_id = obj.get("customer") or tenant.stripe_customer_id
        tenant.stripe_subscription_id = obj.get("subscription") or obj.get("id") or tenant.stripe_subscription_id
    elif etype == "customer.subscription.updated":
        tenant.plan = "pro" if obj.get("status") in _PRO_STATUSES else "free"
    elif etype == "customer.subscription.deleted":
        tenant.plan = "free"
        tenant.stripe_subscription_id = None
    db.commit()
    return {"received": True, "matched": True, "plan": tenant.plan}


@router.post("/dev-upgrade")
def dev_upgrade(
    plan: str = "pro",
    db: Session = Depends(get_db),
    tenant_id: str = Depends(current_tenant_id),
) -> dict:
    """Dev-only helper to change plan without Stripe (for local testing)."""
    if settings.app_env != "dev":
        raise HTTPException(403, "Only available in dev")
    tenant = db.get(models.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    tenant.plan = plan if plan in usage.PLANS else "free"
    db.commit()
    return {"plan": tenant.plan}
