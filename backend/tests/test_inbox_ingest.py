from __future__ import annotations

import base64

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.base import Base
from app.services.inbox import connectors
from app.services.inbox.ingest import ingest_email


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'i.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield s
    s.close()


def _seed_application(db) -> str:
    db.add(models.Tenant(id="t1", name="T"))
    job = models.Job(tenant_id="t1", company="Globex", title="Backend Engineer",
                     description="Python and AWS microservices", ats_vendor="greenhouse")
    db.add(job)
    db.flush()
    app = models.Application(tenant_id="t1", profile_id="p1", job_id=job.id,
                             state="submitted", match_score=70, edit_set={}, ats_report={}, notes=[])
    db.add(app)
    db.commit()
    return app.id


def test_interview_email_creates_prep(db):
    app_id = _seed_application(db)
    res = ingest_email(db, "t1", from_addr="r@globex.com", subject="Interview invite",
                       body="Let's schedule a call via Calendly.", application_id=app_id)
    assert res["classification"]["category"] == "interview_invite"
    assert "prep_plan" in res and res["prep_plan"]["topics"]
    assert db.query(models.InboxEvent).count() == 1
    assert db.query(models.InterviewPrep).count() == 1
    assert db.query(models.Notification).count() == 1


def test_rejection_email_no_prep(db):
    _seed_application(db)
    res = ingest_email(db, "t1", from_addr="r@globex.com", subject="Update",
                       body="Unfortunately we are not moving forward.")
    assert res["classification"]["category"] == "rejection"
    assert "prep_plan" not in res
    assert db.query(models.InterviewPrep).count() == 0


def test_gmail_body_extraction_handles_nested_parts():
    encoded = base64.urlsafe_b64encode(b"Hello from Gmail").decode().rstrip("=")
    payload = {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/html", "body": {"data": "PGI+aGk8L2I+"}},
        {"mimeType": "text/plain", "body": {"data": encoded}},
    ]}
    assert connectors._extract_gmail_body(payload) == "Hello from Gmail"
