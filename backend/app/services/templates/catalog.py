"""Curated catalog of ATS-safe resume template archetypes.

Each entry points at a real, stable, generic source (no copyrighted content bundled). These are
*optional* alternatives — the product's default is to preserve the user's own format. The finder
recommends from here mainly when an uploaded resume is ATS-hostile.
"""
from __future__ import annotations

CATALOG: list[dict] = [
    {
        "id": "single-column-classic",
        "name": "Single-Column Classic",
        "layout": "single-column",
        "fields": ["any"],
        "seniority": ["entry", "mid", "senior"],
        "tags": ["ats-recovery", "safe"],
        "source": "Microsoft Create — resume templates",
        "url": "https://create.microsoft.com/en-us/templates/resumes",
        "why": "One column, standard headings, no tables/graphics — maximally ATS-parseable.",
    },
    {
        "id": "google-docs-resume",
        "name": "Google Docs Resume",
        "layout": "single-column",
        "fields": ["any"],
        "seniority": ["entry", "mid", "senior"],
        "tags": ["ats-recovery", "safe", "free"],
        "source": "Google Docs template gallery",
        "url": "https://docs.google.com/document/u/0/?ftv=1&tgif=d",
        "why": "Free, clean, single-column layouts that export to ATS-friendly DOCX/PDF.",
    },
    {
        "id": "flowcv-builder",
        "name": "FlowCV (ATS builder)",
        "layout": "single-column",
        "fields": ["any"],
        "seniority": ["entry", "mid", "senior"],
        "tags": ["ats-recovery", "safe", "free", "builder"],
        "source": "FlowCV",
        "url": "https://flowcv.com",
        "why": "Free builder with ATS-tested, single-column exports; good when starting fresh.",
    },
    {
        "id": "technical-engineer",
        "name": "Technical / Engineering",
        "layout": "single-column",
        "fields": ["software", "data", "engineering", "devops", "ml"],
        "seniority": ["mid", "senior"],
        "tags": ["safe", "technical"],
        "source": "Overleaf CV templates (tagged: cv)",
        "url": "https://www.overleaf.com/latex/templates/tagged/cv",
        "why": "Skills/projects-forward layouts suited to technical roles; pick single-column ones.",
    },
    {
        "id": "executive-senior",
        "name": "Executive / Senior",
        "layout": "single-column",
        "fields": ["any"],
        "seniority": ["senior", "lead", "executive"],
        "tags": ["safe", "senior"],
        "source": "Microsoft Create — executive resumes",
        "url": "https://create.microsoft.com/en-us/templates/resumes",
        "why": "Emphasizes impact/leadership summary first; keep it single-column for ATS.",
    },
    {
        "id": "entry-level-clean",
        "name": "Entry-Level Clean",
        "layout": "single-column",
        "fields": ["any"],
        "seniority": ["entry"],
        "tags": ["safe", "entry", "free"],
        "source": "Google Docs / FlowCV",
        "url": "https://flowcv.com",
        "why": "Education + projects forward, minimal styling — easy for ATS and recruiters.",
    },
]


def by_id(template_id: str) -> dict | None:
    return next((t for t in CATALOG if t["id"] == template_id), None)
