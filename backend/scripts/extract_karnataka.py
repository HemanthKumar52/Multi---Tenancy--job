"""Extract the Karnataka (Bengaluru/Bangalore) jobs from the saved discovery, with url + description."""
import json
from pathlib import Path

STORAGE = Path(__file__).resolve().parent.parent / "storage"
rows = []
for name in ("entry_jobs.json", "found_jobs.json"):
    p = STORAGE / name
    if p.exists():
        rows += json.loads(p.read_text(encoding="utf-8"))

seen, out = set(), []
for j in rows:
    loc = (j.get("location") or "").lower()
    if "bengaluru" in loc or "bangalore" in loc:
        key = (j.get("company", ""), j.get("title", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": j.get("title"), "company": j.get("company"),
                    "location": j.get("location"), "url": j.get("url"),
                    "description": (j.get("description") or "")[:900]})

(STORAGE / "karnataka_jobs.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
for j in out:
    print(f"- {j['title']} @ {j['company']} ({j['location']})\n  {j['url']}")
print(f"\n{len(out)} Karnataka jobs -> {STORAGE/'karnataka_jobs.json'}")
