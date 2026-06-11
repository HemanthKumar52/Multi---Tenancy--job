from __future__ import annotations

from app.services.matching.matcher import match
from app.services.resume.parser import parse_resume


def test_match_identifies_overlap_and_gaps(sample_resume):
    profile = parse_resume(sample_resume)
    result = match(
        profile,
        "Seeking an engineer with Python, AWS and Kubernetes experience.",
        "Backend Engineer",
    )
    assert "python" in result.matched_skills
    assert "aws" in result.matched_skills
    assert "kubernetes" in result.missing_skills   # candidate lacks it
    assert 0 < result.score <= 100
    assert result.explanation
