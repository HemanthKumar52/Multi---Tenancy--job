"""Resume parsing: a file (DOCX or PDF) -> a structured :class:`MasterProfile`.

DOCX is the first-class path: units keep location maps, so the format-preserving engine can
write tailored text straight back into the original layout. PDF is read-only here (no reliable
in-place layout editing) — we extract text so discovery/matching/tailoring still work, but the
caller should warn the user that producing a tailored file from a PDF means converting to DOCX
first (fidelity may vary). See PLAN.md §5.2.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.services.resume import docx_engine
from app.services.resume.models import (
    ContentUnit,
    ExperienceItem,
    MasterProfile,
    Role,
    Section,
    TextLocation,
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d ()\-.]{7,}\d)")
URL_RE = re.compile(r"(https?://\S+|(?:www\.|linkedin\.com/|github\.com/)\S+)", re.I)

_SECTION_KEYWORDS: list[tuple[Section, tuple[str, ...]]] = [
    (Section.SUMMARY, ("summary", "objective", "profile", "about me")),
    (Section.EXPERIENCE, ("experience", "employment", "work history", "professional background")),
    (Section.EDUCATION, ("education", "academic")),
    (Section.SKILLS, ("skills", "technologies", "technical", "competencies", "tech stack")),
    (Section.PROJECTS, ("projects", "portfolio")),
    (Section.CERTIFICATIONS, ("certification", "certificate", "licenses", "licence")),
]

_SKILL_SPLIT_RE = re.compile(r"[,;|•·/]| - |\t")
_DATE_HINT_RE = re.compile(
    r"(19|20)\d{2}|present|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec", re.I
)


def _match_section(heading_text: str) -> Section | None:
    low = heading_text.lower()
    for section, keys in _SECTION_KEYWORDS:
        if any(k in low for k in keys):
            return section
    return None


def _extract_contact(text_blob: str) -> tuple[str, str, list[str]]:
    email = (EMAIL_RE.search(text_blob) or [None])
    email_val = email.group(0) if hasattr(email, "group") else ""
    phone_match = PHONE_RE.search(text_blob)
    phone_val = phone_match.group(0).strip() if phone_match else ""
    links = sorted({m.group(0).rstrip(".,);") for m in URL_RE.finditer(text_blob)})
    return email_val, phone_val, links


def _build_profile_from_units(units: list[ContentUnit], source_format: str) -> MasterProfile:
    profile = MasterProfile(source_format=source_format, units=units)
    blob = "\n".join(u.text for u in units)
    profile.email, profile.phone, profile.links = _extract_contact(blob)

    # Name: first NAME-role unit, else first non-empty line.
    for u in units:
        if u.role is Role.NAME:
            profile.name = u.text.strip()
            break
    if not profile.name and units:
        profile.name = units[0].text.strip()

    # Walk units, assign sections, and collect structured fields.
    current = Section.OTHER
    current_exp: ExperienceItem | None = None
    summary_lines: list[str] = []

    for u in units:
        if u.role is Role.SECTION_HEADING:
            matched = _match_section(u.text)
            current = matched or Section.OTHER
            u.section = Section.OTHER  # the heading itself stays neutral
            current_exp = None
            continue
        u.section = current

        if current is Section.SUMMARY and u.role in (Role.BODY, Role.BULLET):
            summary_lines.append(u.text.strip())

        elif current is Section.SKILLS:
            for tok in _SKILL_SPLIT_RE.split(u.text):
                tok = tok.strip(" :.-")
                if 1 < len(tok) <= 40:
                    profile.skills.append(tok)

        elif current is Section.EXPERIENCE:
            if u.role is Role.BULLET:
                if current_exp is None:
                    current_exp = ExperienceItem()
                    profile.experience.append(current_exp)
                current_exp.bullets.append(u.text.strip())
                current_exp.unit_ids.append(u.id)
            else:
                # A non-bullet line starts a new role/company header.
                current_exp = ExperienceItem(unit_ids=[u.id])
                if _DATE_HINT_RE.search(u.text):
                    current_exp.dates = u.text.strip()
                else:
                    current_exp.title = u.text.strip()
                profile.experience.append(current_exp)

        elif current is Section.EDUCATION:
            profile.education.append(u.text.strip())
        elif current is Section.PROJECTS:
            profile.projects.append(u.text.strip())
        elif current is Section.CERTIFICATIONS:
            profile.certifications.append(u.text.strip())

    profile.summary = " ".join(summary_lines).strip()
    # De-dup skills, keep order.
    seen: set[str] = set()
    profile.skills = [s for s in profile.skills if not (s.lower() in seen or seen.add(s.lower()))]
    return profile


def parse_docx(path: str | Path) -> MasterProfile:
    document = docx_engine.load_document(path)
    units = docx_engine.parse_units(document)
    return _build_profile_from_units(units, source_format="docx")


def parse_pdf(path: str | Path) -> MasterProfile:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    units: list[ContentUnit] = []
    ordinal = 0
    for page in reader.pages:
        for line in (page.extract_text() or "").splitlines():
            if not line.strip():
                continue
            # No reliable run/paragraph map for PDF -> location is informational only.
            loc = TextLocation(paragraph_ordinal=ordinal, run_count=0, in_table=False)
            role = Role.NAME if ordinal == 0 else Role.BODY
            units.append(ContentUnit(id=f"u{ordinal}", text=line.strip(), role=role, location=loc))
            ordinal += 1
    return _build_profile_from_units(units, source_format="pdf")


def parse_resume(path: str | Path) -> MasterProfile:
    """Dispatch on file extension."""
    suffix = Path(path).suffix.lower()
    if suffix == ".docx":
        return parse_docx(path)
    if suffix == ".pdf":
        return parse_pdf(path)
    raise ValueError(f"Unsupported resume format: {suffix!r} (use .docx or .pdf)")
