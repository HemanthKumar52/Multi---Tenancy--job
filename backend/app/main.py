"""Apply Co-Pilot API entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import DEV_TENANT_ID
from app.api.routes import (
    applications,
    health,
    inbox,
    jobs,
    matches,
    notifications,
    prep,
    profiles,
    tailor,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_dev_tenant()
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

for r in (health, profiles, jobs, matches, tailor, applications, inbox, prep, notifications):
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
