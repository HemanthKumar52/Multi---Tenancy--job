"""Profile-aware ATS template recommender.

Coexists with the format-preserving default: this only *suggests* ATS-safe templates, and leans
in when the uploaded resume is structurally ATS-hostile (tier-2 issues / low score).
"""
from __future__ import annotations

from app.services.common.text import extract_skills
from app.services.templates.catalog import CATALOG

_TECH_FIELDS = {"software", "data", "engineering", "devops", "ml"}
_SENIOR_WORDS = ("senior", "lead", "principal", "staff", "manager", "head", "director", "vp", "chief")


def _infer_signals(profile: dict, ats_report: dict) -> dict:
    experience = profile.get("experience") or []
    titles = " ".join((e.get("title") or "") for e in experience).lower()
    n_exp = len(experience)

    if any(w in titles for w in _SENIOR_WORDS) or n_exp >= 4:
        seniority = "senior"
    elif n_exp <= 1:
        seniority = "entry"
    else:
        seniority = "mid"

    skills_text = " ".join(profile.get("skills") or []) + " " + (profile.get("summary") or "")
    is_technical = bool(set(extract_skills(skills_text)) & {
        "python", "java", "javascript", "typescript", "go", "rust", "react", "aws", "kubernetes",
        "docker", "sql", "pytorch", "tensorflow", "spark", "data engineering", "machine learning",
    })
    field = "software" if is_technical else "general"

    score = ats_report.get("score", 100)
    tier2 = ats_report.get("tier2_count", 0)
    ats_recovery = score < 70 or tier2 > 0

    return {"seniority": seniority, "field": field, "ats_recovery": ats_recovery,
            "ats_score": score, "structural_issues": tier2}


def _score(template: dict, sig: dict) -> int:
    s = 0
    if sig["ats_recovery"] and "ats-recovery" in template.get("tags", []):
        s += 4
    if sig["seniority"] in template.get("seniority", []):
        s += 2
    fields = template.get("fields", [])
    if "any" in fields:
        s += 1
    if sig["field"] in fields or (sig["field"] == "software" and sig["field"] in fields):
        s += 2
    if sig["field"] == "general" and template["id"] == "technical-engineer":
        s -= 3   # don't push a technical template to non-technical profiles
    return s


def recommend(profile: dict, ats_report: dict, limit: int = 4) -> dict:
    sig = _infer_signals(profile, ats_report)
    ranked = sorted(CATALOG, key=lambda t: _score(t, sig), reverse=True)
    recs = [{**t, "match_reason": _reason(t, sig)} for t in ranked[:limit]]

    if sig["ats_recovery"]:
        note = (f"Your resume scored {sig['ats_score']}/100 with {sig['structural_issues']} "
                f"structural issue(s). We can still tailor it in place, but if you'd like a clean "
                f"start, these ATS-safe templates are a good fit.")
    else:
        note = ("Your resume is already ATS-friendly, so we recommend keeping your format — these "
                "are optional alternatives only.")
    return {"note": note, "signals": sig, "recommendations": recs}


def _reason(template: dict, sig: dict) -> str:
    bits = []
    if sig["ats_recovery"] and "ats-recovery" in template.get("tags", []):
        bits.append("fixes the structural ATS issues in your current file")
    if sig["seniority"] in template.get("seniority", []):
        bits.append(f"suited to {sig['seniority']}-level")
    if sig["field"] in template.get("fields", []):
        bits.append(f"good for {sig['field']} roles")
    return "; ".join(bits) or "general-purpose ATS-safe layout"
