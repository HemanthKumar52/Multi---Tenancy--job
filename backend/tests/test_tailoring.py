"""Tailoring must be truthful (no invented skills) and format-preserving (tier-1, in-place)."""
from __future__ import annotations

from app.services.resume.parser import parse_resume
from app.services.tailoring import tailor

JOB = "We are hiring a backend engineer. Required: Python, AWS, PostgreSQL. Build microservices."


def test_truthfulness_guard(sample_resume):
    profile = parse_resume(sample_resume)
    ok, offending = tailor.check_truthful("Skilled in Python and AWS.", profile)
    assert ok and not offending
    # Kubernetes is a known skill the candidate does NOT have -> must be rejected.
    ok2, offending2 = tailor.check_truthful("Expert in Kubernetes and Terraform.", profile)
    assert not ok2
    assert "kubernetes" in offending2


def test_offline_edits_are_truthful_and_tier1(sample_resume):
    profile = parse_resume(sample_resume)
    edit_set = tailor.generate_edit_set(profile, JOB, "Backend Engineer")
    assert edit_set.edits, "expected at least one tailoring edit"
    for e in edit_set.edits:
        assert e.tier == 1
        ok, offending = tailor.check_truthful(e.new_text, profile)
        assert ok, f"edit introduced unsupported skills: {offending}"


def test_skills_line_reordered_to_surface_jd_skills(sample_resume):
    profile = parse_resume(sample_resume)
    edit_set = tailor.generate_edit_set(profile, JOB, "Backend Engineer")
    skills_edits = [e for e in edit_set.edits if "," in e.new_text and "Python" in e.new_text]
    assert skills_edits, "expected a skills-line reorder edit"
    # JD-relevant skills (Python/AWS/PostgreSQL) should lead.
    assert skills_edits[0].new_text.startswith("Python")
