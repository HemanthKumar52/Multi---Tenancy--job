"""SAFE live demo: drive the engine against a REAL Greenhouse application form.

It navigates to a real public Greenhouse job, locates the real fields our adapter targets, fills
them with obviously-fake demo data, screenshots the filled form, and STOPS before submit.
It does NOT submit, does NOT upload a real resume, and uses no real PII — so no application is
ever sent to any company. This proves the automation matches the live DOM.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from app.config import settings
from app.services.apply.playwright_common import host_allowed
from app.services.discovery import greenhouse

STORAGE = Path(__file__).resolve().parent.parent / "storage"
SHOT = STORAGE / "demo_real_greenhouse.png"
BOARDS = ["gitlab", "figma", "discord", "brex", "ramp", "airtable", "gusto", "mongodb",
          "cloudflare", "anthropic", "databricks", "robinhood"]


def find_job():
    for board in BOARDS:
        try:
            jobs = greenhouse.fetch(board)
        except Exception:
            continue
        for j in jobs:
            host = (urlparse(j.url).hostname or "").lower()
            if "greenhouse.io" in host and host_allowed(j.url):
                return j
    return None


def main() -> int:
    job = find_job()
    if not job:
        print("Could not reach a live Greenhouse board right now (network/boards unavailable).")
        return 1
    print(f"Live job: {job.title} @ {job.company}\n  {job.url}\n")

    def present(pg, sel):
        try:
            return pg.locator(sel).first.count() > 0
        except Exception:
            return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=settings.user_agent)
        pg = ctx.new_page()
        pg.set_default_timeout(30000)
        pg.goto(job.url, wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(1500)

        # Reveal the form if it's behind an "Apply" button.
        if not present(pg, "#first_name"):
            for name in ("Apply for this job", "Apply now", "Apply"):
                for getter in (pg.get_by_role("button", name=re.compile(name, re.I)),
                               pg.get_by_role("link", name=re.compile(name, re.I))):
                    try:
                        if getter.first.count() > 0:
                            getter.first.click(timeout=5000)
                            pg.wait_for_timeout(2000)
                            break
                    except Exception:
                        continue
                if present(pg, "#first_name"):
                    break

        fields = {
            "first_name": "#first_name", "last_name": "#last_name", "email": "#email",
            "phone": "#phone", "resume_upload": "#resume, input[type='file']",
            "submit_button": "button:has-text('Submit application'), button[type='submit']",
        }
        found = {k: present(pg, sel) for k, sel in fields.items()}

        # Fill identity fields that exist with OBVIOUSLY FAKE demo data (never real PII, never submit).
        for sel, val in (("#first_name", "Demo"), ("#last_name", "Applicant"),
                         ("#email", "demo@example.invalid"), ("#phone", "+10000000000")):
            try:
                if present(pg, sel):
                    pg.locator(sel).first.fill(val, timeout=4000)
            except Exception:
                pass

        pg.screenshot(path=str(SHOT), full_page=True)
        browser.close()

    print("Real fields our adapter located on the LIVE form:")
    for k, v in found.items():
        print(f"   {'FOUND ' if v else 'missing'}  {k}")
    print(f"\nScreenshot of the filled (NOT submitted) real form -> {SHOT}")
    print("No application was submitted. Fake demo data only. No resume uploaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
