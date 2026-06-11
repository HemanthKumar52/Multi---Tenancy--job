"""Greenhouse live apply — a thin VendorSpec over the shared spec-driven engine.

DOM verified against the current job-boards.greenhouse.io Remix form (legacy boards.* 301s to it).
"""
from __future__ import annotations

from app.services.apply.playwright_common import HostNotAllowed, VendorSpec, submit_via_spec

__all__ = ["submit_application", "HostNotAllowed", "GREENHOUSE_SPEC"]

GREENHOUSE_SPEC = VendorSpec(
    name="greenhouse",
    form_ready=["#application-form", "#first_name"],
    first_name=["#first_name", 'input[autocomplete="given-name"]'],
    last_name=["#last_name", 'input[autocomplete="family-name"]'],
    email=["#email", 'input[autocomplete="email"]', 'input[type="email"]'],
    phone=["#phone", 'input[type="tel"]'],
    resume=["#resume", 'input[type="file"][accept*="pdf"]'],
    submit=["button:has-text('Submit application')", 'button[type="submit"]'],
    success_url_glob="**/confirmation*",
    success_selectors=["h1:has-text('Thank you for applying')", "h2:has-text('Thank you for applying')"],
    iframe_selector="#grnhse_iframe",
    upload_resume_first=False,
)


def submit_application(apply_url, resume_path, identity, answers=None, **kw) -> dict:
    return submit_via_spec(GREENHOUSE_SPEC, apply_url, resume_path, identity, answers, **kw)
