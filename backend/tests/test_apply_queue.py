"""Background apply runner + queue dispatch (no browser; apply_live off -> FAILED)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.base import Base
from app.services.apply import queue, runner
from app.services.apply.orchestrator import ApplicationState


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'q.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _seed(db) -> tuple[models.Application, models.Job]:
    db.add(models.Tenant(id="t1", name="T"))
    job = models.Job(tenant_id="t1", company="Acme", title="Engineer", ats_vendor="greenhouse",
                     url="https://job-boards.greenhouse.io/acme/jobs/1")
    db.add(job)
    db.flush()
    app = models.Application(tenant_id="t1", profile_id="p1", job_id=job.id,
                             state=ApplicationState.PENDING_APPROVAL.value, match_score=70,
                             edit_set={"edits": []}, ats_report={}, notes=[],
                             approved_at=datetime.now(timezone.utc))
    db.add(app)
    db.commit()
    return app, job


def test_runner_sets_terminal_state_and_audit(session_factory):
    db = session_factory()
    app, job = _seed(db)
    draft = runner.run_submission(db, app, job, {"first_name": "J", "email": "j@x.com"}, {})
    db.commit()
    # apply_live is off by default -> adapter refuses -> FAILED (not a crash).
    assert app.state == ApplicationState.FAILED.value == draft.state.value
    assert app.audit["company"] == "Acme" and app.audit["ats_vendor"] == "greenhouse"
    assert db.query(models.Notification).filter(models.Notification.tenant_id == "t1").count() >= 1
    db.close()


def test_queue_dispatch_runs_worker(session_factory, monkeypatch):
    db = session_factory()
    app, _ = _seed(db)
    app.state = ApplicationState.QUEUED.value
    db.commit()
    app_id = app.id
    db.close()

    # Run the worker inline, against the test's engine.
    monkeypatch.setattr(queue, "_submit",
                        lambda fn, *a: fn(*a, session_factory=session_factory))
    queue.dispatch(app_id, "t1", {"first_name": "J", "email": "j@x.com"}, {})

    check = session_factory()
    row = check.get(models.Application, app_id)
    assert row.state == ApplicationState.FAILED.value   # queued -> worker ran -> terminal
    check.close()
