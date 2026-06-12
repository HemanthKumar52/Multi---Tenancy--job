"""Demonstrate the REAL format-preserving engine on Hemanth's actual resume.

Converts his PDF -> DOCX (pdf2docx), parses it, generates a truthful tailored edit set for a target
job (offline engine — no API key), writes the edits back into the converted layout, and reports the
ATS analysis. Honest about PDF->DOCX fidelity.
"""
from __future__ import annotations

from pathlib import Path

from pdf2docx import Converter

from app.services.resume import ats as ats_mod
from app.services.resume import docx_engine
from app.services.resume.parser import parse_docx
from app.services.tailoring import tailor

PDF = r"C:\Users\venka\Downloads\Hemanth Kumar V.pdf"
STORAGE = Path(__file__).resolve().parent.parent / "storage"
CONV = STORAGE / "hemanth_resume.docx"
OUT = STORAGE / "hemanth_resume_stripe_internal_systems.docx"

JD = ("Stripe Internal Systems team: enable effective financial decisions through reliable data, "
      "efficiency and automation. Supports Marketing, Sales, Accounting, Tax, Finance, FinOps and "
      "Treasury. Build internal tools, data insights, and process-improvement automation. "
      "Python, Node.js, NestJS, PostgreSQL, microservices, data-driven workflow automation.")


def main() -> int:
    print("1) Converting PDF -> DOCX (pdf2docx)...")
    cv = Converter(PDF)
    cv.convert(str(CONV))
    cv.close()
    print(f"   -> {CONV}")

    print("\n2) Parsing the converted DOCX...")
    profile = parse_docx(CONV)
    print(f"   name={profile.name!r} | skills={len(profile.skills)} | units={len(profile.units)} "
          f"| experience={len(profile.experience)}")

    print("\n3) ATS analysis of your real resume layout:")
    report = ats_mod.analyze(CONV, profile)
    print(f"   ATS score: {report.score}/100  (tier1={len(report.tier1)}, tier2={len(report.tier2)})")
    for i in report.issues:
        print(f"   - [{'STRUCTURAL' if i.tier == 2 else 'SAFE'}] {i.message}")

    print("\n4) Generating truthful tailored edits for 'Stripe — Internal Systems'...")
    edit_set = tailor.generate_edit_set(profile, JD, "Software Engineer, Internal Systems")
    print(f"   {len(edit_set.edits)} edit(s):")
    for e in edit_set.edits:
        print(f"   - [{e.unit_id}] {e.reason}")
        print(f"       before: {e.original_text[:80]}")
        print(f"       after : {e.new_text[:80]}")

    print("\n5) Writing edits back into your layout (format-preserving)...")
    res = docx_engine.apply_edits(CONV, edit_set, OUT)
    print(f"   applied={res['applied']} skipped={len(res['skipped'])}")
    print(f"   -> tailored DOCX: {OUT}")

    if report.tier2:
        print("\nNOTE: pdf2docx reconstructs your 2-column + photo layout using tables/boxes, which "
              "ATS parsers dislike (flagged above). For best results, rebuild from "
              "tailored_resume_1password.md style as a clean single-column DOCX, OR share your "
              "original .docx and I'll edit THAT in place with full fidelity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
