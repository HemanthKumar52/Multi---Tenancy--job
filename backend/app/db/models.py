"""Multi-tenant ORM models.

Every business row carries ``tenant_id``. In dev (SQLite) isolation is enforced in the query
layer (always filter by tenant). In prod (Postgres) add Row-Level Security policies on
``tenant_id`` as the hard backstop — see PLAN.md §4.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), default="")
    plan: Mapped[str] = mapped_column(String(32), default="free")          # free | pro
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), default="", index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    inbox_alias: Mapped[str] = mapped_column(String(255), default="", index=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class UsageEvent(Base):
    """One row per metered action (tailor / apply). Monthly counts drive plan caps."""

    __tablename__ = "usage_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)               # tailor | apply
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class Resume(Base):
    __tablename__ = "resumes"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    path: Mapped[str] = mapped_column(String(1024))
    source_format: Mapped[str] = mapped_column(String(16), default="docx")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    profile: Mapped["Profile"] = relationship(back_populates="resume", uselist=False)


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    resume_id: Mapped[str] = mapped_column(String(32), ForeignKey("resumes.id"))
    data: Mapped[dict] = mapped_column(JSON, default=dict)          # serialized MasterProfile
    ats_report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    resume: Mapped[Resume] = relationship(back_populates="profile")


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    source: Mapped[str] = mapped_column(String(32), default="")
    ats_vendor: Mapped[str] = mapped_column(String(32), default="external")
    external_id: Mapped[str] = mapped_column(String(128), default="")
    company: Mapped[str] = mapped_column(String(255), default="")
    title: Mapped[str] = mapped_column(String(512), default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(1024), default="")
    posted_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    profile_id: Mapped[str] = mapped_column(String(32))
    job_id: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(32), default="pending_approval")
    match_score: Mapped[int] = mapped_column(Integer, default=0)
    edit_set: Mapped[dict] = mapped_column(JSON, default=dict)
    ats_report: Mapped[dict] = mapped_column(JSON, default=dict)
    tailored_doc_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    notes: Mapped[list] = mapped_column(JSON, default=list)
    # Audit/consent record: vendor result, resume hash, screenshot path, confirmation url, etc.
    audit: Mapped[dict] = mapped_column(JSON, default=dict)
    # Payload for the async worker (identity + answers), so QUEUED applies survive a restart.
    queued_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # consent record
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class InboxEvent(Base):
    __tablename__ = "inbox_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    from_addr: Mapped[str] = mapped_column(String(255), default="")
    subject: Mapped[str] = mapped_column(String(998), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="other")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    application_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class InterviewPrep(Base):
    __tablename__ = "interview_preps"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    application_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    channel: Mapped[str] = mapped_column(String(32), default="in-app")
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
