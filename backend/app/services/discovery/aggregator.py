"""Fan out across discovery sources, normalize, and de-duplicate.

A "source spec" is a small dict the caller (or a saved search) provides, e.g.:
    {"vendor": "greenhouse", "board": "stripe"}
    {"vendor": "lever", "company": "netflix"}
    {"vendor": "adzuna", "what": "python developer", "where": "remote", "country": "us"}
"""
from __future__ import annotations

from app.services.discovery import adzuna, ashby, greenhouse, lever, workable
from app.services.discovery.base import JobPosting

_VENDORS = {
    "greenhouse": lambda s: greenhouse.fetch(s["board"]),
    "lever": lambda s: lever.fetch(s["company"]),
    "ashby": lambda s: ashby.fetch(s["board"]),
    "workable": lambda s: workable.fetch(s["slug"]),
    "adzuna": lambda s: adzuna.fetch(s["what"], s.get("where", ""), country=s.get("country", "gb")),
}


def discover(source_specs: list[dict]) -> list[JobPosting]:
    seen: set[str] = set()
    results: list[JobPosting] = []
    for spec in source_specs:
        vendor = spec.get("vendor")
        fn = _VENDORS.get(vendor)
        if not fn:
            continue
        try:
            postings = fn(spec)
        except Exception:
            # A flaky/unauthorized source must not sink the whole run.
            continue
        for p in postings:
            if p.dedup_key in seen:
                continue
            seen.add(p.dedup_key)
            results.append(p)
    return results
