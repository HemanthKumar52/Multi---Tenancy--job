"""USAJobs (US federal) — official API, requires a free API key + your registered email.

GET https://data.usajobs.gov/api/search with headers: Host, User-Agent (your email), Authorization-Key.
"""
from __future__ import annotations

from app.config import settings
from app.services.discovery.base import JobPosting, html_to_text, polite_get


def available() -> bool:
    return bool(settings.usajobs_api_key and settings.usajobs_email)


def parse(payload: dict) -> list[JobPosting]:
    out: list[JobPosting] = []
    for item in (payload.get("SearchResult") or {}).get("SearchResultItems", []):
        d = item.get("MatchedObjectDescriptor", {})
        summary = ((d.get("UserArea") or {}).get("Details") or {}).get("JobSummary", "")
        out.append(JobPosting(
            source="usajobs", ats_vendor="external",
            external_id=str(d.get("PositionID", "")),
            company=d.get("OrganizationName", ""),
            title=d.get("PositionTitle", ""),
            location=d.get("PositionLocationDisplay", ""),
            description=html_to_text(summary),
            url=d.get("PositionURI", ""),
            posted_at=d.get("PublicationStartDate"),
        ))
    return out


def fetch(what: str, where: str = "", *, timeout: float = 15.0) -> list[JobPosting]:
    if not available():
        raise RuntimeError("USAJobs not configured (USAJOBS_API_KEY + USAJOBS_EMAIL)")
    headers = {
        "Host": "data.usajobs.gov",
        "User-Agent": settings.usajobs_email,
        "Authorization-Key": settings.usajobs_api_key,
    }
    params = {"Keyword": what}
    if where:
        params["LocationName"] = where
    resp = polite_get("https://data.usajobs.gov/api/search", params=params,
                      headers=headers, timeout=timeout)
    return parse(resp.json())
