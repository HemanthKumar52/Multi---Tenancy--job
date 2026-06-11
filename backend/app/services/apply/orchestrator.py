"""Application orchestrator — the co-pilot state machine.

This is the LangGraph graph in plain-Python form (kept dependency-free so the core is testable
offline; the node boundaries map 1:1 onto LangGraph nodes for the durable version):

    DISCOVERED -> match -> tailor -> render -> PENDING_APPROVAL
                                                     |
                                       (human clicks Approve)  <-- HARD GATE
                                                     v
                                              submit -> SUBMITTED | FAILED

The PENDING_APPROVAL state is a hard interrupt: nothing is ever submitted to a third party
without an explicit human approval, which doubles as the consent/audit record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from app.config import settings
from app.services.apply import vendors
from app.services.matching.matcher import MatchResult, match
from app.services.resume import ats as ats_mod
from app.services.resume import docx_engine
from app.services.resume.models import EditSet, MasterProfile
from app.services.tailoring import tailor


class ApplicationState(str, Enum):
    DISCOVERED = "discovered"
    MATCHED = "matched"
    TAILORED = "tailored"
    PENDING_APPROVAL = "pending_approval"
    QUEUED = "queued"                          # approved, awaiting the background apply worker
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    HUMAN_HANDOFF = "human_handoff_required"   # CAPTCHA/login wall — never auto-bypassed
    BLOCKED_HOST = "blocked_host"              # apply URL host not on the allowlist — hard stop
    FAILED = "failed"
    SKIPPED = "skipped"


_STATUS_TO_STATE = {
    "submitted": "submitted",
    "human_handoff_required": "human_handoff_required",
    "failed": "failed",
}


@dataclass
class ApplicationDraft:
    job_title: str
    job_company: str
    job_url: str
    ats_vendor: str
    match: MatchResult
    edit_set: EditSet
    ats_report: dict
    tailored_doc_path: str | None
    notes: list[str] = field(default_factory=list)
    state: ApplicationState = ApplicationState.PENDING_APPROVAL
    audit: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "job_title": self.job_title,
            "job_company": self.job_company,
            "job_url": self.job_url,
            "ats_vendor": self.ats_vendor,
            "match": self.match.to_dict(),
            "edit_set": self.edit_set.to_dict(),
            "ats_report": self.ats_report,
            "tailored_doc_path": self.tailored_doc_path,
            "notes": self.notes,
            "state": self.state.value,
            "audit": self.audit,
        }


def prepare(
    profile: MasterProfile,
    *,
    job_title: str,
    job_company: str,
    job_description: str,
    job_url: str = "",
    ats_vendor: str = "greenhouse",
    source_doc_path: str | None = None,
    out_dir: str | Path | None = None,
) -> ApplicationDraft:
    """Run match -> tailor -> render and stop at PENDING_APPROVAL (never auto-submit)."""
    notes: list[str] = []
    m = match(profile, job_description, job_title)
    edit_set = tailor.generate_edit_set(profile, job_description, job_title)

    tailored_path: str | None = None
    if source_doc_path and Path(source_doc_path).suffix.lower() == ".docx":
        # Default to the configured storage path (absolute), not a cwd-relative dir.
        out_dir = Path(out_dir) if out_dir else (settings.storage_path / "tailored")
        out_dir.mkdir(parents=True, exist_ok=True)
        safe = f"{job_company}_{job_title}".replace("/", "-").replace(" ", "_")[:80]
        out_path = out_dir / f"{safe}.docx"
        report = docx_engine.apply_edits(source_doc_path, edit_set, out_path)
        tailored_path = report["out_path"]
        if report["skipped"]:
            notes.append(f"{len(report['skipped'])} edit(s) skipped during writeback.")
        ats_report = ats_mod.analyze(tailored_path, profile).to_dict()
    else:
        notes.append(
            "No DOCX source available — tailored edits computed but a tailored file was not "
            "rendered (PDF sources must be converted to DOCX first)."
        )
        ats_report = ats_mod.analyze(source_doc_path or "", profile).to_dict()

    return ApplicationDraft(
        job_title=job_title,
        job_company=job_company,
        job_url=job_url,
        ats_vendor=ats_vendor,
        match=m,
        edit_set=edit_set,
        ats_report=ats_report,
        tailored_doc_path=tailored_path,
        notes=notes,
        state=ApplicationState.PENDING_APPROVAL,
    )


def approve_and_submit(
    draft: ApplicationDraft,
    identity: dict | None = None,
    answers: dict | None = None,
) -> ApplicationDraft:
    """Called ONLY after explicit human approval. Drives the vendor apply flow.

    Stores the result dict on ``draft.audit`` so the caller can persist an audit/consent record.
    """
    draft.state = ApplicationState.SUBMITTING
    adapter = vendors.get_adapter(draft.ats_vendor)
    try:
        result = adapter.submit(
            apply_url=draft.job_url,
            resume_path=draft.tailored_doc_path,
            identity=identity or {},
            answers=answers or {},
        )
        draft.audit = result
        if result.get("message"):
            draft.notes.append(result["message"])
        state_value = _STATUS_TO_STATE.get(result.get("status", ""),
                                           "submitted" if result.get("ok") else "failed")
        draft.state = ApplicationState(state_value)
    except vendors.AutomationUnavailable as exc:
        draft.state = ApplicationState.FAILED
        draft.notes.append(str(exc))
    except vendors.HostNotAllowed as exc:
        # A security refusal — keep it distinct from a generic failure so it stays auditable.
        draft.state = ApplicationState.BLOCKED_HOST
        draft.notes.append(f"Blocked: {exc}")
    except Exception as exc:  # noqa: BLE001 — never let an apply crash propagate to the request
        draft.state = ApplicationState.FAILED
        draft.notes.append(f"Apply error: {exc}")
    return draft
