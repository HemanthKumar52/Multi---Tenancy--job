"""Apply Co-Pilot API entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import DEV_TENANT_ID
from app.api.routes import (
    applications,
    auth,
    billing,
    health,
    inbox,
    jobs,
    matches,
    notifications,
    prep,
    profiles,
    tailor,
    templates,
)
from app.config import settings
from app.db import models
from app.db.base import SessionLocal, init_db

logging.basicConfig(level=logging.INFO)


def _seed_dev_tenant() -> None:
    with SessionLocal() as db:
        if not db.get(models.Tenant, DEV_TENANT_ID):
            db.add(models.Tenant(id=DEV_TENANT_ID, name="Dev Tenant"))
            db.commit()


def _recover_queued() -> None:
    """Re-dispatch (or fail) applications left QUEUED by a prior worker/process crash.

    Best-effort: a recovery hiccup must never block startup.
    """
    from app.services.apply import queue
    from app.services.apply.orchestrator import ApplicationState

    try:
        with SessionLocal() as db:
            rows = db.query(models.Application).filter(
                models.Application.state == ApplicationState.QUEUED.value).all()
            for r in rows:
                payload = r.queued_payload or {}
                if payload.get("identity"):
                    queue.dispatch(r.id, r.tenant_id, payload["identity"], payload.get("answers", {}))
                else:
                    r.state = ApplicationState.FAILED.value
                    r.notes = list(r.notes or []) + ["worker lost before submission; please re-apply"]
            db.commit()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("startup").warning("Queued-apply recovery skipped: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Production must require authentication — never boot with the dev tenant-header fallback.
    if settings.app_env != "dev" and not settings.auth_required:
        raise RuntimeError("AUTH_REQUIRED must be true outside dev (tenant-header fallback is dev-only).")
    init_db()
    _seed_dev_tenant()
    _recover_queued()
    yield


app = FastAPI(
    title="Apply Co-Pilot API",
    version="0.1.0",
    description="Format-preserving, truthful resume tailoring + co-pilot job applications.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (health, auth, billing, profiles, jobs, matches, tailor, applications,
          inbox, prep, notifications, templates):
    app.include_router(r.router)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": "Apply Co-Pilot",
        "docs": "/docs",
        "llm_enabled": settings.llm_enabled,
        "principles": ["co-pilot (human approves applies)", "truthful tailoring only",
                       "format-preserving edits", "privacy-first"],
    }
