"""Workable public job-board API.

GET https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true  (no auth, CORS-open)
Returns {name, description, jobs:[...]}. ``details=true`` is required to include the HTML
``description`` per job. (The older www.workable.com/api endpoint is deprecated/302s.)

Workable has no public submit API, so postings are discovery-only — the apply step sends the
user to the posting's own ``application_url``.
"""
from __future__ import annotations

from app.services.discovery.base import JobPosting, html_to_text, polite_get

_BASE = "https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true"


def _location(job: dict) -> str:
    if job.get("telecommuting"):
        return "Remote"
    locs = job.get("locations") or []
    if locs:
        loc = locs[0]
        parts = [loc.get("city"), loc.get("region"), loc.get("country")]
    else:
        parts = [job.get("city"), job.get("state"), job.get("country")]
    return ", ".join(p for p in parts if p)


def parse(payload: dict, slug: str) -> list[JobPosting]:
    company = payload.get("name") or slug
    out: list[JobPosting] = []
    for j in payload.get("jobs", []):
        out.append(JobPosting(
            source="workable",
            ats_vendor="workable",          # discovery-only (no public submit API)
            external_id=str(j.get("shortcode") or j.get("code") or ""),
            company=company,
            title=j.get("title", ""),
            location=_location(j),
            description=html_to_text(j.get("description", "")),
            url=j.get("application_url") or j.get("url", ""),
            posted_at=j.get("published_on") or j.get("created_at"),
        ))
    return out


def fetch(slug: str, *, timeout: float = 15.0) -> list[JobPosting]:
    payload = polite_get(_BASE.format(slug=slug), timeout=timeout).json()
    return parse(payload, slug)
