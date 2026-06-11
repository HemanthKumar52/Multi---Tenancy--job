"""Fan out across discovery sources, normalize, and de-duplicate.

A "source spec" is a small dict the caller (or a saved search) provides, e.g.:
    {"vendor": "greenhouse", "board": "stripe"}
    {"vendor": "lever", "company": "netflix"}
    {"vendor": "adzuna", "what": "python developer", "where": "remote", "country": "us"}
"""
from __future__ import annotations

from app.services.discovery import (
    adzuna,
    apify,
    ashby,
    greenhouse,
    lever,
    remote_boards,
    usajobs,
    workable,
)
from app.services.discovery.base import JobPosting

# Each entry maps a source spec dict -> a list[JobPosting]. ATS-direct boards support apply;
# the remote/aggregator sources are discovery-only.
_VENDORS = {
    # ATS-direct (apply-capable)
    "greenhouse": lambda s: greenhouse.fetch(s["board"]),
    "lever": lambda s: lever.fetch(s["company"]),
    "ashby": lambda s: ashby.fetch(s["board"]),
    "workable": lambda s: workable.fetch(s["slug"]),
    # Aggregators / remote / international (discovery-only)
    "adzuna": lambda s: adzuna.fetch(s["what"], s.get("where", ""), country=s.get("country", "gb")),
    "remotive": lambda s: remote_boards.fetch_remotive(s.get("search", ""), limit=s.get("limit", 50)),
    "remoteok": lambda s: remote_boards.fetch_remoteok(),
    "arbeitnow": lambda s: remote_boards.fetch_arbeitnow(),
    "themuse": lambda s: remote_boards.fetch_themuse(s.get("category", ""), page=s.get("page", 0)),
    "jobicy": lambda s: remote_boards.fetch_jobicy(geo=s.get("geo", ""), industry=s.get("industry", "")),
    "usajobs": lambda s: usajobs.fetch(s["what"], s.get("where", "")),
    "apify": lambda s: apify.fetch(s["actor"], s.get("input", {}), source_label=s.get("label")),
}

# Sources whose results are discovery-only (no auto-apply); useful for the UI to label them.
DISCOVERY_ONLY = {"adzuna", "remotive", "remoteok", "arbeitnow", "themuse", "jobicy", "usajobs", "apify"}


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
