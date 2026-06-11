"""Vendor-adapter safety: the apply_live kill-switch, stub refusals, and the discovery-only fallback."""
from __future__ import annotations

import pytest

from app.services.apply import vendors


def _submit(vendor: str):
    return vendors.get_adapter(vendor).submit(
        apply_url="https://job-boards.greenhouse.io/acme/jobs/1",
        resume_path=None, identity={}, answers={},
    )


def test_greenhouse_refuses_when_apply_live_off(monkeypatch):
    monkeypatch.setattr(vendors.settings, "apply_live", False)
    with pytest.raises(vendors.AutomationUnavailable):
        _submit("greenhouse")


def test_greenhouse_delegates_when_apply_live_on(monkeypatch):
    monkeypatch.setattr(vendors.settings, "apply_live", True)
    called = {}

    def fake_submit(apply_url, resume_path, identity, answers, **kw):
        called["url"] = apply_url
        return {"ok": True, "status": "submitted", "message": "stub"}

    # Adapter imports playwright_greenhouse lazily inside submit(); patch the module function.
    monkeypatch.setattr("app.services.apply.playwright_greenhouse.submit_application", fake_submit)
    result = _submit("greenhouse")
    assert result["status"] == "submitted"
    assert called["url"].startswith("https://job-boards.greenhouse.io")


@pytest.mark.parametrize("vendor", ["lever", "ashby", "external"])
def test_stub_and_external_vendors_refuse(vendor):
    with pytest.raises(vendors.AutomationUnavailable):
        _submit(vendor)


def test_unknown_vendor_falls_back_to_external_discovery_only():
    # Unknown + Workable both resolve to the SAME external (discovery-only) adapter instance.
    assert vendors.get_adapter("totally-unknown") is vendors._ADAPTERS["external"]
    assert vendors.get_adapter("workable") is vendors._ADAPTERS["external"]
    with pytest.raises(vendors.AutomationUnavailable):
        _submit("totally-unknown")
