from __future__ import annotations

from app.services.resume.models import Section
from app.services.resume.parser import parse_resume


def test_parses_identity_and_contact(sample_resume):
    p = parse_resume(sample_resume)
    assert p.name == "Jane Developer"
    assert p.email == "jane@example.com"
    assert p.phone.replace(" ", "").startswith("+1")
    assert any("github.com" in link for link in p.links)


def test_parses_skills_and_summary(sample_resume):
    p = parse_resume(sample_resume)
    assert "Python" in p.skills
    assert "AWS" in p.skills
    assert "Backend engineer" in p.summary


def test_sections_and_experience(sample_resume):
    p = parse_resume(sample_resume)
    assert p.experience, "expected at least one experience item"
    assert any(u.section is Section.SKILLS for u in p.units)
    assert any(u.section is Section.EXPERIENCE for u in p.units)
    # Every unit carries a location for format-preserving writeback.
    assert all(u.location is not None for u in p.units)
