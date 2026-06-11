"""ATS template finder: profile-aware recommendations that respect format-preserving default."""
from __future__ import annotations

from app.services.templates import finder


def test_recovery_recommendations_for_ats_hostile_senior_tech_profile():
    profile = {
        "skills": ["Python", "AWS", "Kubernetes"],
        "summary": "Senior backend engineer with 8 years.",
        "experience": [{"title": "Senior Engineer"}, {"title": "Engineer"},
                       {"title": "Engineer"}, {"title": "Junior Engineer"}],
    }
    ats_report = {"score": 55, "tier2_count": 2}
    out = finder.recommend(profile, ats_report)

    sig = out["signals"]
    assert sig["seniority"] == "senior"          # 4 experiences
    assert sig["field"] == "software"            # technical skills
    assert sig["ats_recovery"] is True           # low score + structural issues
    assert len(out["recommendations"]) == 4
    # An ATS-recovery template should rank at/near the top.
    assert any("ats-recovery" in t["tags"] for t in out["recommendations"][:2])
    assert "55/100" in out["note"]


def test_healthy_profile_keeps_format():
    profile = {"skills": ["Excel", "Communication"], "summary": "Coordinator.",
               "experience": [{"title": "Coordinator"}]}
    ats_report = {"score": 95, "tier2_count": 0}
    out = finder.recommend(profile, ats_report)
    assert out["signals"]["ats_recovery"] is False
    assert out["signals"]["seniority"] == "entry"
    assert "keeping your format" in out["note"]
