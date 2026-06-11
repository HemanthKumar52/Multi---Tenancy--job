"""Live Lever + Ashby apply adapters against local mock forms (never a real company)."""
from __future__ import annotations

import pytest

from app.services.apply import playwright_ashby, playwright_lever
from mock_ats import MockATS


def test_lever_submit(sample_resume):
    with MockATS(port=8793, vendor="lever") as srv:
        result = playwright_lever.submit_application(
            srv.apply_url, str(sample_resume),
            identity={"first_name": "Jane", "last_name": "Developer",
                      "email": "jane@example.com", "phone": "+1 415 555 0100"},
            answers={}, headless=True,
        )
        assert result["ok"] is True and result["status"] == "submitted"
        assert "thanks" in (result["confirmation_url"] or "")
        rec = srv.received
        assert rec.get("name") == "Jane Developer"      # Lever's single full-name field
        assert rec.get("email") == "jane@example.com"
        assert isinstance(rec.get("resume"), dict) and rec["resume"]["size"] > 0


def test_ashby_submit(sample_resume):
    with MockATS(port=8794, vendor="ashby") as srv:
        result = playwright_ashby.submit_application(
            srv.apply_url, str(sample_resume),
            identity={"first_name": "Jane", "last_name": "Developer",
                      "email": "jane@example.com", "phone": "+1 415 555 0100"},
            answers={}, headless=True,
        )
        # Ashby reports success via a container element, not a URL change.
        assert result["ok"] is True and result["status"] == "submitted"
        rec = srv.received
        assert rec.get("name") == "Jane Developer"
        assert rec.get("email") == "jane@example.com"
        assert isinstance(rec.get("resume"), dict) and rec["resume"]["size"] > 0


@pytest.mark.parametrize("mod", [playwright_lever, playwright_ashby])
def test_host_allowlist_enforced(mod, sample_resume):
    with pytest.raises(mod.HostNotAllowed):
        mod.submit_application("https://careers.evil-example.com/apply", str(sample_resume),
                               identity={"email": "x@y.com"}, answers={})


@pytest.mark.parametrize("url", [
    "https://job-boards.greenhouse.io/acme/jobs/1",
    "https://jobs.lever.co/acme/uuid/apply",
    "https://jobs.ashbyhq.com/acme/uuid/application",
])
def test_canonical_apply_hosts_are_allowlisted(url):
    # Regression guard: every shipped live vendor's canonical apply host must pass the allowlist.
    from app.services.apply.playwright_common import host_allowed
    assert host_allowed(url) is True
    assert host_allowed(url.replace("https://", "http://")) is False   # https required
