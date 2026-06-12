"""Assemble the tailoring-workflow result into a single ready-to-use markdown doc."""
import json
import sys
from pathlib import Path

src = sys.argv[1]
dest_name = sys.argv[2] if len(sys.argv) > 2 else "application_packs.md"
packs = json.load(open(src, encoding="utf-8"))["result"]["packs"]

ORDER = {"strong": 0, "possible": 1, "stretch": 2, "reach": 3}
packs.sort(key=lambda p: ORDER.get(p["pack"].get("realistic_fit", "reach"), 9))

ICON = {"strong": "🟢", "possible": "🟡", "stretch": "🟠", "reach": "🔴"}
lines = ["# Tailored application packs — Hemanth Kumar V",
         "", "Honest, new-grad-lens tailoring. Each pack uses only your real experience. "
         "Apply via the link, paste the tailored summary/bullets/note, and answer the likely "
         "questions in your own words.", "",
         "## Priority order (best realistic fit first)", ""]
for p in packs:
    fit = p["pack"].get("realistic_fit", "?")
    lines.append(f"- {ICON.get(fit,'')} **{fit.upper()}** — {p['title']} @ {p['company']} ({p['location']})")
lines.append("\n---\n")

for p in packs:
    k = p["pack"]
    fit = k.get("realistic_fit", "?")
    lines += [f"## {ICON.get(fit,'')} {p['title']} @ {p['company']}",
              f"**Fit: {fit.upper()}** · {p['location']} · [Apply]({p['url']})", "",
              f"_{k.get('fit_reason','')}_", "",
              "**Tailored summary (paste at top of resume / application):**",
              f"> {k.get('tailored_summary','')}", "",
              "**Lead with these skills:** " + ", ".join(k.get("emphasize_skills", [])), "",
              "**Resume bullets (from your real experience):**"]
    lines += [f"- {b}" for b in k.get("suggested_bullets", [])]
    if k.get("gaps_to_address"):
        lines += ["", "**Gaps to address honestly:**"]
        lines += [f"- {g}" for g in k["gaps_to_address"]]
    if k.get("likely_questions"):
        lines += ["", "**Likely interview questions:**"]
        lines += [f"- {q}" for q in k["likely_questions"]]
    lines += ["", "**Cover note (paste-ready):**", f"> {k.get('short_note','')}", "", "---", ""]

dest = Path(__file__).resolve().parent.parent / "storage" / dest_name
dest.write_text("\n".join(lines), encoding="utf-8")

# Console summary
print(f"{'FIT':10} {'TITLE':46} COMPANY")
for p in packs:
    print(f"{p['pack'].get('realistic_fit',''):10} {p['title'][:46]:46} {p['company']}")
print(f"\nWrote {len(packs)} packs -> {dest}")
