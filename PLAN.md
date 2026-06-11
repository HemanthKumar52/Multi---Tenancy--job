# Apply Co-Pilot — Build Plan

> Working name; rename freely. A multi-tenant SaaS that turns one master resume into
> per-job, ATS-optimized, **format-preserving** tailored applications on automation-friendly
> job boards, applies with a human approval gate, tracks outcomes, and preps the user for interviews.

_Last updated: 2026-06-10_

---

## 1. Vision

A **co-pilot, not an autopilot.** The agent does all the heavy lifting — discovery, matching,
resume tailoring, form pre-fill, outcome tracking, interview prep — and the user approves each
submission with one click. This is legal (no ToS violations), ban-resistant, higher quality than
spray-and-pray, and actually shippable.

The product loop: **Find → Tailor → Apply (approve) → Track → Prep.**

---

## 2. Locked decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Audience | **Multi-tenant SaaS** | Build for many users from day one |
| Apply autonomy | **Co-pilot — human approves each apply** | Legal, ban-resistant, quality, consent audit trail |
| Resume handling | **Format-preserving, truthful tailoring** | Edit inside the user's own template; never fabricate, never redesign |
| Job sources (MVP) | **ATS-direct boards** (Greenhouse, Lever, Ashby, Workable) **+ Adzuna** aggregator | Legal, automation-friendly, companies *want* applicants |
| Email tracking (MVP) | **Forwarding-alias model** (no Gmail OAuth) | Avoids Google CASA verification wall on the critical path |
| Deferred to paid tiers | LinkedIn/Indeed discovery, native Gmail inbox connect | ToS + verification walls — added after revenue justifies them |

---

## 3. Core principles

1. **Co-pilot.** Every external submission is user-approved. The approval is also the consent record.
2. **Truthful tailoring only.** The agent *reselects, reorders, and rephrases facts that already
   exist in the user's master profile.* It never invents jobs, skills, dates, or metrics.
3. **Format-preserving.** Edits happen *inside the user's uploaded resume layout/template.* No new
   design is generated. (See §5 — this is a core engine, not an afterthought.)
4. **Legal-first.** Only automate sources where automation is acceptable. Defer ToS-hostile sources.
5. **Privacy-first.** Resumes and contact data are PII. Encrypt at rest, isolate per tenant,
   delete on cancellation, support GDPR/CCPA export & erase.
6. **Metered economics.** Tailors, applies, and browser-minutes are variable-cost — price on usage.

---

## 4. System architecture (multi-tenant)

```
┌──────────────────────────────────────────────────────────────────┐
│                       Dashboard (Next.js 16)                       │
│  onboarding · master profile editor · job feed + match scores ·    │
│  tailor diff & ATS report · approve-to-apply · application tracker │
│                · interview prep · alerts/settings                  │
└───────────────┬──────────────────────────────────┬────────────────┘
        REST/RPC│                                   │
┌───────────────▼──────────────────┐   ┌────────────▼───────────────┐
│  Orchestrator (FastAPI+LangGraph) │   │  Notifier                   │
│  agentic state machine w/ HITL    │   │  (email + Telegram + web)   │
│  interrupts on the approval gate  │   │                             │
└─┬──────┬───────┬────────┬─────────┘   └─────────────────────────────┘
  │      │       │        │
┌─▼──┐ ┌─▼───┐ ┌─▼──────┐ ┌▼──────────┐ ┌──────────────────────────┐
│Job │ │Match│ │Resume  │ │Apply      │ │Inbox Monitor             │
│Disc│ │Eng. │ │Tailor +│ │Worker     │ │(forwarding alias inbound)│
│APIs│ │LLM+ │ │Format  │ │Playwright │ │classify → link → prep    │
│    │ │pgvec│ │Engine  │ │+ approval │ │                          │
└────┘ └─────┘ └────────┘ └───────────┘ └──────────────────────────┘
   │                                                  │
┌──▼──────────────────────────────────────────────────▼─────────────┐
│  Postgres + pgvector (tenant_id RLS on every row)                  │
│  KMS-encrypted secrets · Object storage for resume files           │
│  Redis + queue for browser jobs · Stripe (usage billing)           │
└────────────────────────────────────────────────────────────────────┘
```

**Tenancy:** `tenant_id` on every row + Postgres Row-Level Security (schema-per-tenant only if a
customer demands hard isolation). **Auth/billing:** Clerk or Auth0 + Stripe usage-based. **Secrets:**
KMS/secrets-manager, never plaintext. **Browser workers:** ephemeral, isolated, queued, one-per-apply
(co-pilot keeps this cheap — a browser only spins up when a user clicks Apply).

---

## 5. Format-preserving ATS engine  ⭐ (the differentiating, trickiest piece)

**Goal:** make the user's *own* resume ATS-friendly and job-tailored — editing in place, never
producing a new template.

### 5.1 Source of truth = two linked artifacts
1. **The original document file** (DOCX strongly preferred; PDF supported with caveats below).
2. A **master profile JSON** parsed from it, where each content unit (header, bullet, skill,
   date, section) carries a **location map** back to its place in the document
   (paragraph/run indices for DOCX). This map is what lets us write edits back *into the same layout.*

### 5.2 Editing model
Tailoring produces a structured **edit set**: a list of `{location, original_text, new_text, reason}`.
Edits are then applied deterministically to the document:

- **DOCX (primary path):** edit the document XML in place (e.g. `python-docx` / direct OOXML).
  Replace text *within existing runs*, preserving run-level formatting (font, size, bold, color).
  Handle rewrites that span multiple runs by normalizing runs while keeping the paragraph's style.
  Section reordering = moving existing paragraph blocks, not re-styling them.
- **PDF (caveated path):** true in-place PDF editing while preserving layout is unreliable.
  Strategy: prompt the user to upload DOCX when possible; if PDF-only, convert PDF→DOCX, treat as
  DOCX, and **warn that exact visual fidelity may vary.** Be honest — don't pretend pixel-perfect.

### 5.3 The ATS tension — two tiers (this is how we honor "keep my format")
Some uploaded layouts are inherently ATS-hostile (two-column, tables-for-layout, icons/graphics,
text in headers/footers, exotic fonts). Making them ATS-parseable can *require* structural change.
So we split edits:

- **Tier 1 — Safe, in-place, auto-applied (with diff approval):**
  keyword injection from the JD, bullet rephrasing, section reordering within the existing layout,
  standardizing section headings, fixing date formats, removing parser-breaking special characters.
  *These never change the look.*
- **Tier 2 — Structural, opt-in only (never silent):**
  flatten multi-column → single column, convert layout tables → linear text, move header/footer
  content into the body, replace icons/images with text. Surfaced as suggestions in an
  **ATS Risk Report** with an explicit "Apply structural fix?" toggle. **Default = preserve format.**

### 5.4 Outputs per job
- The **tailored resume in the user's original format** (Tier-1 edits applied).
- An **ATS compatibility score + issue list** (what's safe, what's structural).
- A **diff view** (original ↔ tailored) so the user approves before anything is used.
- Optional cover letter (separate doc).
- Optional "ATS-safe plain export" as a *fallback* the user can choose — but it is never the default.

### 5.5 Guardrails
- Truthfulness validator: every `new_text` must be supported by the master profile; flag anything
  that introduces a new claim and block it from auto-apply.
- Length/overflow guard: edits that would overflow a page or break the layout get flagged.

---

## 6. Data model (core tables)

- `tenants`, `users`, `subscriptions`, `usage_events`
- `resumes` — original file ref (object storage), format, parse status
- `master_profiles` — structured JSON (experience, bullets, skills, projects, education, metrics)
- `profile_location_maps` — content unit ↔ document location (for format-preserving writeback)
- `jobs` — normalized JD (source, company, title, location, description, skills, ATS vendor, apply_url)
- `job_embeddings` — pgvector
- `matches` — job ↔ user, fit score, explanation, gaps
- `tailored_documents` — edit set, tailored file ref, ATS score, diff, approval status
- `applications` — job, tailored doc, state machine status, submitted_at, approval/consent record
- `inbox_events` — parsed inbound mail (alias), classification, linked application
- `interview_preps` — extracted topics, study plan, generated material
- `notifications` — channel, payload, status

---

## 7. Tech stack

- **Agents/backend:** Python · FastAPI · **LangGraph** (state machine with human-in-the-loop
  interrupts — natural fit for the approval gate)
- **LLM:** **Claude** — Opus for tailoring quality, Sonnet for classification/matching/cheap passes
- **Browser automation:** **Playwright (Python)** on a managed/containerized browser farm; per-region
  proxies as needed
- **DB:** **Postgres + pgvector** (RLS), object storage for files
- **Queue/scheduler:** Redis + Celery (or APScheduler early)
- **Inbound email:** Postmark / SendGrid Inbound / Cloudflare Email Routing → `{user}@inbox.app`
- **Auth/billing:** Clerk or Auth0 + Stripe (usage-based)
- **Frontend:** Next.js 16
- **Resume IO:** `python-docx` / OOXML for DOCX; PDF parse + caveated PDF→DOCX path

---

## 8. Phased roadmap

### Phase 0 — Foundation & master profile (≈ wk 1–2)
Auth + tenancy skeleton. Resume upload → parse → **master profile JSON + location map**. Profile
editor UI. _Deliverable: a user can upload a resume and see/edit their structured profile._

### Phase 1 — Discovery + matching (≈ wk 2–4)
Integrate **Greenhouse/Lever/Ashby/Workable** public board endpoints + **Adzuna**. Normalize, dedup,
embed. Semantic + skill match → **fit score with explanation + gaps**. Ranked job feed UI.

### Phase 2 — Format-preserving tailoring engine (≈ wk 4–6)  ⭐
The §5 engine: edit set generation, DOCX in-place writeback, ATS score + risk report (two tiers),
diff view + approval, cover letter, truthfulness guardrails. _The hero feature._

### Phase 3 — Co-pilot apply (≈ wk 6–8)
Playwright apply flows for the 4 ATS vendors. Pre-fill from profile + tailored doc → user reviews →
**Approve → submit.** One browser per request. Per-application state machine + consent record.

### Phase 4 — Inbox tracking + interview prep (≈ wk 8–10)
Forwarding-alias inbound parsing → classify (confirmation / rejection / OA / **interview** /
recruiter). Link to applications. On interview detected → extract company/role/round → **prep plan
(topics, likely questions, company research)** → notify (email + Telegram).

### Phase 5 — Orchestration, analytics, hardening (≈ wk 10+)
Scheduling, response-rate analytics, billing polish, compliance (GDPR/CCPA export+erase), security
review. _Then_ premium expansions: native Gmail connect (pursue CASA), LinkedIn/Indeed discovery.

---

## 9. Pricing model (covers variable cost)

Meter the variable-cost actions: **tailors, applies, browser-minutes, LLM tokens.**
- Free tier: small monthly cap of tailors + applies.
- Paid tiers: scale caps + features (more sources, native Gmail, priority browser queue).
- Avoid flat-unlimited — power users on auto-apply will exceed unit economics.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| ATS boards detect/block automation | Co-pilot (low volume, human-triggered), per-region proxies, respect rate limits, prefer vendor-clean flows |
| Gmail CASA verification wall | Launch on forwarding-alias; native Gmail is a later paid add-on |
| Browser farm cost/ops | One browser per approved apply only; ephemeral, queued |
| Resume format fidelity (esp. PDF) | DOCX-first; PDF gets explicit fidelity warning + convert path |
| ATS-hostile original layouts | Two-tier edits; structural fixes opt-in, never silent |
| Fabrication / trust | Truthfulness validator blocks unsupported claims from auto-apply |
| PII / compliance | Encryption at rest, RLS, retention + delete-on-cancel, DPA, export/erase |
| Liability for submissions | Per-apply approval = explicit consent + audit trail |

---

## 11. Open questions / decisions to confirm

1. **Job sources** — proceed with ATS-direct + Adzuna for MVP, or prioritize a specific market
   (India tech / US remote / EU) that changes which APIs matter most?
2. **Email** — confirm forwarding-alias for MVP, native Gmail deferred to paid tier?
3. **Branding/name** — keep "Apply Co-Pilot" working name or align with your "Stride" family
   (note: Stride ATS is the *recruiter* side; this is the complementary *candidate* side)?
4. **Next step** — turn this into a repo scaffold (FastAPI + LangGraph + Postgres + Next.js,
   starting Phase 0), or refine further first?
