"""Daily auto-apply scheduler.

When ``SCHEDULER_ENABLED`` is on, builds each enabled SavedSearch's daily batch every morning and
notifies the user ("N applications ready to review"). It NEVER auto-sends — review_mode keeps the
human one-click 'send all' in control. APScheduler is imported lazily so dev/tests don't need it.
"""
from __future__ import annotations

import logging

from app.config import settings
from app.db import models
from app.db.base import SessionLocal
from app.services.apply import auto_apply
from app.services.resume.parser import parse_resume

log = logging.getLogger("scheduler")


def run_daily_batches(session_factory=SessionLocal) -> dict:
    """Build today's batch for every enabled saved search. Returns a per-search summary."""
    summary: list[dict] = []
    db = session_factory()
    try:
        searches = db.query(models.SavedSearch).filter(models.SavedSearch.enabled.is_(True)).all()
        for s in searches:
            # Tenant-scoped — never resolve another tenant's profile/resume by raw id.
            profile_row = (db.query(models.Profile)
                           .filter(models.Profile.id == s.profile_id,
                                   models.Profile.tenant_id == s.tenant_id).first())
            resume = None
            if profile_row:
                resume = (db.query(models.Resume)
                          .filter(models.Resume.id == profile_row.resume_id,
                                  models.Resume.tenant_id == s.tenant_id).first())
            if not resume:
                continue
            try:
                profile = parse_resume(resume.path)
                batch = auto_apply.build_batch(db, s.tenant_id, s, profile, resume.path)
                db.add(models.Notification(
                    tenant_id=s.tenant_id,
                    title=f"{batch['prepared_count']} applications ready to review",
                    body=f"Search '{s.name}': {batch['prepared_count']} prepared, "
                         f"{batch['manual_count']} to apply manually. Open to review and send.",
                ))
                db.commit()
                summary.append({"search": s.name, "batch_id": batch["batch_id"],
                                "prepared": batch["prepared_count"]})
            except Exception as exc:  # noqa: BLE001 — one bad search must not stop the rest
                log.warning("Daily batch failed for search %s: %s", s.id, exc)
                db.rollback()
    finally:
        db.close()
    return {"searches_run": len(summary), "details": summary}


def start_scheduler() -> None:
    """Start the daily cron (lazy APScheduler import). Call once at app startup if enabled."""
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(run_daily_batches, "cron", hour=settings.scheduler_hour, minute=0,
                      id="daily_auto_apply", replace_existing=True)
    scheduler.start()
    log.info("Daily auto-apply scheduler started (hour=%s).", settings.scheduler_hour)
