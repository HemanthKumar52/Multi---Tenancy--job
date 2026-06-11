"""Live Greenhouse application automation via Playwright.

Built on the verified current Greenhouse DOM (job-boards.greenhouse.io Remix form; the legacy
boards.greenhouse.io URLs 301 to it). Key facts encoded here:

* Text fields ``#first_name`` / ``#last_name`` / ``#email`` / ``#phone`` are controlled React
  inputs — use ``.fill()``; fall back to label locators.
* Resume upload is a *hidden* ``input#resume[type=file]`` — ``set_input_files`` directly; never
  click the visible "Attach" button (it opens the OS chooser Playwright can't drive).
* The form may be inline (``#application-form``) or embedded in ``iframe#grnhse_iframe`` — we run
  all locators (incl. success detection) through ``scope`` so both cases work.
* Submit button text is "Submit application"; it uses ``aria-disabled`` (not ``disabled``).
* Success = navigation to ``**/confirmation*`` and/or a "Thank you for applying" heading.

Guardrails: honest identifiable UA, **no** stealth / CAPTCHA evasion (a CAPTCHA/login wall —
checked across all frames — returns ``human_handoff_required``), a scheme/port-aware host
allowlist re-checked after redirects, and audit screenshots restricted to PII-free states.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from app.config import settings
from app.services.apply.vendors import HostNotAllowed  # re-exported (pg.HostNotAllowed)

_LOOPBACK = {"127.0.0.1", "localhost"}

__all__ = ["submit_application", "HostNotAllowed"]


def _host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    scheme = (parsed.scheme or "").lower()
    if host not in {h.lower() for h in settings.apply_allowed_hosts}:
        return False
    if host in _LOOPBACK:
        return settings.app_env == "dev"   # the local sandbox is dev-only
    return scheme == "https"               # real ATS hosts must be https


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


_CAPTCHA_SELECTORS = (
    'iframe[src*="recaptcha"]', 'iframe[src*="hcaptcha"]', 'iframe[title*="captcha" i]',
    'div.g-recaptcha', '[data-sitekey]', 'input[type="password"]',
)


def _looks_like_captcha_or_login(page) -> str | None:
    """Return a reason if a CAPTCHA / bot-check / login wall is present in ANY frame, else None."""
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


def _answer_questions(scope, page, answers: dict) -> list[str]:
    """Map answers to custom questions by visible label. Returns labels we couldn't fill."""
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
        # react-select combobox: open, pick option, and ALWAYS dismiss the menu on failure so a
        # lingering overlay can't intercept the later submit click.
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


def _detect_success(page, scope, timeout_ms: int) -> bool:
    # Top-level navigation (inline / redirect form).
    try:
        page.wait_for_url("**/confirmation*", timeout=timeout_ms)
        return True
    except PWTimeout:
        pass
    # Confirmation heading — queried through `scope`, so it works inside the embed iframe too.
    try:
        scope.get_by_role("heading", name=re.compile("thank you for applying", re.I)).first.wait_for(
            state="visible", timeout=5000
        )
        return True
    except PWTimeout:
        pass
    # Any frame navigated to a confirmation URL.
    try:
        return any("confirmation" in (fr.url or "") for fr in page.frames)
    except Exception:
        return False


def submit_application(
    apply_url: str,
    resume_path: str | None,
    identity: dict,
    answers: dict | None = None,
    *,
    headless: bool | None = None,
    timeout_ms: int | None = None,
    screenshot_dir: str | None = None,
) -> dict:
    """Drive the Greenhouse apply form. Returns a structured result + audit fields.

    Never submits to a host outside the allowlist — enforced before launch AND after redirects.
    """
    if not _host_allowed(apply_url):
        raise HostNotAllowed(
            f"Refusing to submit to non-allowlisted host {urlparse(apply_url).hostname!r}. "
            f"Add it to APPLY_ALLOWED_HOSTS (https required for non-loopback)."
        )

    headless = settings.browser_headless if headless is None else headless
    timeout_ms = settings.apply_timeout_ms if timeout_ms is None else timeout_ms
    shot_dir = Path(screenshot_dir or (settings.storage_path / "apply_screenshots"))
    shot_dir.mkdir(parents=True, exist_ok=True)

    result: dict = {"ok": False, "status": "failed", "message": "", "confirmation_url": None,
                    "screenshot_path": None, "unfilled_questions": [],
                    "resume_sha256": _sha256(resume_path) if resume_path else None}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=settings.user_agent)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(apply_url, wait_until="domcontentloaded", timeout=timeout_ms)

            # Re-validate after redirects — goto follows 30x, so the landed host must be checked.
            if not _host_allowed(page.url):
                raise HostNotAllowed(
                    f"Redirected to non-allowlisted host {urlparse(page.url).hostname!r} — aborting."
                )

            handoff = _looks_like_captcha_or_login(page)
            if handoff:
                result.update(status="human_handoff_required", message=handoff)
                return _finalize(page, shot_dir, result)

            scope = page
            if page.locator("#grnhse_iframe").count() > 0:
                scope = page.frame_locator("#grnhse_iframe")

            try:
                scope.locator("#application-form, #first_name").first.wait_for(state="visible", timeout=timeout_ms)
            except PWTimeout:
                result.update(message="Application form did not load (no #application-form / #first_name).")
                return _finalize(page, shot_dir, result)

            _fill_first(scope, ["#first_name", 'input[autocomplete="given-name"]'], identity.get("first_name", ""))
            _fill_first(scope, ["#last_name", 'input[autocomplete="family-name"]'], identity.get("last_name", ""))
            _fill_first(scope, ["#email", 'input[autocomplete="email"]', 'input[type="email"]'], identity.get("email", ""))
            _fill_first(scope, ["#phone", 'input[type="tel"]'], identity.get("phone", ""))

            if resume_path:
                try:
                    scope.locator('#resume, input[type="file"][accept*="pdf"]').first.set_input_files(
                        resume_path, timeout=timeout_ms
                    )
                except Exception as exc:  # noqa: BLE001
                    result.update(message=f"Resume upload failed: {exc}")
                    return _finalize(page, shot_dir, result)

            result["unfilled_questions"] = _answer_questions(scope, page, answers or {})

            handoff = _looks_like_captcha_or_login(page)
            if handoff:
                result.update(status="human_handoff_required", message=handoff)
                return _finalize(page, shot_dir, result)

            submit = scope.get_by_role("button", name=re.compile("submit application", re.I)).first
            if submit.count() == 0:
                submit = scope.locator('button[type="submit"]').first
            if submit.count() == 0:
                result.update(message="Submit button not found.")
                return _finalize(page, shot_dir, result)

            # aria-disabled guard with a bounded, non-blocking probe (Greenhouse disables while
            # uploading/validating). A missing/slow attribute must never block on the page default.
            for _ in range(20):
                try:
                    if (submit.get_attribute("aria-disabled", timeout=500) or "false") != "true":
                        break
                except Exception:
                    break
            submit.click(timeout=timeout_ms)

            if _detect_success(page, scope, timeout_ms):
                result.update(ok=True, status="submitted", confirmation_url=page.url,
                              message="Submitted; reached confirmation.")
            else:
                result.update(message="Submit did not produce a confirmation — possible validation error.")
            return _finalize(page, shot_dir, result)
        except HostNotAllowed:
            raise   # hard security stop — never softened into a 'failed' result
        except Exception as exc:  # noqa: BLE001 — capture audit + structured result, don't escape
            result.update(message=f"Apply error: {exc}")
            return _finalize(page, shot_dir, result)
        finally:
            context.close()
            browser.close()


def _finalize(page, shot_dir: Path, result: dict) -> dict:
    """Screenshot for the audit record — only on PII-free states (the confirmation page) unless
    debug screenshots are explicitly enabled (filled forms contain PII and aren't captured)."""
    if result.get("status") != "submitted" and not settings.apply_debug_screenshots:
        return result
    try:
        stamp = hashlib.sha1(f"{page.url}:{result['status']}".encode()).hexdigest()[:12]
        path = shot_dir / f"apply_{result['status']}_{stamp}.png"
        page.screenshot(path=str(path), full_page=True)
        result["screenshot_path"] = str(path)
    except Exception:
        pass
    return result
