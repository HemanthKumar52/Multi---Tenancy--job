"""Pydantic request models for the API. Responses are returned as plain dicts/JSON."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)   # bound feeds into PBKDF2
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str = Field(max_length=128)


class DiscoverRequest(BaseModel):
    source_specs: list[dict] = Field(
        default_factory=list,
        examples=[[{"vendor": "greenhouse", "board": "stripe"}, {"vendor": "lever", "company": "netflix"}]],
    )


class ManualJobRequest(BaseModel):
    title: str
    company: str = ""
    description: str = ""
    location: str = ""
    url: str = ""
    ats_vendor: str = "external"


class MatchRequest(BaseModel):
    profile_id: str
    job_id: str


class TailorRequest(BaseModel):
    profile_id: str
    job_id: str


class PrepareRequest(BaseModel):
    profile_id: str
    job_id: str


class ApproveRequest(BaseModel):
    answers: dict = Field(default_factory=dict)
    # Must be explicitly set true by the caller — a bare approve is rejected (co-pilot consent).
    confirm: bool = False


class InboundEmailRequest(BaseModel):
    from_addr: str = ""
    subject: str = ""
    body: str = ""
    to_alias: str = ""
    application_id: str | None = None


class AnswerProfileRequest(BaseModel):
    profile_id: str = ""
    identity: dict = Field(default_factory=dict)   # first_name/last_name/email/phone
    answers: dict = Field(default_factory=dict)     # {question label: answer}
    meta: dict = Field(default_factory=dict)        # work_authorized, needs_sponsorship, links


class SavedSearchRequest(BaseModel):
    profile_id: str
    name: str = "Daily auto-apply"
    source_specs: list[dict] = Field(default_factory=list)
    daily_cap: int = 10
    vendor_allowlist: list[str] = Field(default_factory=lambda: ["greenhouse", "lever", "ashby"])
    review_mode: bool = True


class PrepRequest(BaseModel):
    company: str = ""
    role: str = ""
    email_body: str = ""
    job_id: str | None = None
    application_id: str | None = None
