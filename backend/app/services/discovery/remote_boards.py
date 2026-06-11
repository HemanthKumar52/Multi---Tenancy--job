"""Free public remote/international job-board APIs (no auth).

Remotive · RemoteOK · Arbeitnow · The Muse · Jobicy. All are discovery-only — the user applies
via the original link (ats_vendor="external"). Each source has a pure ``parse_*`` (for tests) and
a ``fetch_*`` that pages through ``polite_get`` (honest UA + rate limit).
"""
from __future__ import annotations

from app.services.discovery.base import JobPosting, html_to_text, polite_get


def _post(source: str, **kw) -> JobPosting:
    return JobPosting(source=source, ats_vendor="external", **kw)


# ── Remotive (https://remotive.com/api/remote-jobs) ──────────────────────────
def parse_remotive(payload: dict) -> list[JobPosting]:
    out = []
    for j in payload.get("jobs", []):
        out.append(_post("remotive", external_id=str(j.get("id", "")),
                         company=j.get("company_name", ""), title=j.get("title", ""),
                         location=j.get("candidate_required_location") or "Remote",
                         description=html_to_text(j.get("description", "")),
                         url=j.get("url", ""), posted_at=j.get("publication_date")))
    return out


def fetch_remotive(search: str = "", *, limit: int = 50) -> list[JobPosting]:
    params = {"limit": limit}
    if search:
        params["search"] = search
    return parse_remotive(polite_get("https://remotive.com/api/remote-jobs", params=params).json())


# ── RemoteOK (https://remoteok.com/api) — first list item is legal metadata ──
def parse_remoteok(payload: list) -> list[JobPosting]:
    out = []
    for j in payload if isinstance(payload, list) else []:
        if not j.get("position"):      # skips the leading {"legal": ...} header element
            continue
        out.append(_post("remoteok", external_id=str(j.get("id", "")),
                         company=j.get("company", ""), title=j.get("position", ""),
                         location=j.get("location") or "Remote",
                         description=html_to_text(j.get("description", "")),
                         url=j.get("url", ""), posted_at=j.get("date")))
    return out


def fetch_remoteok() -> list[JobPosting]:
    return parse_remoteok(polite_get("https://remoteok.com/api").json())


# ── Arbeitnow (https://www.arbeitnow.com/api/job-board-api) — international ───
def parse_arbeitnow(payload: dict) -> list[JobPosting]:
    out = []
    for j in payload.get("data", []):
        loc = j.get("location") or ("Remote" if j.get("remote") else "")
        out.append(_post("arbeitnow", external_id=str(j.get("slug", "")),
                         company=j.get("company_name", ""), title=j.get("title", ""),
                         location=loc, description=html_to_text(j.get("description", "")),
                         url=j.get("url", ""), posted_at=str(j.get("created_at", "")) or None))
    return out


def fetch_arbeitnow() -> list[JobPosting]:
    return parse_arbeitnow(polite_get("https://www.arbeitnow.com/api/job-board-api").json())


# ── The Muse (https://www.themuse.com/api/public/jobs) ───────────────────────
def parse_themuse(payload: dict) -> list[JobPosting]:
    out = []
    for j in payload.get("results", []):
        locs = ", ".join(n for loc in (j.get("locations") or []) if (n := loc.get("name")))
        out.append(_post("themuse", external_id=str(j.get("id", "")),
                         company=(j.get("company") or {}).get("name", ""),
                         title=j.get("name", ""), location=locs,
                         description=html_to_text(j.get("contents", "")),
                         url=(j.get("refs") or {}).get("landing_page", ""),
                         posted_at=j.get("publication_date")))
    return out


def fetch_themuse(category: str = "", *, page: int = 0) -> list[JobPosting]:
    params = {"page": page}
    if category:
        params["category"] = category
    return parse_themuse(polite_get("https://www.themuse.com/api/public/jobs", params=params).json())


# ── Jobicy (https://jobicy.com/api/v2/remote-jobs) ───────────────────────────
def parse_jobicy(payload: dict) -> list[JobPosting]:
    out = []
    for j in payload.get("jobs", []):
        out.append(_post("jobicy", external_id=str(j.get("id", "")),
                         company=j.get("companyName", ""), title=j.get("jobTitle", ""),
                         location=j.get("jobGeo") or "Remote",
                         description=html_to_text(j.get("jobDescription", "")),
                         url=j.get("url", ""), posted_at=j.get("pubDate")))
    return out


def fetch_jobicy(*, count: int = 50, geo: str = "", industry: str = "") -> list[JobPosting]:
    params: dict = {"count": count}
    if geo:
        params["geo"] = geo
    if industry:
        params["industry"] = industry
    return parse_jobicy(polite_get("https://jobicy.com/api/v2/remote-jobs", params=params).json())
