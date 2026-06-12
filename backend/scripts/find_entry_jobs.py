"""Early-career-targeted job hunt: bias search to junior/grad/intern, exclude senior/staff,
rank by fit with an early-career boost. Saves entry_jobs.csv + entry_top_for_tailoring.json.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from app.services.discovery.aggregator import discover
from app.services.matching.matcher import match
from app.services.resume.parser import parse_resume

RESUME = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\venka\Downloads\Hemanth Kumar V.pdf"

SOURCES = [
    {"vendor": "remotive", "search": "junior", "limit": 60},
    {"vendor": "remotive", "search": "graduate", "limit": 40},
    {"vendor": "remotive", "search": "intern", "limit": 40},
    {"vendor": "remotive", "search": "frontend developer", "limit": 50},
    {"vendor": "remotive", "search": "full stack developer", "limit": 50},
    {"vendor": "remoteok"},
    {"vendor": "arbeitnow"},
    {"vendor": "jobicy", "industry": "dev"},
    {"vendor": "greenhouse", "board": "stripe"},
]

SWE = ("software engineer", "software developer", "backend", "frontend", "front-end", "full stack",
       "full-stack", "fullstack", "react", "node", "flutter", "mobile", "web developer",
       "application developer", "developer", "engineer", "sde")
EARLY = ("junior", "jr ", "jr.", "graduate", "grad ", "new grad", "new-grad", "intern", "entry",
         "entry-level", "early career", "associate", "trainee", "apprentice", "level 1", "i ")
SENIOR = ("senior", "sr.", "sr ", "staff", "lead ", "principal", "architect", "head of", "director",
          "manager", " vp", "iii", " ii", "10+", "8+ years", "distinguished")


def is_swe(t: str) -> bool:
    return any(k in t for k in SWE)


def is_senior(t: str) -> bool:
    return any(k in t for k in SENIOR)


def is_early(t: str) -> bool:
    return any(k in t for k in EARLY)


def main() -> int:
    profile = parse_resume(RESUME)
    print(f"Profile: {profile.name} | discovering early-career roles from {len(SOURCES)} sources...")
    postings = discover(SOURCES)
    print(f"  -> {len(postings)} fetched")

    kept = []
    for p in postings:
        t = p.title.lower()
        if is_swe(t) and not is_senior(t):
            kept.append(p)
    print(f"  -> {len(kept)} non-senior software roles")

    ranked = []
    for p in kept:
        m = match(profile, p.description, p.title)
        early = is_early(p.title.lower())
        boosted = min(100, m.score + (12 if early else 0))   # nudge true early-career up
        ranked.append((early, boosted, m, p))
    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)

    out = []
    for early, boosted, m, p in ranked:
        out.append({"fit": boosted, "early_career": early, "title": p.title, "company": p.company,
                    "location": p.location, "source": p.source, "url": p.url,
                    "matched_skills": m.matched_skills[:8], "missing_skills": m.missing_skills[:6],
                    "description": (p.description or "")[:1400]})

    storage = Path(__file__).resolve().parent.parent / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    (storage / "entry_jobs.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    with (storage / "entry_jobs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fit", "early_career", "title", "company", "location", "source", "apply_url"])
        for j in out:
            w.writerow([j["fit"], j["early_career"], j["title"], j["company"], j["location"],
                        j["source"], j["url"]])
    (storage / "entry_top_for_tailoring.json").write_text(
        json.dumps([{k: j[k] for k in ("fit", "title", "company", "location", "url",
                                        "matched_skills", "missing_skills", "description")}
                    for j in out[:12]], indent=2), encoding="utf-8")

    print(f"\nTop {min(25, len(out))} early-career matches:\n")
    for i, j in enumerate(out[:25], 1):
        tag = "EARLY" if j["early_career"] else "     "
        print(f"{i:2}. [{j['fit']:>3}] {tag} {j['title'][:44]:44} {(j['company'] or '-')[:18]:18} {(j['location'] or '-')[:22]}")
    print(f"\nSaved {len(out)} jobs -> {storage/'entry_jobs.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
