"""Background apply execution.

Approved applies run off the request thread (a browser session takes seconds). The default is an
in-process thread pool — the same shape as a managed browser-worker farm — and the interface is
Celery-ready (swap ``dispatch`` to ``.delay()`` a task). One ephemeral worker per approved apply.

The executor is swappable so tests can run inline.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from app.db import models
from app.db.base import SessionLocal
from app.services.apply import runner
from app.services.apply.orchestrator import ApplicationState

# min(8, ...) keeps the local farm modest; raise/replace with Celery for real scale.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="apply-worker")


def set_executor(submit_fn: Callable) -> None:
    """Override how work is scheduled (tests use an inline runner)."""
    global _submit
    _submit = submit_fn


def _default_submit(fn, *args) -> None:
    _executor.submit(fn, *args)


_submit = _default_submit


def _work(application_id: str, tenant_id: str, identity: dict, answers: dict,
          session_factory=SessionLocal) -> str:
    """Run one queued application to a terminal state. Opens its own DB session."""
    db = session_factory()
    try:
        app_row = (
            db.query(models.Application)
            .filter(models.Application.id == application_id,
                    models.Application.tenant_id == tenant_id)
            .first()
        )
        if not app_row or app_row.state != ApplicationState.QUEUED.value:
            return "skipped"
        job = db.get(models.Job, app_row.job_id)
        if not job:
            app_row.state = ApplicationState.FAILED.value
            app_row.notes = list(app_row.notes or []) + ["Job no longer exists"]
            db.commit()
            return app_row.state
        runner.run_submission(db, app_row, job, identity, answers)
        db.commit()
        return app_row.state
    finally:
        db.close()


def dispatch(application_id: str, tenant_id: str, identity: dict, answers: dict) -> None:
    """Schedule a queued application for background submission."""
    _submit(_work, application_id, tenant_id, identity, answers)
