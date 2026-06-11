from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db import models
from app.db.base import get_db
from app.schemas import LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])


def _make_alias(email: str, user_id: str) -> str:
    local = re.sub(r"[^a-z0-9]+", ".", email.split("@")[0].lower()).strip(".") or "user"
    return f"{local}.{user_id[:6]}@{settings.inbound_domain}"


def _token_response(user: models.User, tenant: models.Tenant) -> dict:
    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, email=user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name,
                 "inbox_alias": user.inbox_alias},
        "tenant": {"id": tenant.id, "plan": tenant.plan},
    }


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    email = req.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(400, "Invalid email")
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(409, "An account with this email already exists")

    tenant = models.Tenant(name=req.name or email)
    db.add(tenant)
    db.flush()
    user = models.User(
        tenant_id=tenant.id, email=email, name=req.name,
        password_hash=hash_password(req.password),
    )
    db.add(user)
    db.flush()
    user.inbox_alias = _make_alias(email, user.id)
    db.commit()
    return _token_response(user, tenant)


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)) -> dict:
    email = req.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    tenant = db.get(models.Tenant, user.tenant_id)
    return _token_response(user, tenant)


@router.get("/me")
def me(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    tenant = db.get(models.Tenant, user.tenant_id)
    return {
        "id": user.id, "email": user.email, "name": user.name,
        "inbox_alias": user.inbox_alias,
        "tenant": {"id": tenant.id, "plan": tenant.plan} if tenant else None,
    }
