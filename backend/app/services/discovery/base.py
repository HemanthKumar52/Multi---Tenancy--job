"""Shared types + helpers for job discovery sources."""
from __future__ import annotations

import html
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.services.common.text import extract_skills

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")

# ── ToS-respectful HTTP ──────────────────────────────────────────────────────
# Honest identifiable UA, a low per-host rate limit (>= min_interval between hits to a host),
# and exponential backoff that honors Retry-After on 429/5xx. No stealth, no UA spoofing.
_last_hit: dict[str, float] = {}
_rate_lock = threading.Lock()


def polite_get(url: str, *, params: dict | None = None, timeout: float = 15.0,
               retries: int = 2, min_interval: float = 1.0) -> httpx.Response:
    host = (urlparse(url).hostname or "").lower()
    # Reserve this host's slot *inside* the lock, then sleep *outside* it — so pacing one host
    # never serializes requests to other hosts, and concurrent threads don't stampede on a stale
    # timestamp.
    with _rate_lock:
        now = time.monotonic()
        wait = min_interval - (now - _last_hit.get(host, 0.0))
        _last_hit[host] = now + max(wait, 0.0)
    if wait > 0:
        time.sleep(wait)

    headers = {"User-Agent": settings.user_agent}
    resp: httpx.Response | None = None
    for attempt in range(retries + 1):
        resp = httpx.get(url, params=params, timeout=timeout, headers=headers,
                         follow_redirects=True)
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            retry_after = resp.headers.get("Retry-After")
            delay = float(retry_after) if (retry_after or "").isdigit() else 1.5 * (attempt + 1)
            time.sleep(min(delay, 10.0))
            continue
        break
    # Re-stamp so the next caller paces from the actual last network hit (incl. retry time).
    with _rate_lock:
        _last_hit[host] = time.monotonic()
    assert resp is not None
    resp.raise_for_status()
    return resp


def html_to_text(raw: str) -> str:
    """Cheap HTML -> text for job descriptions (no bs4 dependency)."""
    if not raw:
        return ""
    text = raw.replace("</p>", "\n").replace("<br>", "\n").replace("<br/>", "\n").replace("</li>", "\n")
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    return _WS_RE.sub("\n\n", text).strip()


@dataclass
class JobPosting:
    source: str                      # 'greenhouse' | 'lever' | 'ashby' | 'adzuna' | ...
    ats_vendor: str                  # which ATS the apply flow targets
    external_id: str
    company: str
    title: str
    location: str
    description: str
    url: str
    posted_at: str | None = None
    skills: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.skills:
            self.skills = extract_skills(f"{self.title}\n{self.description}")

    @property
    def dedup_key(self) -> str:
        return f"{self.company.lower().strip()}::{self.title.lower().strip()}"

    def to_dict(self) -> dict:
        return asdict(self)
