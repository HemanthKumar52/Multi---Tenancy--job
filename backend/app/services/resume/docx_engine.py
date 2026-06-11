"""Format-preserving DOCX engine.

The contract that makes "edit my resume in its own layout" reliable:

* ``collect_paragraphs`` walks a document in a **stable, deterministic order** (body
  paragraphs, then descending into tables in document order). Parsing and editing both use
  this same walk, so a paragraph's ordinal is a durable handle.
* ``parse_units`` turns each paragraph into a :class:`ContentUnit` with a
  :class:`TextLocation` pointing at that ordinal.
* ``apply_edits`` writes new text **back into the same run**, preserving the run's font /
  weight / colour and the paragraph's style. The layout never changes — only the words.

Multi-run note: when a paragraph's text spans several runs (e.g. bold company + normal text),
the engine writes the new text into the first run and clears the rest. The paragraph keeps the
first run's character formatting. This is the right trade-off for whole-bullet rephrasing, and
it never alters page layout, fonts at the paragraph level, or structure.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.document import Document as _Document
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from app.services.resume.models import ContentUnit, EditSet, Role, TextLocation


# ── deterministic traversal ──────────────────────────────────────────────────
def _iter_block_items(parent):
    """Yield Paragraph and Table children of ``parent`` in document order."""
    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:  # pragma: no cover - defensive
        parent_elm = parent._element

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def collect_paragraphs(document: _Document) -> list[tuple[Paragraph, bool]]:
    """Return every paragraph in stable order as ``(paragraph, in_table)`` tuples.

    Descends into tables (and nested tables). Merged cells are visited once.
    """
    out: list[tuple[Paragraph, bool]] = []
    seen_tc: set[int] = set()

    def walk(parent, in_table: bool) -> None:
        for block in _iter_block_items(parent):
            if isinstance(block, Paragraph):
                out.append((block, in_table))
            elif isinstance(block, Table):
                for row in block.rows:
                    for cell in row.cells:
                        tc_id = id(cell._tc)
                        if tc_id in seen_tc:
                            continue
                        seen_tc.add(tc_id)
                        walk(cell, True)

    walk(document, False)
    return out


# ── role heuristics ──────────────────────────────────────────────────────────
_HEADING_STYLE_HINTS = ("heading", "title")


def _looks_like_heading(paragraph: Paragraph, text: str) -> bool:
    style = (paragraph.style.name or "").lower() if paragraph.style else ""
    if any(h in style for h in _HEADING_STYLE_HINTS):
        return True
    # Short, all-caps / title-ish line with no trailing period and few words.
    words = text.split()
    if 1 <= len(words) <= 5 and not text.endswith("."):
        letters = [c for c in text if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) / len(letters) > 0.7:
            return True
    return False


# Common resume section titles — recognized as headings regardless of case/styling.
_SECTION_TITLES = frozenset({
    "summary", "objective", "profile", "about", "about me",
    "experience", "work experience", "professional experience", "employment", "employment history",
    "education", "academic background",
    "skills", "technical skills", "core skills", "core competencies", "technologies", "tech stack",
    "projects", "personal projects", "key projects",
    "certifications", "certificates", "licenses", "awards", "achievements",
    "languages", "interests", "contact",
})


def _is_section_title(text: str) -> bool:
    low = text.strip().lower().rstrip(":").strip()
    return "," not in low and len(low.split()) <= 3 and low in _SECTION_TITLES


def _is_bullet(paragraph: Paragraph, text: str) -> bool:
    style = (paragraph.style.name or "").lower() if paragraph.style else ""
    if "list" in style:
        return True
    # numbering present
    if paragraph._p.find(qn("w:numPr")) is not None:
        return True
    return text.lstrip().startswith(("•", "-", "*", "▪", "◦", "‣", "·"))


def _classify_role(paragraph: Paragraph, text: str, ordinal: int) -> Role:
    stripped = text.strip()
    if not stripped:
        return Role.UNKNOWN
    if ordinal == 0 and len(stripped.split()) <= 5:
        return Role.NAME
    if "@" in stripped and "." in stripped and len(stripped.split()) <= 8:
        return Role.CONTACT
    if _is_section_title(stripped):
        return Role.SECTION_HEADING
    if _is_bullet(paragraph, stripped):
        return Role.BULLET
    if _looks_like_heading(paragraph, stripped):
        return Role.SECTION_HEADING
    return Role.BODY


# ── parsing ──────────────────────────────────────────────────────────────────
def parse_units(document: _Document) -> list[ContentUnit]:
    """Flatten a document into ordered, location-mapped content units."""
    units: list[ContentUnit] = []
    for ordinal, (paragraph, in_table) in enumerate(collect_paragraphs(document)):
        text = paragraph.text
        if not text.strip():
            continue  # skip blank spacers; they have no editable content
        loc = TextLocation(
            paragraph_ordinal=ordinal,
            run_count=len(paragraph.runs),
            style=paragraph.style.name if paragraph.style else None,
            in_table=in_table,
        )
        units.append(
            ContentUnit(
                id=f"u{ordinal}",
                text=text,
                role=_classify_role(paragraph, text, ordinal),
                location=loc,
            )
        )
    return units


def load_document(path: str | Path) -> _Document:
    return Document(str(path))


# ── format-preserving writeback ──────────────────────────────────────────────
def _set_paragraph_text_preserving(paragraph: Paragraph, new_text: str) -> None:
    """Replace a paragraph's text while preserving its first run's formatting + style."""
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(new_text)
        return
    runs[0].text = new_text
    for run in runs[1:]:
        run.text = ""


def apply_edits(
    in_path: str | Path,
    edit_set: EditSet,
    out_path: str | Path,
    *,
    include_tier2: bool = False,
) -> dict:
    """Apply an edit set to a DOCX, writing the result to ``out_path``.

    Only tier-1 edits are applied unless ``include_tier2`` is set (structural, opt-in).
    Returns a small report of what was applied / skipped. The original file is untouched.
    """
    document = load_document(in_path)
    paragraphs = collect_paragraphs(document)

    edits = edit_set.tier1() + (edit_set.tier2() if include_tier2 else [])
    applied, skipped = [], []

    for edit in edits:
        # unit ids are "u<ordinal>"; resolve the ordinal robustly.
        try:
            ordinal = int(edit.unit_id.lstrip("u"))
        except ValueError:
            skipped.append({"unit_id": edit.unit_id, "why": "unparseable id"})
            continue
        if not (0 <= ordinal < len(paragraphs)):
            skipped.append({"unit_id": edit.unit_id, "why": "ordinal out of range"})
            continue
        paragraph, _ = paragraphs[ordinal]
        # Guard: ensure the document still says what the edit expected (no drift).
        if edit.original_text.strip() and paragraph.text.strip() != edit.original_text.strip():
            skipped.append({"unit_id": edit.unit_id, "why": "text drifted from original"})
            continue
        _set_paragraph_text_preserving(paragraph, edit.new_text)
        applied.append(edit.unit_id)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    document.save(str(out_path))
    return {
        "out_path": str(out_path),
        "applied": applied,
        "skipped": skipped,
        "tier2_included": include_tier2,
    }


def document_plain_text(path: str | Path) -> str:
    """Linearized text of a document — useful for diffs and ATS keyword checks."""
    document = load_document(path)
    return "\n".join(p.text for p, _ in collect_paragraphs(document) if p.text.strip())
