"""Greenhouse public job board API.

GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
No auth required — these are public boards companies *want* surfaced. Automation-friendly.
"""
from __future__ import annotations

from app.services.discovery.base import JobPosting, html_to_text, polite_get

_BASE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def fetch(board_token: str, *, timeout: float = 15.0) -> list[JobPosting]:
    url = _BASE.format(token=board_token)
    jobs = polite_get(url, timeout=timeout).json().get("jobs", [])
    out: list[JobPosting] = []
    for j in jobs:
        out.append(JobPosting(
            source="greenhouse",
            ats_vendor="greenhouse",
            external_id=str(j.get("id")),
            company=board_token,
            title=j.get("title", ""),
            location=(j.get("location") or {}).get("name", ""),
            description=html_to_text(j.get("content", "")),
            url=j.get("absolute_url", ""),
            posted_at=j.get("updated_at"),
        ))
    return out
