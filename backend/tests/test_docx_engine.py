"""The crux test: editing text must preserve the original formatting + layout."""
from __future__ import annotations

from docx import Document

from app.services.resume import docx_engine
from app.services.resume.models import Edit, EditSet


def _find_unit(units, needle):
    return next(u for u in units if needle in u.text)


def test_edit_preserves_run_formatting(sample_resume, tmp_path):
    doc = docx_engine.load_document(sample_resume)
    units = docx_engine.parse_units(doc)
    target = _find_unit(units, "Led a team")

    new_text = "Directed a team of 4 engineers building a Python microservice on AWS"
    edit_set = EditSet(edits=[Edit(
        unit_id=target.id, original_text=target.text, new_text=new_text, tier=1,
    )])

    out = tmp_path / "tailored.docx"
    report = docx_engine.apply_edits(sample_resume, edit_set, out)
    assert target.id in report["applied"]

    # Reload and verify: text changed, first run's bold preserved, trailing run cleared.
    reloaded = docx_engine.load_document(out)
    paras = docx_engine.collect_paragraphs(reloaded)
    ordinal = target.location.paragraph_ordinal
    paragraph, _ = paras[ordinal]

    assert paragraph.text == new_text
    assert paragraph.runs[0].bold is True          # formatting preserved
    assert paragraph.runs[1].text == ""            # collapsed into run[0]


def test_layout_and_other_paragraphs_untouched(sample_resume, tmp_path):
    doc = docx_engine.load_document(sample_resume)
    before = docx_engine.collect_paragraphs(doc)

    units = docx_engine.parse_units(doc)
    target = _find_unit(units, "Led a team")
    edit_set = EditSet(edits=[Edit(target.id, target.text, "Shipped a service", tier=1)])

    out = tmp_path / "tailored2.docx"
    docx_engine.apply_edits(sample_resume, edit_set, out)

    after = docx_engine.collect_paragraphs(docx_engine.load_document(out))
    # Same number of paragraphs (no structural change).
    assert len(before) == len(after)
    # An unrelated paragraph is identical.
    edu_before = next(p.text for p, _ in before if "B.S. Computer Science" in p.text)
    edu_after = next(p.text for p, _ in after if "B.S. Computer Science" in p.text)
    assert edu_before == edu_after


def test_drifted_edit_is_skipped(sample_resume, tmp_path):
    edit_set = EditSet(edits=[Edit("u4", "this is not the real text", "whatever", tier=1)])
    out = tmp_path / "tailored3.docx"
    report = docx_engine.apply_edits(sample_resume, edit_set, out)
    assert "u4" not in report["applied"]
    assert any(s["unit_id"] == "u4" for s in report["skipped"])
