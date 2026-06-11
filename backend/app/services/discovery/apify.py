"""Apify connector — run any Apify job-scraper actor (LinkedIn, Indeed, Glassdoor, …).

Gated behind ``APIFY_TOKEN``. Postings are **discovery-only**: results are surfaced for the user
to review and apply to via the original link — we never auto-apply on these aggregated sources
(consistent with the legal-first stance; those sites' ToS restrict automated submission).

Uses the run-sync endpoint which runs the actor and returns dataset items in one call.
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.services.discovery.base import JobPosting, html_to_text

_RUN_SYNC = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def available() -> bool:
    return bool(settings.apify_token)


def _first(d: dict, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return default


def parse(items: list, source_label: str = "apify") -> list[JobPosting]:
    """Best-effort mapping — Apify actors vary, so we probe common field names."""
    out: list[JobPosting] = []
    for j in items if isinstance(items, list) else []:
        title = _first(j, "title", "position", "jobTitle", "name")
        if not title:
            continue
        desc = _first(j, "description", "descriptionText", "jobDescription", "summary")
        out.append(JobPosting(
            source=source_label, ats_vendor="external",
            external_id=str(_first(j, "id", "jobId", "url", default="")),
            company=_first(j, "company", "companyName", "company_name", "employer"),
            title=title,
            location=_first(j, "location", "place", "jobLocation", default="Remote"),
            description=html_to_text(desc),
            url=_first(j, "url", "jobUrl", "link", "applyUrl"),
            posted_at=_first(j, "postedAt", "publishedAt", "date", "postedDate", default=None) or None,
        ))
    return out


def fetch(actor_id: str, run_input: dict | None = None, *,
          source_label: str | None = None, timeout: float = 120.0) -> list[JobPosting]:
    if not available():
        raise RuntimeError("Apify not configured (set APIFY_TOKEN)")
    url = _RUN_SYNC.format(actor=actor_id)
    resp = httpx.post(url, params={"token": settings.apify_token},
                      json=run_input or {}, timeout=timeout,
                      headers={"User-Agent": settings.user_agent})
    resp.raise_for_status()
    return parse(resp.json(), source_label or f"apify:{actor_id}")
