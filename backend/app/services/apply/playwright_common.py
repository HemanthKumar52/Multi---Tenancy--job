"""Generic, spec-driven Playwright apply engine shared by all ATS vendors.

Each vendor supplies a :class:`VendorSpec` (selectors + a couple of behavior flags); the engine
handles everything that must be identical across vendors: the host allowlist (pre-launch AND
after redirects), CAPTCHA/login detection across all frames (→ human handoff, never bypassed),
embed-iframe scope resolution, resume upload, identity + custom-question filling, an
``aria-disabled``-aware submit, success detection, and a PII-safe audit screenshot.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from app.config import settings
from app.services.apply.vendors import HostNotAllowed  # re-exported by vendor modules

_LOOPBACK = {"127.0.0.1", "localhost"}
_CAPTCHA_SELECTORS = (
    'iframe[src*="recaptcha"]', 'iframe[src*="hcaptcha"]', 'iframe[title*="captcha" i]',
    'div.g-recaptcha', '[data-sitekey]', 'input[type="password"]',
)


@dataclass
class VendorSpec:
    name: str
    form_ready: list[str]                      # any-of selectors signaling the form has hydrated
    email: list[str]
    submit: list[str]
    resume: list[str] = field(default_factory=list)
    first_name: list[str] = field(default_factory=list)
    last_name: list[str] = field(default_factory=list)
    full_name: list[str] = field(default_factory=list)
    phone: list[str] = field(default_factory=list)
    success_url_glob: str | None = None
    success_selectors: list[str] = field(default_factory=list)
    iframe_selector: str | None = None
    upload_resume_first: bool = False


def host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {h.lower() for h in settings.apply_allowed_hosts}:
        return False
    if host in _LOOPBACK:
        return settings.app_env == "dev"
    return (parsed.scheme or "").lower() == "https"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def looks_like_captcha_or_login(page) -> str | None:
    try:
        frames = list(page.frames)
    except Exception:
        frames = []
    for frame in frames:
        for sel in _CAPTCHA_SELECTORS:
            try:
                if frame.locator(sel).count() > 0:
                    return f"blocked by {sel} — handed off to human (no automated bypass)"
            except Exception:
                continue
    return None


def _fill_first(scope, selectors: list[str], value: str) -> bool:
    if not value:
        return False
    for sel in selectors:
        try:
            loc = scope.locator(sel).first
            if loc.count() > 0:
                loc.fill(value, timeout=5000)
                return True
        except Exception:
            continue
    return False


def _present(scope, selectors: list[str]) -> bool:
    for sel in selectors:
        try:
            if scope.locator(sel).first.count() > 0:
                return True
        except Exception:
            continue
    return False


def _fill_identity(scope, spec: VendorSpec, identity: dict) -> None:
    first = identity.get("first_name", "")
    last = identity.get("last_name", "")
    if spec.first_name and _present(scope, spec.first_name):
        _fill_first(scope, spec.first_name, first)
        _fill_first(scope, spec.last_name, last)
    else:
        full = (first + " " + last).strip() or identity.get("name", "")
        _fill_first(scope, spec.full_name or spec.first_name, full)
    _fill_first(scope, spec.email, identity.get("email", ""))
    _fill_first(scope, spec.phone, identity.get("phone", ""))


def _answer_questions(scope, page, answers: dict) -> list[str]:
    unfilled: list[str] = []
    for label, value in (answers or {}).items():
        rx = re.compile(re.escape(label), re.I)
        try:
            loc = scope.get_by_label(rx).first
            if loc.count() > 0:
                loc.fill(str(value), timeout=4000)
                continue
        except Exception:
            pass
        try:
            combo = scope.get_by_role("combobox", name=rx).first
            if combo.count() > 0:
                combo.click(timeout=4000)
                try:
                    scope.get_by_role("option", name=re.compile(re.escape(str(value)), re.I)).first.click(timeout=4000)
                    continue
                except Exception:
                    try:
                        page.keyboard.press("Escape")
                    except Exception:
                        pass
        except Exception:
            pass
        unfilled.append(label)
    return unfilled


def _upload_resume(scope, spec: VendorSpec, resume_path: str, timeout_ms: int) -> str | None:
    if not (resume_path and spec.resume):
        return None
    last_err: Exception | None = None
    for sel in spec.resume:
        try:
            loc = scope.locator(sel).first
            if loc.count() > 0:
                loc.set_input_files(resume_path, timeout=timeout_ms)
                return None
        except Exception as exc:  # matched a control but set_input_files failed
            last_err = exc
            continue
    return f"Resume upload failed: {last_err}" if last_err else "Resume upload control not found."


def _detect_success(page, scope, spec: VendorSpec, timeout_ms: int) -> bool:
    if spec.success_url_glob:
        try:
            page.wait_for_url(spec.success_url_glob, timeout=timeout_ms)
            return True
        except PWTimeout:
            pass
    for sel in spec.success_selectors:
        try:
            scope.locator(sel).first.wait_for(state="visible", timeout=4000)
            return True
        except PWTimeout:
            continue
        except Exception:
            continue
    try:
        return any("confirmation" in (fr.url or "") or "thanks" in (fr.url or "") for fr in page.frames)
    except Exception:
        return False


def submit_via_spec(
    spec: VendorSpec,
    apply_url: str,
    resume_path: str | None,
    identity: dict,
    answers: dict | None = None,
    *,
    headless: bool | None = None,
    timeout_ms: int | None = None,
    screenshot_dir: str | None = None,
    dry_run: bool = False,
) -> dict:
    if not host_allowed(apply_url):
        raise HostNotAllowed(
            f"Refusing to submit to non-allowlisted host {urlparse(apply_url).hostname!r}.")

    headless = settings.browser_headless if headless is None else headless
    timeout_ms = settings.apply_timeout_ms if timeout_ms is None else timeout_ms
    shot_dir = Path(screenshot_dir or (settings.storage_path / "apply_screenshots"))
    shot_dir.mkdir(parents=True, exist_ok=True)

    result: dict = {"ok": False, "status": "failed", "message": "", "confirmation_url": None,
                    "screenshot_path": None, "unfilled_questions": [], "vendor": spec.name,
                    "resume_sha256": sha256_file(resume_path) if resume_path else None}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=settings.user_agent)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(apply_url, wait_until="domcontentloaded", timeout=timeout_ms)
            if not host_allowed(page.url):
                raise HostNotAllowed(
                    f"Redirected to non-allowlisted host {urlparse(page.url).hostname!r} — aborting.")

            handoff = looks_like_captcha_or_login(page)
            if handoff:
                result.update(status="human_handoff_required", message=handoff)
                return _finalize(page, shot_dir, result)

            scope = page
            if spec.iframe_selector and page.locator(spec.iframe_selector).count() > 0:
                scope = page.frame_locator(spec.iframe_selector)

            try:
                ready = ", ".join(spec.form_ready)
                scope.locator(ready).first.wait_for(state="visible", timeout=timeout_ms)
            except PWTimeout:
                result.update(message="Application form did not load.")
                return _finalize(page, shot_dir, result)

            # Some vendors auto-parse the resume and overwrite typed fields, so upload first there.
            if spec.upload_resume_first and resume_path:
                err = _upload_resume(scope, spec, resume_path, timeout_ms)
                if err:
                    result.update(message=err)
                    return _finalize(page, shot_dir, result)
                page.wait_for_timeout(800)  # let any resume-parse autofill settle

            _fill_identity(scope, spec, identity)

            if not spec.upload_resume_first and resume_path:
                err = _upload_resume(scope, spec, resume_path, timeout_ms)
                if err:
                    result.update(message=err)
                    return _finalize(page, shot_dir, result)

            result["unfilled_questions"] = _answer_questions(scope, page, answers or {})

            handoff = looks_like_captcha_or_login(page)
            if handoff:
                result.update(status="human_handoff_required", message=handoff)
                return _finalize(page, shot_dir, result)

            submit = None
            for sel in spec.submit:
                cand = scope.locator(sel).first
                try:
                    if cand.count() > 0:
                        submit = cand
                        break
                except Exception:
                    continue
            if submit is None:
                result.update(message="Submit button not found.")
                return _finalize(page, shot_dir, result)

            if dry_run:
                # Validation / preview: everything is filled, but we STOP before submit.
                # Nothing is ever sent to the company.
                result.update(ok=True, status="dry_run", submit_ready=True,
                              message=f"{spec.name}: form filled and ready — stopped before submit "
                                      f"(dry run, nothing sent).")
                return _finalize(page, shot_dir, result)

            for _ in range(20):   # aria-disabled guard (bounded, ~5s, not a busy-spin)
                try:
                    if (submit.get_attribute("aria-disabled", timeout=500) or "false") != "true":
                        break
                except Exception:
                    break
                page.wait_for_timeout(250)
            submit.click(timeout=timeout_ms)

            if _detect_success(page, scope, spec, timeout_ms):
                result.update(ok=True, status="submitted", confirmation_url=page.url,
                              message=f"Submitted to {spec.name}; confirmation reached.")
            else:
                result.update(message="Submit did not produce a confirmation — possible validation error.")
            return _finalize(page, shot_dir, result)
        except HostNotAllowed:
            raise
        except Exception as exc:  # noqa: BLE001
            result.update(message=f"Apply error: {exc}")
            return _finalize(page, shot_dir, result)
        finally:
            context.close()
            browser.close()


def _finalize(page, shot_dir: Path, result: dict) -> dict:
    # Screenshot the confirmation (submitted) or the filled-but-unsent form (dry_run) for evidence.
    if result.get("status") not in ("submitted", "dry_run") and not settings.apply_debug_screenshots:
        return result
    try:
        stamp = hashlib.sha1(f"{page.url}:{result['status']}:{result['vendor']}".encode()).hexdigest()[:12]
        path = shot_dir / f"apply_{result['vendor']}_{result['status']}_{stamp}.png"
        page.screenshot(path=str(path), full_page=True)
        result["screenshot_path"] = str(path)
    except Exception:
        pass
    return result
