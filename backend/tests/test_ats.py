from __future__ import annotations

from app.services.resume import ats as ats_mod
from app.services.resume.parser import parse_resume


def test_clean_resume_scores_well(sample_resume):
    profile = parse_resume(sample_resume)
    report = ats_mod.analyze(sample_resume, profile)
    assert report.score >= 80
    assert report.tier2 == []          # single column, no tables/images


def test_table_resume_flags_structural_tier2(table_resume):
    profile = parse_resume(table_resume)
    report = ats_mod.analyze(table_resume, profile)
    codes = {i.code for i in report.issues}
    assert "layout_tables" in codes
    layout = next(i for i in report.issues if i.code == "layout_tables")
    assert layout.tier == 2             # structural -> opt-in only
    assert report.score < 100


def test_missing_email_is_tier1(table_resume):
    profile = parse_resume(table_resume)
    report = ats_mod.analyze(table_resume, profile)
    # table_resume has no parseable email line.
    missing = [i for i in report.issues if i.code == "missing_email"]
    assert missing and missing[0].tier == 1
