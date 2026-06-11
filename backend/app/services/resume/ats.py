"""ATS compatibility scoring and a two-tier risk report.

The whole point of the product's resume promise: improve ATS-friendliness *without* redesigning
the user's resume. So issues are split into two tiers (see PLAN.md §5.3):

* **Tier 1 — safe, in-place** content fixes (missing contact, non-standard headings, exotic
  bullet glyphs). These can be auto-applied; they never change the look.
* **Tier 2 — structural** problems (multi-column layout, layout tables, images, text boxes,
  content stranded in headers/footers). These are *surfaced as opt-in suggestions only* — we
  never silently re-flow someone's layout.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from docx.oxml.ns import qn

from app.services.resume import docx_engine
from app.services.resume.models import MasterProfile, Role, Section

_SEVERITY_WEIGHT = {"high": 20, "med": 10, "low": 4}
_EXOTIC_BULLETS = set("▪◦‣·●○■□♦➢➤")


@dataclass
class AtsIssue:
    code: str
    severity: str          # high | med | low
    tier: int              # 1 = safe in-place, 2 = structural/opt-in
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AtsReport:
    score: int = 100
    issues: list[AtsIssue] = field(default_factory=list)

    def add(self, issue: AtsIssue) -> None:
        self.issues.append(issue)

    def finalize(self) -> "AtsReport":
        penalty = sum(_SEVERITY_WEIGHT.get(i.severity, 0) for i in self.issues)
        self.score = max(0, 100 - penalty)
        return self

    @property
    def tier1(self) -> list[AtsIssue]:
        return [i for i in self.issues if i.tier == 1]

    @property
    def tier2(self) -> list[AtsIssue]:
        return [i for i in self.issues if i.tier == 2]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "issues": [i.to_dict() for i in self.issues],
            "tier1_count": len(self.tier1),
            "tier2_count": len(self.tier2),
        }


# ── content checks (work for both DOCX and PDF) ──────────────────────────────
def _check_profile(profile: MasterProfile, report: AtsReport) -> None:
    if not profile.email:
        report.add(AtsIssue(
            "missing_email", "high", 1,
            "No email address detected — ATS often rejects resumes without parseable contact info.",
            "Add a plain-text email line near the top.",
        ))
    if not profile.phone:
        report.add(AtsIssue(
            "missing_phone", "med", 1,
            "No phone number detected.",
            "Add a plain-text phone number.",
        ))

    headings = {
        u.text.strip().lower()
        for u in profile.units if u.role is Role.SECTION_HEADING
    }
    standard = ("experience", "education", "skills")
    if not any(any(s in h for h in headings) for s in standard):
        report.add(AtsIssue(
            "nonstandard_headings", "med", 1,
            "Standard section headings (Experience / Education / Skills) weren't clearly detected.",
            "Use conventional, plain-text section headings so the ATS can segment your resume.",
        ))

    for u in profile.units:
        if any(ch in _EXOTIC_BULLETS for ch in u.text[:2]):
            report.add(AtsIssue(
                "exotic_bullets", "low", 1,
                "Decorative bullet glyphs found; some ATS parsers garble them.",
                "Use a standard hyphen or the built-in list style.",
            ))
            break

    if not profile.skills:
        report.add(AtsIssue(
            "no_skills_section", "med", 1,
            "No skills section detected — keyword matching against job descriptions suffers.",
            "Add a plain Skills section listing your true technologies.",
        ))


# ── structural checks (DOCX only) ────────────────────────────────────────────
def _check_docx_structure(path: str | Path, report: AtsReport) -> None:
    document = docx_engine.load_document(path)

    # Multi-column layout
    for section in document.sections:
        cols = section._sectPr.find(qn("w:cols"))
        if cols is not None:
            num = cols.get(qn("w:num"))
            if num and int(num) > 1:
                report.add(AtsIssue(
                    "multi_column", "high", 2,
                    "Multi-column layout detected. Many ATS read left-to-right and scramble columns.",
                    "Optional: flatten to a single column (changes layout — opt-in).",
                ))
                break

    # Layout tables
    if document.tables:
        report.add(AtsIssue(
            "layout_tables", "high", 2,
            f"{len(document.tables)} table(s) found. Tables used for layout often break ATS parsing.",
            "Optional: convert table content to linear text (changes layout — opt-in).",
        ))

    # Images / drawings
    drawings = sum(1 for el in document.element.iter() if el.tag.endswith("}drawing"))
    if drawings or document.inline_shapes:
        report.add(AtsIssue(
            "images", "med", 2,
            "Images/graphics detected. ATS can't read text inside images.",
            "Optional: replace graphic elements with text (changes layout — opt-in).",
        ))

    # Text boxes
    if any(el.tag.endswith("}txbxContent") for el in document.element.iter()):
        report.add(AtsIssue(
            "text_boxes", "high", 2,
            "Text boxes detected. Text inside boxes is frequently invisible to ATS.",
            "Optional: move text-box content into the document body (changes layout — opt-in).",
        ))

    # Content stranded in headers/footers
    def _hf_has_text(container) -> bool:
        return any(p.text.strip() for p in getattr(container, "paragraphs", []))

    for section in document.sections:
        if _hf_has_text(section.header) or _hf_has_text(section.footer):
            report.add(AtsIssue(
                "header_footer_content", "med", 2,
                "Content found in the header/footer. Many ATS skip these regions entirely.",
                "Optional: move contact details into the main body (changes layout — opt-in).",
            ))
            break


def analyze(path: str | Path, profile: MasterProfile) -> AtsReport:
    """Full ATS report for a parsed resume + its source file."""
    report = AtsReport()
    _check_profile(profile, report)
    if profile.source_format == "docx" and Path(path).suffix.lower() == ".docx":
        _check_docx_structure(path, report)
    return report.finalize()
