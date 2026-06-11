"""Ashby public job board API.

GET https://api.ashbyhq.com/posting-api/job-board/{board_name}?includeCompensation=true
"""
from __future__ import annotations

from app.services.discovery.base import JobPosting, html_to_text, polite_get

_BASE = "https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"


def fetch(board_name: str, *, timeout: float = 15.0) -> list[JobPosting]:
    url = _BASE.format(board=board_name)
    jobs = polite_get(url, timeout=timeout).json().get("jobs", [])
    out: list[JobPosting] = []
    for j in jobs:
        out.append(JobPosting(
            source="ashby",
            ats_vendor="ashby",
            external_id=str(j.get("id")),
            company=board_name,
            title=j.get("title", ""),
            location=j.get("location", ""),
            description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml", "")),
            url=j.get("applyUrl") or j.get("jobUrl", ""),
            posted_at=j.get("publishedAt"),
        ))
    return out
