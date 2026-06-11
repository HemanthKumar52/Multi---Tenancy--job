"""Auth + tenancy isolation + plan/usage, against an isolated DB (dependency override)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401 — register tables on Base.metadata
from app.db.base import Base, get_db
from app.main import app


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 't.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TS = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override():
        db = TS()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _register(client, email="a@b.com", pw="password123"):
    r = client.post("/auth/register", json={"email": email, "password": pw, "name": "A"})
    assert r.status_code == 200, r.text
    return r.json()


def test_register_login_me(client):
    data = _register(client)
    assert data["access_token"]
    assert data["user"]["inbox_alias"].endswith("@inbox.applycopilot.local")
    h = {"Authorization": f"Bearer {data['access_token']}"}

    me = client.get("/auth/me", headers=h)
    assert me.status_code == 200 and me.json()["email"] == "a@b.com"

    # No token -> 401
    assert client.get("/auth/me").status_code == 401

    # Login
    good = client.post("/auth/login", json={"email": "a@b.com", "password": "password123"})
    assert good.status_code == 200
    bad = client.post("/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert bad.status_code == 401

    # Duplicate registration rejected
    assert client.post("/auth/register",
                       json={"email": "a@b.com", "password": "password123"}).status_code == 409


def test_tenant_isolation_via_token(client):
    h1 = {"Authorization": f"Bearer {_register(client, 'u1@x.com')['access_token']}"}
    h2 = {"Authorization": f"Bearer {_register(client, 'u2@x.com')['access_token']}"}

    client.post("/jobs", json={"title": "Secret Role", "company": "U1Co"}, headers=h1)
    assert len(client.get("/jobs", headers=h1).json()["jobs"]) == 1
    assert client.get("/jobs", headers=h2).json()["jobs"] == []   # isolated


def test_plan_and_usage(client):
    h = {"Authorization": f"Bearer {_register(client)['access_token']}"}
    plan = client.get("/billing/plan", headers=h).json()
    assert plan["plan"] == "free"
    assert plan["usage"]["tailor"]["cap"] == 20 and plan["usage"]["tailor"]["used"] == 0

    up = client.post("/billing/dev-upgrade", headers=h)
    assert up.status_code == 200 and up.json()["plan"] == "pro"
    assert client.get("/billing/plan", headers=h).json()["plan"] == "pro"
