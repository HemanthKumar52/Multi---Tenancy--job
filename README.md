# Apply Co-Pilot

Multi-tenant SaaS that turns one master resume into per-job, ATS-optimized,
**format-preserving** tailored applications on automation-friendly job boards, applies with a
human approval gate (co-pilot, not autopilot), tracks outcomes via a forwarding-alias inbox, and
preps the user for interviews.

> Architecture, decisions, and the phased roadmap live in [`PLAN.md`](./PLAN.md).

## Core principles

- **Co-pilot** — every external submission is user-approved (the approval is also the consent record).
- **Truthful tailoring only** — the agent reselects/reorders/rephrases facts already in the master
  profile. It never invents experience.
- **Format-preserving** — edits happen *inside the user's uploaded resume layout*. No new template
  is generated. ATS fixes come in two tiers: safe in-place (auto) vs structural (opt-in).
- **Legal-first / privacy-first** — only automate acceptable sources; encrypt PII; isolate tenants.

## Repo layout

```
apply-copilot/
├─ PLAN.md                 # full build plan
├─ docker-compose.yml      # Postgres+pgvector, Redis
├─ backend/                # Python · FastAPI · LangGraph · Playwright
│  └─ app/
│     ├─ services/resume/  # ⭐ parser, format-preserving DOCX engine, ATS report
│     ├─ services/matching # job<->profile fit scoring
│     ├─ services/tailoring# edit-set generation (Claude + offline fallback)
│     ├─ services/discovery# Greenhouse/Lever/Ashby/Workable/Adzuna clients
│     ├─ services/apply/    # LangGraph orchestrator + Playwright per-vendor
│     ├─ services/inbox/    # email classifier + interview-prep generator
│     ├─ db/ · schemas/ · api/
└─ frontend/               # Next.js 16 dashboard
```

## Quick start (backend, offline-capable)

The core runs **without any API key or database** — it falls back to SQLite and a local
deterministic tailoring/embedding path so you can develop offline.

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest                      # proves the resume + format engine works
uvicorn app.main:app --reload
# open http://localhost:8000/docs
```

Optional, for full power:
- `ANTHROPIC_API_KEY` — enables Claude-quality tailoring/classification (else offline fallback).
- `DATABASE_URL=postgresql+psycopg://...` — Postgres+pgvector (else SQLite).
- `docker compose up -d` — brings up Postgres+pgvector and Redis.

## Frontend

```powershell
cd frontend
pnpm install
pnpm dev                    # http://localhost:3000
```

## Status

- **Phase 0** (master profile) and **Phase 2** (format-preserving tailoring + ATS): implemented + tested.
- **Discovery**: Greenhouse, Lever, Ashby, Workable, Adzuna clients behind a ToS-respectful HTTP
  layer (`polite_get`: honest UA, per-host rate limit, backoff).
- **Phase 3 apply**: **live Greenhouse automation via Playwright** is wired and tested against a
  local mock form (never a real company). It is gated behind `APPLY_LIVE` (off by default), enforces
  a scheme/port-aware host allowlist (re-checked after redirects), hands off to a human on
  CAPTCHA/login walls (no evasion), and writes an audit record (resume hash, confirmation screenshot).
- **Inbox + interview prep**: forwarding-alias webhook → classify → auto prep.

Verified by **29 backend tests** + an **11-step end-to-end HTTP smoke** (`scripts/smoke_e2e.py`),
and a clean Next.js production build. Hardened against a 20-finding adversarial review.
See `PLAN.md` §8 for the full roadmap.

### Safety model (apply step)

Nothing is submitted without an explicit human `confirm=true` approval (the consent record).
`APPLY_LIVE=0` by default; even when enabled, a submission can only reach an allowlisted host, a
CAPTCHA/login wall becomes `human_handoff_required` rather than being bypassed, applications are
deduped per (user, job), and an already-submitted application cannot be re-submitted.
