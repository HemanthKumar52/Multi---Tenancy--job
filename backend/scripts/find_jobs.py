"""Live job hunt for a real resume: parse -> discover (real public boards) -> match -> rank.
No Anthropic key needed (offline matcher). Saves a ranked queue to storage/found_jobs.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.services.discovery.aggregator import discover
from app.services.matching.matcher import match
from app.services.resume.parser import parse_resume

RESUME = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\venka\Downloads\Hemanth Kumar V.pdf"

# Real, public, no-auth sources — global + remote coverage.
SOURCES = [
    {"vendor": "remotive", "search": "software engineer", "limit": 80},
    {"vendor": "remotive", "search": "full stack", "limit": 60},
    {"vendor": "remotive", "search": "react", "limit": 40},
    {"vendor": "remoteok"},
    {"vendor": "arbeitnow"},
    {"vendor": "jobicy", "industry": "dev"},
    # A few ATS-direct boards (skipped automatically if a token doesn't resolve):
    {"vendor": "greenhouse", "board": "gitlab"},
    {"vendor": "greenhouse", "board": "stripe"},
    {"vendor": "lever", "board": "voiceflow", "company": "voiceflow"},
]

SWE_KEYWORDS = (
    "software engineer", "software developer", "backend", "back-end", "frontend", "front-end",
    "full stack", "full-stack", "fullstack", "react", "node", "flutter", "mobile",
    "web developer", "application developer", "sde", "engineer ii", "engineer i", "developer",
    "typescript", "javascript", "python developer",
)


def is_swe(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in SWE_KEYWORDS)


def main() -> int:
    print(f"Parsing resume: {RESUME}")
    profile = parse_resume(RESUME)
    print(f"  -> {profile.name or '(name not parsed)'} | skills detected: {len(profile.skills)}")

    print(f"\nDiscovering from {len(SOURCES)} live sources...")
    postings = discover(SOURCES)
    print(f"  -> {len(postings)} total postings fetched")

    swe = [p for p in postings if is_swe(p.title)]
    print(f"  -> {len(swe)} software-engineering roles after filtering")

    ranked = []
    for p in swe:
        m = match(profile, p.description, p.title)
        ranked.append((m.score, m, p))
    ranked.sort(key=lambda x: x[0], reverse=True)

    out = []
    for score, m, p in ranked:
        out.append({
            "fit": score, "title": p.title, "company": p.company, "location": p.location,
            "source": p.source, "ats_vendor": p.ats_vendor, "url": p.url,
            "matched_skills": m.matched_skills[:8], "missing_skills": m.missing_skills[:6],
            "description": (p.description or "")[:1600],
        })

    storage = Path(__file__).resolve().parent.parent / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    (storage / "found_jobs.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    # A ready-to-apply tracker (CSV) of every match.
    import csv
    with (storage / "found_jobs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fit", "title", "company", "location", "source", "apply_url"])
        for j in out:
            w.writerow([j["fit"], j["title"], j["company"], j["location"], j["source"], j["url"]])

    # Small input file for the tailoring agents (top 12, descriptions trimmed).
    (storage / "top_for_tailoring.json").write_text(
        json.dumps([{k: j[k] for k in ("fit", "title", "company", "location", "url",
                                        "matched_skills", "missing_skills", "description")}
                    for j in out[:12]], indent=2), encoding="utf-8")
    dest = storage / "found_jobs.json"

    print(f"\nTop {min(25, len(out))} matches for {profile.name or 'you'}:\n")
    for i, j in enumerate(out[:25], 1):
        loc = (j["location"] or "—")[:28]
        print(f"{i:2}. [{j['fit']:>3}] {j['title'][:46]:46}  {(j['company'] or '—')[:20]:20} {loc:28} {j['source']}")
    print(f"\nSaved full ranked list ({len(out)} jobs) -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
