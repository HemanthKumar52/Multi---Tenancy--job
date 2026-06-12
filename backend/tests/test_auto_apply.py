"""Daily batch auto-apply: build a batch (discover->dedupe->split->tailor) and send-all."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.base import Base
from app.services.apply import auto_apply
from app.services.discovery.base import JobPosting
from app.services.resume.parser import parse_resume


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'a.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield s
    s.close()


def test_build_then_send_batch(db, sample_resume, monkeypatch):
    db.add(models.Tenant(id="t1", name="T"))
    db.commit()

    postings = [
        JobPosting("greenhouse", "greenhouse", "1", "Acme", "Backend Engineer", "Remote",
                   "Python and AWS and PostgreSQL microservices", "https://job-boards.greenhouse.io/acme/jobs/1"),
        JobPosting("greenhouse", "greenhouse", "2", "Globex", "Frontend Engineer", "Remote",
                   "React and TypeScript", "https://job-boards.greenhouse.io/globex/jobs/2"),
        JobPosting("remotive", "external", "3", "RemoteCo", "Fullstack Engineer", "Worldwide",
                   "Node and React", "https://remotive.com/x"),  # discovery-only -> manual
    ]
    monkeypatch.setattr(auto_apply, "discover", lambda specs: postings)

    profile = parse_resume(sample_resume)
    search = models.SavedSearch(tenant_id="t1", profile_id="p1", name="daily",
                                source_specs=[{"vendor": "greenhouse", "board": "acme"}],
                                daily_cap=2, vendor_allowlist=["greenhouse", "lever", "ashby"])
    db.add(search)
    db.commit()

    batch = auto_apply.build_batch(db, "t1", search, profile, str(sample_resume))
    assert batch["prepared_count"] == 2            # the two ATS-direct jobs, capped at 2
    assert batch["manual_count"] == 1              # the external one -> you-click list

    apps = db.query(models.Application).filter(models.Application.batch_id == batch["batch_id"]).all()
    assert len(apps) == 2
    assert all(a.state == "pending_approval" for a in apps)
    assert all(a.tailored_doc_path for a in apps)  # tailored DOCX rendered for each

    # Save reusable answers, then one-click send-all.
    ap = models.AnswerProfile(tenant_id="t1",
                              identity={"first_name": "Hemanth", "last_name": "Kumar",
                                        "email": "h@example.com", "phone": "+910000000000"},
                              answers={"Why do you want to work here?": "I build reliable backends."})
    db.add(ap)
    db.commit()

    res = auto_apply.send_batch(db, "t1", batch["batch_id"], ap.identity, ap.answers)
    assert res["processed"] == 2
    # APPLY_LIVE is off by default -> adapters refuse -> failed (not a crash, not a real submit).
    assert res["counts"].get("failed", 0) == 2
    after = db.query(models.Application).filter(models.Application.batch_id == batch["batch_id"]).all()
    assert all(a.state == "failed" and a.approved_at is not None for a in after)
