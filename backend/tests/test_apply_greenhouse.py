"""End-to-end test of the live Greenhouse Playwright adapter against a LOCAL mock form.

No real company is ever contacted — the adapter drives 127.0.0.1 only (and the host allowlist
makes anything else a hard error).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.services.apply import playwright_greenhouse as pg
from mock_ats import MockGreenhouse


@pytest.fixture
def mock_gh():
    with MockGreenhouse(port=8791) as srv:
        yield srv


@pytest.fixture
def mock_gh_handoff():
    with MockGreenhouse(port=8792, handoff=True) as srv:
        yield srv


def test_live_submit_fills_uploads_and_confirms(mock_gh, sample_resume):
    result = pg.submit_application(
        mock_gh.apply_url,
        str(sample_resume),
        identity={"first_name": "Jane", "last_name": "Developer",
                  "email": "jane@example.com", "phone": "+1 415 555 0100"},
        answers={"Why do you want to work here?": "I love building reliable backends.",
                 "Are you authorized to work?": "Yes"},
        headless=True,
    )

    # Adapter result
    assert result["ok"] is True
    assert result["status"] == "submitted"
    assert "confirmation" in (result["confirmation_url"] or "")
    # Exact resume hash for the audit record (not just truthy).
    assert result["resume_sha256"] == hashlib.sha256(Path(sample_resume).read_bytes()).hexdigest()
    assert result["screenshot_path"] and Path(result["screenshot_path"]).exists()
    assert result["unfilled_questions"] == []

    # The mock server received exactly what we filled (proves the form was actually driven).
    rec = mock_gh.received
    assert rec.get("first_name") == "Jane"
    assert rec.get("last_name") == "Developer"
    assert rec.get("email") == "jane@example.com"
    assert rec.get("question_2") == "Yes"
    resume = rec.get("resume")
    assert isinstance(resume, dict) and resume["size"] > 0   # the resume file was uploaded


def test_dry_run_fills_but_never_submits(mock_gh, sample_resume):
    result = pg.submit_application(
        mock_gh.apply_url, str(sample_resume),
        identity={"first_name": "Jane", "last_name": "Developer",
                  "email": "jane@example.com", "phone": "+1 415 555 0100"},
        answers={"Why do you want to work here?": "I love backends.",
                 "Are you authorized to work?": "Yes"},
        headless=True, dry_run=True,
    )
    assert result["ok"] is True and result["status"] == "dry_run"
    assert result.get("submit_ready") is True
    assert result["screenshot_path"] and Path(result["screenshot_path"]).exists()
    assert mock_gh.received == {}    # the form was filled but NOTHING was submitted


def test_captcha_or_login_triggers_human_handoff(mock_gh_handoff, sample_resume):
    result = pg.submit_application(
        mock_gh_handoff.apply_url,
        str(sample_resume),
        identity={"first_name": "Jane", "email": "jane@example.com"},
        answers={},
        headless=True,
    )
    # Never auto-bypassed: hands off to the human.
    assert result["ok"] is False
    assert result["status"] == "human_handoff_required"
    # The form was never filled, and no PII screenshot is captured on a non-submit state.
    assert result["screenshot_path"] is None
    # The resume hash is still computed for the audit trail even on a non-submit outcome.
    assert result["resume_sha256"] == hashlib.sha256(Path(sample_resume).read_bytes()).hexdigest()
    assert mock_gh_handoff.received == {}


def test_refuses_non_allowlisted_host(sample_resume):
    # Hard stop BEFORE any browser launch — a submission can never reach a non-allowlisted host.
    with pytest.raises(pg.HostNotAllowed):
        pg.submit_application(
            "https://careers.evil-example.com/apply",
            str(sample_resume),
            identity={"first_name": "Jane", "email": "jane@example.com"},
            answers={},
        )
