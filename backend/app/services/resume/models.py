"""Core resume domain models.

Two linked artifacts power the whole format-preserving pipeline (see PLAN.md §5):

1. The original document file (DOCX preferred).
2. A ``MasterProfile`` parsed from it, where every ``ContentUnit`` carries a ``TextLocation``
   back to its position in the document. The location is what lets us write tailored text
   *back into the same layout* without redesigning anything.

Tailoring produces an ``EditSet`` (a list of ``Edit`` operations against unit ids). The DOCX
engine applies them deterministically, preserving run-level formatting.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Semantic role of a content unit, inferred heuristically during parsing."""

    NAME = "name"
    CONTACT = "contact"
    SECTION_HEADING = "section_heading"
    SUBHEADING = "subheading"   # e.g. a job title / company line under a section
    BULLET = "bullet"
    BODY = "body"
    SKILL_LINE = "skill_line"
    DATE = "date"
    UNKNOWN = "unknown"


# Canonical sections we try to map a resume onto.
class Section(str, Enum):
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    PROJECTS = "projects"
    CERTIFICATIONS = "certifications"
    OTHER = "other"


@dataclass
class TextLocation:
    """Where a content unit lives in the document, for deterministic writeback.

    ``paragraph_ordinal`` is the index of the paragraph in the document's stable traversal
    order (body paragraphs + table-cell paragraphs, document order). Both parsing and editing
    walk the document with the same traversal, so the ordinal is a reliable handle.
    """

    paragraph_ordinal: int
    run_count: int = 0
    style: str | None = None
    in_table: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContentUnit:
    """One addressable piece of resume content (almost always one paragraph)."""

    id: str
    text: str
    role: Role = Role.UNKNOWN
    section: Section = Section.OTHER
    location: TextLocation | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["role"] = self.role.value
        d["section"] = self.section.value
        return d


@dataclass
class ExperienceItem:
    title: str = ""
    company: str = ""
    dates: str = ""
    bullets: list[str] = field(default_factory=list)
    unit_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MasterProfile:
    """Structured, canonical view of a resume. The single source of truth for tailoring.

    Tailoring may only surface/rephrase facts that exist here — never invent new ones.
    """

    name: str = ""
    email: str = ""
    phone: str = ""
    links: list[str] = field(default_factory=list)
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    experience: list[ExperienceItem] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    # The flat, ordered, location-mapped units — the bridge to the document.
    units: list[ContentUnit] = field(default_factory=list)
    source_format: str = "docx"

    def unit_by_id(self, unit_id: str) -> ContentUnit | None:
        for u in self.units:
            if u.id == unit_id:
                return u
        return None

    def all_known_text(self) -> str:
        """Everything the profile asserts — used by the truthfulness guard."""
        parts: list[str] = [self.name, self.summary, " ".join(self.skills)]
        parts += self.education + self.projects + self.certifications
        for e in self.experience:
            parts += [e.title, e.company, e.dates, *e.bullets]
        parts += [u.text for u in self.units]
        return "\n".join(p for p in parts if p)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "links": self.links,
            "summary": self.summary,
            "skills": self.skills,
            "experience": [e.to_dict() for e in self.experience],
            "education": self.education,
            "projects": self.projects,
            "certifications": self.certifications,
            "units": [u.to_dict() for u in self.units],
            "source_format": self.source_format,
        }


@dataclass
class Edit:
    """A single tailoring operation against a content unit.

    tier 1 = safe, in-place, layout-preserving (rephrase/keyword-surfacing/reorder).
    tier 2 = structural; never auto-applied, surfaced as an opt-in suggestion only.
    """

    unit_id: str
    original_text: str
    new_text: str
    reason: str = ""
    tier: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EditSet:
    edits: list[Edit] = field(default_factory=list)

    def tier1(self) -> list[Edit]:
        return [e for e in self.edits if e.tier == 1]

    def tier2(self) -> list[Edit]:
        return [e for e in self.edits if e.tier == 2]

    def to_dict(self) -> dict[str, Any]:
        return {"edits": [e.to_dict() for e in self.edits]}
