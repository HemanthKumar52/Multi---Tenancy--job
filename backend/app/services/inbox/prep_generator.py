"""Interview-prep generator.

When an inbound email is classified as an interview invite, we extract the likely topics (from
the email + the original job description) and produce a study plan. Offline: skills-driven
template. With a key: Claude writes a richer, role-specific plan.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.common.text import extract_skills
from app.services.tailoring import llm


@dataclass
class PrepPlan:
    company: str
    role: str
    topics: list[str] = field(default_factory=list)
    likely_questions: list[str] = field(default_factory=list)
    study_plan: list[str] = field(default_factory=list)
    company_research: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def generate(company: str, role: str, email_body: str, job_description: str = "") -> PrepPlan:
    if llm.llm_available():
        try:
            return _generate_llm(company, role, email_body, job_description)
        except Exception:
            pass
    return _generate_offline(company, role, email_body, job_description)


def _generate_offline(company: str, role: str, email_body: str, job_description: str) -> PrepPlan:
    topics = extract_skills(f"{role}\n{job_description}\n{email_body}") or ["core fundamentals"]
    topics = topics[:10]
    likely = [f"Tell me about your experience with {t}." for t in topics[:5]]
    likely += [
        "Walk me through a project you're proud of.",
        f"Why do you want to work at {company or 'this company'}?",
        "Describe a time you handled a difficult technical trade-off.",
    ]
    plan = [f"Review {t}: refresh fundamentals and prepare a concrete example." for t in topics[:6]]
    plan.append("Prepare 2-3 STAR stories mapped to the job's responsibilities.")
    plan.append(f"Draft 3 thoughtful questions to ask {company or 'the interviewer'}.")
    research = [
        f"Read {company}'s product/About pages and recent news." if company else "Research the company.",
        "Understand how the team/role fits the org.",
        "Review the job description once more and map each requirement to your experience.",
    ]
    return PrepPlan(company=company, role=role, topics=topics,
                    likely_questions=likely, study_plan=plan, company_research=research)


_LLM_SYSTEM = (
    "You are an interview coach. Given an interview invitation and the job description, produce "
    "JSON with keys: topics (list), likely_questions (list), study_plan (list), company_research "
    "(list). Be specific and practical. Return ONLY JSON."
)


def _generate_llm(company: str, role: str, email_body: str, job_description: str) -> PrepPlan:
    user = (f"COMPANY: {company}\nROLE: {role}\n\nINVITE EMAIL:\n{email_body[:3000]}\n\n"
            f"JOB DESCRIPTION:\n{job_description[:4000]}")
    data = llm.complete_json(_LLM_SYSTEM, user, max_tokens=1500)
    return PrepPlan(
        company=company, role=role,
        topics=list(data.get("topics", [])),
        likely_questions=list(data.get("likely_questions", [])),
        study_plan=list(data.get("study_plan", [])),
        company_research=list(data.get("company_research", [])),
    )
