"""Adzuna aggregator API (global coverage). Requires free app id/key.

GET https://api.adzuna.com/v1/api/jobs/{country}/search/1?app_id=&app_key=&what=&where=
"""
from __future__ import annotations

from app.config import settings
from app.services.discovery.base import JobPosting, html_to_text, polite_get

_BASE = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


def available() -> bool:
    return bool(settings.adzuna_app_id and settings.adzuna_app_key)


def fetch(what: str, where: str = "", *, country: str = "gb", page: int = 1,
          results: int = 25, timeout: float = 15.0) -> list[JobPosting]:
    if not available():
        raise RuntimeError("Adzuna keys not configured (ADZUNA_APP_ID / ADZUNA_APP_KEY)")
    url = _BASE.format(country=country, page=page)
    params = {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key,
        "what": what,
        "where": where,
        "results_per_page": results,
        "content-type": "application/json",
    }
    out: list[JobPosting] = []
    for j in polite_get(url, params=params, timeout=timeout).json().get("results", []):
        out.append(JobPosting(
            source="adzuna",
            ats_vendor="external",          # aggregator -> external apply, discovery-only
            external_id=str(j.get("id")),
            company=(j.get("company") or {}).get("display_name", ""),
            title=j.get("title", ""),
            location=(j.get("location") or {}).get("display_name", ""),
            description=html_to_text(j.get("description", "")),
            url=j.get("redirect_url", ""),
            posted_at=j.get("created"),
        ))
    return out
