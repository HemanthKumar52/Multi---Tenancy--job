"""Edit-set generation — the heart of truthful, format-preserving tailoring.

Two paths behind one interface:

* **LLM path** (when ``ANTHROPIC_API_KEY`` is set): Claude proposes rephrasings of existing
  units to mirror the job description.
* **Offline path** (default): deterministic, conservative edits — reorder the skills line to
  surface JD-relevant skills first, and weave *already-true* matched skills into the summary.

Either way, **every proposed edit passes a truthfulness guard**: an edit may not introduce a
skill that the master profile doesn't already assert. Edits that fail the guard are dropped, so
tailoring can only ever *surface and rephrase* real facts — never invent.
"""
from __future__ import annotations

from app.services.common.text import extract_skills
from app.services.matching.matcher import match
from app.services.resume.models import Edit, EditSet, MasterProfile, Role, Section
from app.services.tailoring import llm


# ── truthfulness guard ───────────────────────────────────────────────────────
def check_truthful(new_text: str, profile: MasterProfile) -> tuple[bool, list[str]]:
    """An edit is truthful if it introduces no skill absent from the master profile."""
    known = set(extract_skills(profile.all_known_text()))
    known |= {s.lower() for s in profile.skills}
    introduced = set(extract_skills(new_text))
    offending = sorted(s for s in introduced if s not in known)
    return (len(offending) == 0, offending)


def _guarded(edit: Edit, profile: MasterProfile) -> Edit | None:
    ok, offending = check_truthful(edit.new_text, profile)
    if not ok:
        return None  # would fabricate — drop it
    return edit


# ── offline deterministic path ───────────────────────────────────────────────
def _skills_units(profile: MasterProfile):
    return [
        u for u in profile.units
        if u.section is Section.SKILLS
        and u.role in (Role.BODY, Role.BULLET, Role.SKILL_LINE)
        and "," in u.text
    ]


def _reorder_skills_edit(unit_text: str, job_skills: set[str]) -> str | None:
    parts = [p.strip() for p in unit_text.split(",")]
    parts = [p for p in parts if p]
    if len(parts) < 3:
        return None
    relevant = [p for p in parts if p.lower() in job_skills]
    rest = [p for p in parts if p.lower() not in job_skills]
    reordered = relevant + rest
    if reordered == parts:
        return None  # already ordered well
    return ", ".join(reordered)


def _summary_unit(profile: MasterProfile):
    for u in profile.units:
        if u.section is Section.SUMMARY and u.role in (Role.BODY,):
            return u
    return None


def _offline_edits(profile: MasterProfile, job_text: str, job_title: str) -> list[Edit]:
    job_skills = {s.lower() for s in extract_skills(job_text + " " + job_title)}
    edits: list[Edit] = []

    # 1) Surface JD-relevant skills first in the skills line (reorders existing tokens only).
    for unit in _skills_units(profile):
        new_text = _reorder_skills_edit(unit.text, job_skills)
        if new_text:
            edits.append(Edit(
                unit_id=unit.id,
                original_text=unit.text,
                new_text=new_text,
                reason="Reordered your existing skills to lead with those the job emphasizes.",
                tier=1,
            ))

    # 2) Weave matched-but-unmentioned true skills into the summary.
    summary = _summary_unit(profile)
    if summary:
        result = match(profile, job_text, job_title)
        already = set(extract_skills(summary.text))
        to_add = [s for s in result.matched_skills if s not in already][:3]
        if to_add:
            joined = ", ".join(to_add)
            new_text = summary.text.rstrip(". ") + f". Skilled in {joined}."
            edits.append(Edit(
                unit_id=summary.id,
                original_text=summary.text,
                new_text=new_text,
                reason="Highlighted skills you already have that the job specifically asks for.",
                tier=1,
            ))

    return edits


# ── LLM path ─────────────────────────────────────────────────────────────────
_LLM_SYSTEM = (
    "You tailor resumes to job descriptions. CRITICAL RULES: (1) You may only rephrase, "
    "reorder, or re-emphasize facts already present in the candidate's units. (2) NEVER invent "
    "skills, employers, dates, titles, or metrics. (3) Preserve approximate length. Return ONLY "
    "a JSON array of objects: {\"unit_id\": str, \"new_text\": str, \"reason\": str}. Only "
    "include units you actually changed."
)


def _llm_edits(profile: MasterProfile, job_text: str, job_title: str) -> list[Edit]:
    units_payload = [
        {"unit_id": u.id, "role": u.role.value, "section": u.section.value, "text": u.text}
        for u in profile.units
        if u.role in (Role.BODY, Role.BULLET)  # only rephrase editable body/bullet text
    ]
    user = (
        f"JOB TITLE:\n{job_title}\n\nJOB DESCRIPTION:\n{job_text}\n\n"
        f"CANDIDATE UNITS (only rephrase these, truthfully):\n{units_payload}"
    )
    proposed = llm.complete_json(_LLM_SYSTEM, user)
    edits: list[Edit] = []
    for item in proposed if isinstance(proposed, list) else []:
        unit = profile.unit_by_id(item.get("unit_id", ""))
        if not unit:
            continue
        edits.append(Edit(
            unit_id=unit.id,
            original_text=unit.text,
            new_text=str(item.get("new_text", "")).strip(),
            reason=str(item.get("reason", "")),
            tier=1,
        ))
    return edits


# ── public entry point ───────────────────────────────────────────────────────
def generate_edit_set(profile: MasterProfile, job_text: str, job_title: str = "") -> EditSet:
    """Produce a guarded, tier-1 edit set tailoring ``profile`` to a job."""
    if llm.llm_available():
        try:
            raw_edits = _llm_edits(profile, job_text, job_title)
        except Exception:
            raw_edits = _offline_edits(profile, job_text, job_title)
    else:
        raw_edits = _offline_edits(profile, job_text, job_title)

    guarded = [e for e in (_guarded(e, profile) for e in raw_edits) if e is not None]
    # ignore no-op edits
    guarded = [e for e in guarded if e.new_text.strip() and e.new_text.strip() != e.original_text.strip()]
    return EditSet(edits=guarded)
