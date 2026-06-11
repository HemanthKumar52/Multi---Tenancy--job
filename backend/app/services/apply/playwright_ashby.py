"""Ashby live apply — VendorSpec over the shared engine.

DOM verified against jobs.ashbyhq.com/<org>/<id>/application: a React SPA with slow hydration
(wait on .ashby-application-form-container), a name field that may be single or split, a hidden
file input, and a submit button (.ashby-application-form-submit-button). Success renders
.ashby-application-form-success-container (no URL change). Embedded boards live in an
iframe[src*="ashbyhq"]; the engine switches scope automatically.
"""
from __future__ import annotations

from app.services.apply.playwright_common import HostNotAllowed, VendorSpec, submit_via_spec

__all__ = ["submit_application", "HostNotAllowed", "ASHBY_SPEC"]

ASHBY_SPEC = VendorSpec(
    name="ashby",
    form_ready=[".ashby-application-form-container", "input[type='email']"],
    first_name=["input[aria-label='First Name']", "input[name*='first' i]"],
    last_name=["input[aria-label='Last Name']", "input[name*='last' i]"],
    full_name=["input[aria-label='Name']", "input[id*='_systemfield_name']"],
    email=["input[type='email']", "input[aria-label='Email']"],
    phone=["input[type='tel']", "input[aria-label='Phone']"],
    resume=["input[type='file']"],
    submit=[".ashby-application-form-submit-button", "button:has-text('Submit Application')",
            "button:has-text('Submit')", "form button[type='submit']"],
    success_url_glob=None,
    success_selectors=[".ashby-application-form-success-container",
                       "*:has-text('Application submitted')", "*:has-text('Thanks for applying')"],
    iframe_selector="iframe[src*='ashbyhq']",
    upload_resume_first=True,
)


def submit_application(apply_url, resume_path, identity, answers=None, **kw) -> dict:
    return submit_via_spec(ASHBY_SPEC, apply_url, resume_path, identity, answers, **kw)
