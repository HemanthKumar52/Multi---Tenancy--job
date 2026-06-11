"""Per-vendor apply adapters.

Greenhouse is live (Playwright) and gated behind ``settings.apply_live`` — OFF by default, so
nothing submits unless an operator explicitly enables it. Lever/Ashby are stubbed (Phase 3).
External/aggregator sources are discovery-only and refuse to auto-apply by design.
"""
from __future__ import annotations

from typing import Protocol

from app.config import settings


class AutomationUnavailable(RuntimeError):
    """Raised when a vendor's live apply automation isn't enabled/wired."""


class HostNotAllowed(RuntimeError):
    """The apply URL host is not on the submission allowlist — hard security stop (never softened).

    Defined here (a dependency-light module) so the orchestrator can reference it without importing
    Playwright at app startup; the Playwright adapter re-exports it.
    """


class VendorAdapter(Protocol):
    vendor: str

    def submit(self, *, apply_url: str, resume_path: str | None, identity: dict, answers: dict) -> dict:
        """Return {ok, status, message, ...}. Raise AutomationUnavailable if not enabled."""
        ...


class _GreenhouseAdapter:
    vendor = "greenhouse"

    def submit(self, *, apply_url: str, resume_path: str | None, identity: dict, answers: dict) -> dict:
        if not settings.apply_live:
            raise AutomationUnavailable(
                "Greenhouse live apply is disabled (set APPLY_LIVE=1 to enable). The match → tailor "
                "→ approval-gate flow is fully wired; only the final browser submit is held back."
            )
        from app.services.apply import playwright_greenhouse as pg

        return pg.submit_application(apply_url, resume_path, identity, answers)


class _LeverAdapter:
    vendor = "lever"

    def submit(self, *, apply_url: str, resume_path: str | None, identity: dict, answers: dict) -> dict:
        raise AutomationUnavailable("Lever live apply automation is stubbed (Phase 3).")


class _AshbyAdapter:
    vendor = "ashby"

    def submit(self, *, apply_url: str, resume_path: str | None, identity: dict, answers: dict) -> dict:
        raise AutomationUnavailable("Ashby live apply automation is stubbed (Phase 3).")


class _ExternalAdapter:
    vendor = "external"

    def submit(self, *, apply_url: str, resume_path: str | None, identity: dict, answers: dict) -> dict:
        # Aggregator/unknown ATS: discovery-only. The user applies via the original link.
        raise AutomationUnavailable(
            "This posting is discovery-only (external/aggregator source). Open the job link to "
            "apply manually; auto-apply is reserved for supported ATS vendors."
        )


_ADAPTERS: dict[str, VendorAdapter] = {
    "greenhouse": _GreenhouseAdapter(),
    "lever": _LeverAdapter(),
    "ashby": _AshbyAdapter(),
    "external": _ExternalAdapter(),
}


def get_adapter(vendor: str) -> VendorAdapter:
    return _ADAPTERS.get(vendor, _ADAPTERS["external"])
