"""Lever live apply — VendorSpec over the shared engine.

DOM verified against jobs.lever.co/<company>/<id>/apply: a SINGLE full-name field (name="name"),
a hidden resume input (#resume-upload-input) that auto-parses (so upload first), and an anchor
submit (a[data-qa="btn-submit"]). Success → navigation to **/thanks. hCaptcha, if shown, trips
the shared CAPTCHA detector → human handoff.
"""
from __future__ import annotations

from app.services.apply.playwright_common import HostNotAllowed, VendorSpec, submit_via_spec

__all__ = ["submit_application", "HostNotAllowed", "LEVER_SPEC"]

LEVER_SPEC = VendorSpec(
    name="lever",
    form_ready=["input[name='name']", "form"],
    full_name=["input[name='name']", "input[data-qa='name-input']"],
    email=["input[name='email']", "input[type='email']"],
    phone=["input[name='phone']", "input[type='tel']"],
    resume=["#resume-upload-input", "input[name='resume']", "input[type='file'][name='resume']"],
    submit=["a[data-qa='btn-submit']", "#btn-submit", "button[data-qa='btn-submit']",
            "a:has-text('Submit application')"],
    success_url_glob="**/thanks*",
    success_selectors=["h3[data-qa='msg-submit-success']", "*:has-text('Application submitted!')"],
    iframe_selector=None,
    upload_resume_first=True,
)


def submit_application(apply_url, resume_path, identity, answers=None, **kw) -> dict:
    return submit_via_spec(LEVER_SPEC, apply_url, resume_path, identity, answers, **kw)
