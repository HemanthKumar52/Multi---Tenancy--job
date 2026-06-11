"""Classify inbound application-related email.

Inbound arrives via the forwarding-alias model ({user}@inbox.<domain>) — no Gmail OAuth, so
no Google CASA dependency on the launch path (see PLAN.md §5/Blocker 1). Rule-based by default;
upgrades to Claude when a key is present.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum

from app.services.tailoring import llm


class EmailCategory(str, Enum):
    CONFIRMATION = "confirmation"           # "we received your application"
    INTERVIEW_INVITE = "interview_invite"   # schedule / invite
    ONLINE_ASSESSMENT = "online_assessment"  # coding test / OA link
    REJECTION = "rejection"
    RECRUITER_OUTREACH = "recruiter_outreach"
    OTHER = "other"


@dataclass
class Classification:
    category: EmailCategory
    confidence: float
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["category"] = self.category.value
        return d


_RULES: list[tuple[EmailCategory, tuple[str, ...]]] = [
    (EmailCategory.ONLINE_ASSESSMENT,
     ("online assessment", "coding test", "hackerrank", "codility", "take-home", "take home",
      "coding challenge", "complete the assessment")),
    (EmailCategory.INTERVIEW_INVITE,
     ("interview", "schedule a call", "availability", "calendly", "meet with", "phone screen",
      "next round", "speak with the team", "book a time")),
    (EmailCategory.REJECTION,
     ("unfortunately", "not moving forward", "other candidates", "will not be proceeding",
      "decided not to", "regret to inform", "position has been filled")),
    (EmailCategory.CONFIRMATION,
     ("we have received", "thank you for applying", "application received", "received your "
      "application", "successfully submitted")),
    (EmailCategory.RECRUITER_OUTREACH,
     ("came across your profile", "exciting opportunity", "i'm a recruiter", "reaching out",
      "would you be open")),
]


def classify(subject: str, body: str) -> Classification:
    if llm.llm_available():
        try:
            return _classify_llm(subject, body)
        except Exception:
            pass
    return _classify_rules(subject, body)


def _classify_rules(subject: str, body: str) -> Classification:
    text = f"{subject}\n{body}".lower()
    for category, phrases in _RULES:  # ordered by specificity / priority
        hits = [p for p in phrases if p in text]
        if hits:
            conf = min(0.95, 0.6 + 0.1 * len(hits))
            return Classification(category=category, confidence=conf, signals=hits)
    return Classification(category=EmailCategory.OTHER, confidence=0.4)


_LLM_SYSTEM = (
    "Classify a job-application email into exactly one of: confirmation, interview_invite, "
    "online_assessment, rejection, recruiter_outreach, other. Reply with ONLY the label."
)


def _classify_llm(subject: str, body: str) -> Classification:
    label = llm.complete(_LLM_SYSTEM, f"SUBJECT: {subject}\n\nBODY:\n{body[:4000]}",
                         model=None, max_tokens=10).strip().lower()
    label = re.sub(r"[^a-z_]", "", label)
    try:
        return Classification(category=EmailCategory(label), confidence=0.9, signals=["llm"])
    except ValueError:
        return _classify_rules(subject, body)
