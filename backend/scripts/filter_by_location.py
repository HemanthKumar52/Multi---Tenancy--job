"""Filter already-discovered jobs to the user's locations: international/remote + India only in
Karnataka, Tamil Nadu, Kerala, Andhra Pradesh. Reuses saved JSON (no network). Writes targeted_jobs.csv.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

STORAGE = Path(__file__).resolve().parent.parent / "storage"

PREFERRED_IN = ("karnataka", "bengaluru", "bangalore", "mysuru", "mysore",
                "tamil nadu", "tamilnadu", "chennai", "coimbatore", "madurai",
                "kerala", "kochi", "cochin", "trivandrum", "thiruvananthapuram", "kozhikode", "calicut",
                "andhra", "visakhapatnam", "vizag", "vijayawada", "amaravati", "tirupati", "guntur")
OTHER_IN = ("india", "mumbai", "maharashtra", "new delhi", "delhi", "gurgaon", "gurugram", "noida",
            "pune", "kolkata", "hyderabad", "telangana", "ahmedabad", "jaipur", "indore", "chandigarh")


def keep(location: str) -> bool:
    loc = (location or "").lower()
    if any(p in loc for p in PREFERRED_IN):
        return True                       # India, preferred state/city
    if any(o in loc for o in OTHER_IN):
        return False                      # India, but not a preferred state
    return True                           # international / remote / global


def load(name: str) -> list[dict]:
    p = STORAGE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def main() -> int:
    rows = load("entry_jobs.json") + load("found_jobs.json")
    seen, merged = set(), []
    for j in rows:
        key = f"{(j.get('company') or '').lower()}::{(j.get('title') or '').lower()}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(j)

    targeted = [j for j in merged if keep(j.get("location", ""))]
    targeted.sort(key=lambda j: j.get("fit", 0), reverse=True)

    with (STORAGE / "targeted_jobs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fit", "title", "company", "location", "source", "apply_url"])
        for j in targeted:
            w.writerow([j.get("fit"), j.get("title"), j.get("company"), j.get("location"),
                        j.get("source"), j.get("url")])

    intl = [j for j in targeted if not any(p in (j.get("location") or "").lower() for p in PREFERRED_IN)]
    india = [j for j in targeted if any(p in (j.get("location") or "").lower() for p in PREFERRED_IN)]
    print(f"Merged {len(merged)} unique jobs -> {len(targeted)} match your locations "
          f"({len(intl)} international/remote, {len(india)} in your India states)\n")

    print("Top 30 location-matched roles:\n")
    for i, j in enumerate(targeted[:30], 1):
        loc = (j.get("location") or "-")[:24]
        print(f"{i:2}. [{j.get('fit'):>3}] {j.get('title','')[:42]:42} {(j.get('company') or '-')[:16]:16} {loc:24}")
    if india:
        print("\nIn your India states:")
        for j in india[:12]:
            print(f"   [{j.get('fit'):>3}] {j.get('title','')[:42]:42} {(j.get('company') or '-')[:16]:16} {j.get('location','')}")
    print(f"\nSaved -> {STORAGE/'targeted_jobs.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
