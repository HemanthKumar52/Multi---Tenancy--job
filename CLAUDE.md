# CLAUDE.md — Apply Co-Pilot

Multi-tenant SaaS that turns one master resume into per-job, ATS-optimized, **format-preserving**
tailored applications, applies with a **human approval gate** (co-pilot), tracks outcomes via a
forwarding-alias inbox + optional native connectors, and generates interview prep.

## Non-negotiable principles (enforced in code)
1. **Co-pilot** — nothing is submitted to a third party without an explicit `confirm=true` human
   approval (the consent/audit record). No batch/auto-apply.
2. **Truthful tailoring** — edits only resurface/rephrase facts already in the master profile; a
   truthfulness guard (`services/tailoring/tailor.check_truthful`) drops any edit that introduces an
   unknown skill. Apply identity comes from the user's own profile.
3. **Format-preserving** — tailoring edits are written back into the user's *own* DOCX layout
   (`services/resume/docx_engine`). The ATS template finder only *suggests* alternatives; it never
   auto-replaces. ATS fixes are two-tier: tier-1 safe in-place vs tier-2 structural (opt-in).
4. **Legal-first** — discovery via official/public APIs; aggregator/scraped sources (Adzuna, remote
   boards, Apify) are **discovery-only** (user applies via the original link). Live apply only on
   sanctioned ATS vendors, host-allowlisted, with **no CAPTCHA/anti-bot evasion** (→ human handoff).

## Architecture
- **Backend** (`backend/app`): FastAPI + SQLAlchemy (SQLite dev / Postgres+pgvector prod).
  - `services/resume/` — parser → `MasterProfile` (+ location map), format-preserving DOCX engine, ATS report.
  - `services/matching/` — fit score + gaps (offline hashed-BoW embeddings; swap for a real provider in prod).
  - `services/tailoring/` — edit-set generation (Claude when `ANTHROPIC_API_KEY` set, else deterministic offline) + truthfulness guard.
  - `services/discovery/` — Greenhouse/Lever/Ashby/Workable (ATS-direct) + Adzuna/Remotive/RemoteOK/Arbeitnow/TheMuse/Jobicy/USAJobs/Apify (discovery-only), all via `base.polite_get` (honest UA, per-host rate limit, backoff). `aggregator.discover(specs)` fans out + dedupes.
  - `services/apply/` — spec-driven Playwright engine (`playwright_common.submit_via_spec`) with per-vendor specs (`playwright_greenhouse/lever/ashby`); `vendors` registry (gated on `apply_live`); `orchestrator` (match→tailor→render→PENDING_APPROVAL state machine); `runner.run_submission` (shared by sync + async paths); `queue` (background executor, Celery-ready); **`auto_apply`** (daily batch: discover→dedupe→split ATS-vs-manual→tailor top N → review-then-send-all). `services/scheduler.py` runs the daily batch when `SCHEDULER_ENABLED`.
  - `services/inbox/` — `ingest_email` pipeline (classify → persist → interview prep + notify), used by the forwarding-alias webhook and the IMAP/Gmail `connectors` (gated).
  - `services/templates/` — profile-aware ATS template recommender (catalog + finder).
  - `services/billing/usage.py` — per-tenant monthly metering + plan caps (free/pro); Stripe optional.
  - `core/security.py` — PBKDF2 passwords + JWT. `api/deps.py` — JWT→tenant resolution (dev header fallback).
- **Frontend** (`frontend/`): Next.js 16 App Router dashboard. Design: "precision editorial" — Fraunces/Hanken/IBM Plex, warm paper canvas (see `app/globals.css`).

## Commands
```bash
# Backend (offline-capable: SQLite + deterministic tailoring, no keys needed)
cd backend && python -m venv .venv && .venv/Scripts/activate    # (or source .venv/bin/activate)
pip install -r requirements.txt
python -m playwright install chromium      # only needed for live-apply tests
pytest                                     # full suite
python scripts/smoke_e2e.py                # end-to-end HTTP smoke
uvicorn app.main:app --reload              # http://localhost:8000/docs

# Frontend
cd frontend && pnpm install && pnpm dev     # http://localhost:3000
pnpm build                                  # production / type-check

# Full stack
docker compose up -d --build               # db + redis + api + web
```

## Key env flags (all optional in dev; see `.env.example`)
- `ANTHROPIC_API_KEY` — Claude tailoring/classification (else offline fallback).
- `DATABASE_URL` — Postgres (else SQLite under `storage/`).
- `AUTH_REQUIRED` — when true, unauthenticated requests are rejected (dev defaults to a seeded tenant).
- `APPLY_LIVE` — **off by default**; enables real browser submission. `APPLY_ALLOWED_HOSTS` gates targets.
- `APPLY_ASYNC` — run approved applies on the background worker instead of inline.
- `ADZUNA_*`, `USAJOBS_*`, `APIFY_TOKEN` — extra discovery sources. `STRIPE_*` — billing.

## Conventions
- Services are framework-agnostic and unit-tested; routes are thin. Every business row carries
  `tenant_id` (add Postgres RLS in prod). New discovery source = a `parse_*` (pure, tested) + `fetch_*`
  (via `polite_get`) + an entry in `aggregator._VENDORS`. New apply vendor = a `VendorSpec` + registry entry.
- Tests: parser/engine/ATS/tailoring/matching are pure; apply adapters run against local mock forms
  (`tests/mock_ats.py`) — never a real company. Discovery parsers test sample payloads (no network).

## Status (2026-06-11)
Phases 0–3 complete + multi-tenant SaaS layer (auth, usage/plans, background queue, native inbox
connectors, deploy). Live apply works for Greenhouse/Lever/Ashby (gated, verified vs mocks). Next:
Stripe production wiring, Gmail CASA verification, managed browser farm, Postgres RLS policies.
