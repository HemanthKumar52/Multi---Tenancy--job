"""Job <-> profile matching: a fit score with an explanation and skill gaps."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.common.text import extract_skills
from app.services.matching import embeddings
from app.services.resume.models import MasterProfile


@dataclass
class MatchResult:
    score: int = 0                                  # 0..100
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _profile_skill_set(profile: MasterProfile) -> set[str]:
    skills = {s.lower() for s in profile.skills}
    # Also harvest skills mentioned anywhere in the resume text (e.g. inside bullets).
    skills |= set(extract_skills(profile.all_known_text()))
    return skills


def match(profile: MasterProfile, job_text: str, job_title: str = "") -> MatchResult:
    """Combine skill overlap (precise) with semantic similarity (fuzzy)."""
    job_skills = set(extract_skills(job_text + " " + job_title))
    prof_skills = _profile_skill_set(profile)

    matched = sorted(job_skills & prof_skills)
    missing = sorted(job_skills - prof_skills)

    skill_overlap = len(matched) / len(job_skills) if job_skills else 0.0

    semantic = embeddings.cosine(
        embeddings.embed(profile.all_known_text()),
        embeddings.embed(f"{job_title}\n{job_text}"),
    )
    # semantic cosine on hashed BoW is small in magnitude; scale into a usable 0..1 band.
    semantic_scaled = min(1.0, max(0.0, semantic) * 1.5)

    score = round(100 * (0.65 * skill_overlap + 0.35 * semantic_scaled))

    if not job_skills:
        explanation = "Could not extract concrete skills from the job text; matched on overall similarity."
    else:
        hit = ", ".join(matched[:6]) or "none of the listed skills"
        gap = ", ".join(missing[:6])
        explanation = f"Strong on: {hit}." + (f" Missing: {gap}." if gap else " No notable gaps.")

    return MatchResult(
        score=score,
        matched_skills=matched,
        missing_skills=missing,
        explanation=explanation,
    )
