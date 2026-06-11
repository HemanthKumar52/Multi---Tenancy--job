"""Lever public postings API.

GET https://api.lever.co/v0/postings/{company}?mode=json  (no auth, public board)
"""
from __future__ import annotations

from app.services.discovery.base import JobPosting, html_to_text, polite_get

_BASE = "https://api.lever.co/v0/postings/{company}?mode=json"


def fetch(company: str, *, timeout: float = 15.0) -> list[JobPosting]:
    url = _BASE.format(company=company)
    out: list[JobPosting] = []
    for j in polite_get(url, timeout=timeout).json():
        cats = j.get("categories") or {}
        out.append(JobPosting(
            source="lever",
            ats_vendor="lever",
            external_id=str(j.get("id")),
            company=company,
            title=j.get("text", ""),
            location=cats.get("location", ""),
            description=j.get("descriptionPlain") or html_to_text(j.get("description", "")),
            url=j.get("hostedUrl", ""),
            posted_at=str(j.get("createdAt")) if j.get("createdAt") else None,
        ))
    return out
