# PFAM Phasewise Implementation Plan

## Project Overview
Profit-First Ad Manager (PFAM) is a multi-tenant SaaS platform for D2C brands that unifies Shopify commerce data and ad platform data (Meta, Google, TikTok) to compute true profitability and automate campaign decisions. Across the design doc, PRD, SRS, tech stack doc, and prior implementation plan, the product center of gravity is consistent: **Net Profit first**, with transparent attribution confidence, conservative automation guardrails, and strong operational reliability.

This plan follows the recommended Stack B architecture from the docs: `Next.js 14 + TypeScript + Tailwind + shadcn/ui` frontend, `FastAPI + Python 3.12 + SQLAlchemy + Alembic` backend, `Supabase Postgres`, `Clerk`, `Celery + Upstash Redis`, `Cloudflare R2`, `Resend`, and `Stripe`. The phase order is intentionally slow and foundational: infra and schema first, then ingestion, attribution, profit, automation, UI, and finally hardening + launch.

Every phase is scoped to be independently completable and testable. Nothing advanced (ML tier, broad reporting, production rollout) is started before the data and reliability prerequisites are met.

## Phase Roadmap

| Phase | Name | Description | Est. Complexity |
|-------|------|-------------|-----------------|
| 0 | Foundations & Repos | Create frontend/backend repos, env, baseline app skeletons | Medium |
| 1 | Auth, Tenancy, RBAC | Clerk JWT verification, org scoping, role enforcement | High |
| 2 | Data Model & Migrations | Core schema, constraints, indexes, immutable audit log | High |
| 3 | Shopify Connector | OAuth, secure token storage, idempotent order/refund ingestion | High |
| 4 | Meta & Google Connectors | OAuth + incremental ad data ingestion with rate-limit handling | High |
| 5 | Attribution Engine (T1-T4) | Deterministic + probabilistic attribution waterfall | Very High |
| 6 | Profit & Returns Engine | Net profit snapshots, return reserve logic, recalculation | Very High |
| 7 | Rules Engine & Action Execution | Rule eval, guardrails, idempotent actions, full audit trail | Very High |
| 8 | Dashboard APIs & Core UI | Overview, campaigns, products, attribution inspector UI | High |
| 9 | Settings, COGS, Notifications, Reports | COGS workflows, team settings, channel delivery, exports | High |
| 10 | Billing, Onboarding, Hardening | Stripe, onboarding wizard, tests, observability, launch gate | High |
| 11 | Tier 5 ML Attribution | Train/serve XGBoost model with fallback behavior | Very High |

## Micro-Phase Map (Only Oversized Phases)

| Parent Phase | Micro-Phases |
|--------------|--------------|
| 4 | 4A Meta OAuth, 4B Meta Sync, 4C Google OAuth, 4D Google Sync |
| 5 | 5A Attribution Core, 5B Tier 1, 5C Tier 2, 5D Tier 3, 5E Tier 4 + Orchestration |
| 6 | 6A Return Rates, 6B Core Profit Formula, 6C Profit Windows + Recompute |
| 7 | 7A Rule CRUD + Schema, 7B Evaluator + Guardrails, 7C Action Worker + Audit + Undo |
| 8 | 8A Dashboard APIs, 8B Overview UI, 8C Campaigns UI + Right Panel |
| 9 | 9A COGS + Team/Org Settings, 9B Notifications, 9C Exports + Reports |
| 10 | 10A Stripe Billing, 10B Onboarding, 10C Hardening + Launch Checklist |

---

## Phase 0: Foundations & Repos

**Goal:**  
Establish a clean, repeatable project foundation for both frontend and backend so all later phases can be implemented without rework. This phase creates the baseline structure, environment configuration, runtime scripts, and health checks.

**Scope (What we're building):**
- Create `pfam-frontend/` (`Next.js 14`, TS, Tailwind, App Router) and `pfam-backend/` (`FastAPI`, `SQLAlchemy 2.0`, `Alembic`, `Celery`).
- Add root `.cursorrules` alignment in both repos.
- Backend core files: `app/main.py`, `app/config.py`, `app/db.py`, `app/middleware/auth.py`, `celery_app.py`, `alembic/env.py`.
- Frontend core files: `src/app/layout.tsx`, `src/middleware.ts`, auth pages, dashboard shell layout, `src/lib/api.ts`.
- Health endpoint `GET /health` and local run scripts.

**Out of Scope (What we're NOT building yet):**
- Business-domain tables and migrations.
- Any external connector implementation.
- Profit calculations, rules, charts, exports.

**Prerequisites:**
- Accounts and keys prepared for Clerk/Supabase/Railway/Upstash (placeholders acceptable for now).
- Python 3.12 and Node environment available.

**Acceptance Criteria:**
- [ ] `GET /health` returns success response.
- [ ] Frontend boots and protected dashboard route redirects unauthenticated users.
- [ ] Clerk sign-in/sign-up pages render.
- [ ] Backend and frontend have environment loading and no startup errors.

**Files/Folders to be created or modified:**
- `pfam-backend/app/main.py`
- `pfam-backend/app/config.py`
- `pfam-backend/app/db.py`
- `pfam-backend/app/middleware/auth.py`
- `pfam-backend/celery_app.py`
- `pfam-backend/alembic/env.py`
- `pfam-frontend/src/app/layout.tsx`
- `pfam-frontend/src/app/(auth)/sign-in/page.tsx`
- `pfam-frontend/src/app/(auth)/sign-up/page.tsx`
- `pfam-frontend/src/app/(dashboard)/layout.tsx`
- `pfam-frontend/src/middleware.ts`
- `pfam-frontend/src/lib/api.ts`

**Cursor Prompt:**  
We are building PFAM (Profit-First Ad Manager), a multi-tenant SaaS for true campaign profitability. Nothing domain-specific is implemented yet. In this phase, build the foundation only: backend and frontend skeletons with auth middleware and health checks. Reference `@PFAM_TechStack_v1.docx`, `@PFAM_SRS_v2.docx`, and `@PFAM_Implementation_Plan_v1.docx`.

Use Stack B exactly: Next.js 14 + TypeScript + Tailwind + shadcn/ui (frontend), FastAPI + Python 3.12 + SQLAlchemy 2.0 + Alembic + Celery (backend), Clerk for auth.

Create backend files: `app/main.py`, `app/config.py`, `app/db.py`, `app/middleware/auth.py`, `celery_app.py`, `alembic/env.py`, plus package `__init__.py` files.  
In `app/main.py`, add `GET /health`.  
In `app/middleware/auth.py`, verify Clerk JWT via JWKS and inject `org_id`/`user_id` into request state.  
Create frontend files: `src/app/layout.tsx`, `src/middleware.ts`, `src/lib/api.ts`, `src/app/(auth)/sign-in/page.tsx`, `src/app/(auth)/sign-up/page.tsx`, `src/app/(dashboard)/layout.tsx`.

Follow constraints from docs: strict typing, clear error responses, no secret logging, UTC timestamps, and project conventions.  
Do not build anything outside this scope. Ask me before making assumptions.

---

## Phase 1: Auth, Multi-Tenancy, and RBAC
**Goal:**  
Implement security and data isolation primitives early: org-scoped access on every query path and role-based endpoint protection, ensuring no cross-tenant leakage.

**Scope (What we're building):**
- User/org models and tenant context propagation from Clerk JWT.
- RBAC middleware/dependencies for Owner/Admin/Analyst/Read-Only.
- Auth/role audit events into append-only `audit_log`.
- Team management endpoints skeleton (`invite`, `list`, `role update`, `remove`).

**Out of Scope (What we're NOT building yet):**
- Platform connectors.
- Rule execution.
- Billing enforcement logic.

**Prerequisites:**
- Phase 0 complete.

**Acceptance Criteria:**
- [ ] Unauthorized requests get `401`; unauthorized roles get `403`.
- [ ] All protected endpoints enforce org scoping.
- [ ] Role updates and security events append audit entries.

**Files/Folders to be created or modified:**
- `pfam-backend/app/middleware/rbac.py`
- `pfam-backend/app/routers/team.py`
- `pfam-backend/app/services/auth/`
- `pfam-backend/app/models/user.py`
- `pfam-backend/app/models/organization.py`

**Cursor Prompt:**  
PFAM foundation is complete (app shells + JWT middleware). In this phase, implement multi-tenant authz and RBAC only. Reference `@PFAM_SRS_v2.docx`, `@PFAM_Product_Requirements_Document.docx`, and `@PFAM_Design_Doc_v1.docx`.

Implement Owner/Admin/Analyst/Read-Only permissions in backend middleware/dependencies (`app/middleware/rbac.py`). Enforce org-level filtering (`org_id` from JWT) in all new team endpoints. Add `app/routers/team.py` with list, invite, role update, and remove endpoints. Ensure role changes and auth events write append-only audit records.

Tech constraints: FastAPI + Pydantic v2 + SQLAlchemy 2.0, strict validation, no PII/token logging, immutable audit behavior.  
Do not build anything outside this scope. Ask me before making assumptions.

---

## Phase 2: Data Model & Migrations
**Goal:**  
Establish the full PFAM core schema with strong constraints and indexes before implementing ingestion or business logic.

**Scope (What we're building):**
- Alembic migrations for core entities: orgs/users/stores/ad_accounts/campaign hierarchy/orders/line_items/returns/attribution/profit/rules/audit/notifications/settings.
- Enforce `org_id` on all tenant tables.
- Monetary fields as integer cents; confidence/ratios as numeric decimal fields.
- Immutable `audit_log` design (no updates/deletes path in app).
- Required unique constraints and query indexes.

**Out of Scope (What we're NOT building yet):**
- Connector workers or API ingestion logic.
- Attribution/profit computations.

**Prerequisites:**
- Phase 1 complete.

**Acceptance Criteria:**
- [ ] All required tables exist and migrate cleanly.
- [ ] All money fields are integer cents.
- [ ] `audit_log` is append-only in code paths.
- [ ] Indexes exist for high-frequency lookup paths.

**Files/Folders to be created or modified:**
- `pfam-backend/app/models/*.py`
- `pfam-backend/alembic/versions/*_core_schema.py`

**Cursor Prompt:**  
PFAM auth/tenancy is already built. Now implement database schema and Alembic migrations only. Reference `@PFAM_SRS_v2.docx`, `@PFAM_Product_Requirements_Document.docx`, and `@PFAM_Implementation_Plan_v1.docx`.

Create SQLAlchemy models and migrations for organizations, users, stores, ad_accounts, campaigns, ad_sets, ad_insights, orders, line_items, returns, attributed_orders, sku_return_rates, cogs_settings, profit_metrics, automation_rules, rule_executions, audit_log, and notifications. Ensure every tenant-scoped table has `org_id`. Use UUID PKs, UTC timestamps, and integer cents for all money.

Add unique constraints and indexes for sync idempotency and dashboard query performance. Keep `audit_log` append-only by design.
Do not build anything outside this scope. Ask me before making assumptions.

---

## Phase 3: Shopify Connector
**Goal:**  
Get commerce ingestion production-ready first, since order/line-item/refund data is the backbone for attribution and profit.

**Scope (What we're building):**
- Shopify OAuth initiation + callback routes.
- AES-256 encrypted token storage.
- Idempotent historical + incremental sync tasks for orders, line items, refunds.
- Store connector status endpoints and manual sync endpoint with cooldown.

**Out of Scope (What we're NOT building yet):**
- Meta/Google connectors.
- Attribution and profit processing chain.

**Prerequisites:**
- Phase 2 complete.
- Shopify partner app configured.

**Acceptance Criteria:**
- [ ] OAuth connects and persists encrypted token.
- [ ] 90-day import succeeds with upsert idempotency.
- [ ] Refunds ingested with line-item granularity.
- [ ] Manual sync cooldown works.

**Files/Folders to be created or modified:**
- `pfam-backend/app/routers/connectors.py`
- `pfam-backend/app/routers/stores.py`
- `pfam-backend/app/services/connectors/shopify.py`
- `pfam-backend/app/workers/sync_shopify.py`
- `pfam-backend/app/utils/encryption.py`

**Cursor Prompt:**  
PFAM schema is complete and tenant-safe. Build Shopify connector and ingestion now. Reference `@PFAM_SRS_v2.docx`, `@PFAM_Product_Requirements_Document.docx`, and `@PFAM_TechStack_v1.docx`.

Implement `GET /api/connect/shopify` and callback in `app/routers/connectors.py`; validate `*.myshopify.com`, store nonce in Redis, exchange code for token, encrypt token (AES-256), persist to `stores`, and trigger Celery sync.

Build `app/workers/sync_shopify.py` for idempotent upserts of orders, line_items, and returns with pagination and retry/backoff handling. Add `app/routers/stores.py` endpoints for list/detail/sync/disconnect, with org scoping and manual sync rate-limit (5 minutes).

Follow conventions: never log tokens, all DB queries tenant-filtered, retries 3x with backoff, and money in cents.  
Do not build anything outside this scope. Ask me before making assumptions.

---

## Phase 4: Meta & Google Connectors
**Goal:**  
Ingest ad-side campaign/ad set/insight data with resilient token lifecycle and rate-limit handling.

**Scope (What we're building):**
- Meta OAuth + token exchange + account ingestion + sync worker.
- Google OAuth + customer discovery + GAQL ingestion worker.
- Upsert workflows for campaigns/ad_sets/ad_insights.
- Token refresh + expired-token status + retry patterns.

**Out of Scope (What we're NOT building yet):**
- Action execution on live accounts.
- TikTok connector.

**Prerequisites:**
- Phase 3 complete.

**Acceptance Criteria:**
- [ ] Meta and Google OAuth flows complete.
- [ ] Campaign/ad set/insight records are populated for 90 days.
- [ ] Repeat sync produces no duplicates.
- [ ] Rate-limit and token-expiry paths are graceful.

**Files/Folders to be created or modified:**
- `pfam-backend/app/services/connectors/meta.py`
- `pfam-backend/app/services/connectors/google.py`
- `pfam-backend/app/workers/sync_meta.py`
- `pfam-backend/app/workers/sync_google.py`
- `pfam-backend/app/routers/connectors.py`

**Cursor Prompt:**  
Shopify ingestion is complete. In this phase, build Meta and Google connectors and data sync only. Reference `@PFAM_SRS_v2.docx`, `@PFAM_Product_Requirements_Document.docx`, `@PFAM_Implementation_Plan_v1.docx`.

Implement OAuth flows and encrypted token storage for Meta (`ads_read`, `ads_management`) and Google Ads (`adwords` scope). Build Celery workers for campaigns/adsets/ad insights upserts and 90-day daily metrics ingestion.

Implement token refresh logic, rate-limit handling (Meta code 17, Google quota throttling), and connector sync statuses. Keep strict org scoping and idempotent upserts.
Do not build anything outside this scope. Ask me before making assumptions.

**Micro-Phases (execute in order):**
- **4A — Meta OAuth:** implement callback flow, token encryption, account linking, connector status fields.
- **4B — Meta Sync Worker:** campaign/adset/insight ingestion, retries, rate-limit backoff, idempotent upserts.
- **4C — Google OAuth:** OAuth credential exchange, refresh token persistence, customer/account discovery.
- **4D — Google Sync Worker:** GAQL campaign/ad group/performance ingestion with quota-aware throttling.

---

## Phase 5: Attribution Engine (Tier 1-4)
**Goal:**  
Ship the non-ML attribution waterfall with confidence labels and deterministic fallback behavior.

**Scope (What we're building):**
- Attribution package with orchestrator and tier modules:
  - Tier 1 direct click ID (`fbclid/gclid/ttclid`).
  - Tier 2 conversion matching.
  - Tier 3 SKU-weighted.
  - Tier 4 blended by spend.
- Attribution result schema and `attributed_orders` upsert worker integration.
- Coverage metrics and unmatched order handling.

**Out of Scope (What we're NOT building yet):**
- Tier 5 ML attribution.

**Prerequisites:**
- Phases 3 and 4 complete.

**Acceptance Criteria:**
- [ ] Tier 1 and Tier 2 pass known-match tests.
- [ ] Tier 3/4 fallback runs for unmatched orders.
- [ ] Confidence tiers match spec values.
- [ ] Attribution job rerun remains idempotent.

**Files/Folders to be created or modified:**
- `pfam-backend/app/services/attribution/orchestrator.py`
- `pfam-backend/app/services/attribution/tier1_click_id.py`
- `pfam-backend/app/services/attribution/tier2_conversion_id.py`
- `pfam-backend/app/services/attribution/tier3_sku_weighted.py`
- `pfam-backend/app/services/attribution/tier4_blended.py`
- `pfam-backend/app/workers/run_attribution.py`

**Cursor Prompt:**  
Commerce and ad data ingestion are already running. Build PFAM attribution tiers 1-4 now, with strict waterfall and confidence tracking. Reference `@PFAM_SRS_v2.docx`, `@PFAM_Product_Requirements_Document.docx`, and `@PFAM_Design_Doc_v1.docx`.

Create attribution modules and orchestrator in `app/services/attribution/`. Output must include `attribution_tier`, `confidence_score`, `attribution_method`, and matched click/conversion metadata. Implement tier order: direct click ID, conversion ID, SKU-weighted, blended fallback.

Add worker `app/workers/run_attribution.py` to process unattributed orders and upsert `attributed_orders`. Include per-org attribution window setting support and coverage reporting.
Do not build anything outside this scope. Ask me before making assumptions.

**Micro-Phases (execute in order):**
- **5A — Attribution Core:** result model, orchestrator shell, shared helpers, conflict resolution policy.
- **5B — Tier 1:** click-id extraction and deterministic direct matching tests.
- **5C — Tier 2:** conversion-id/value-time matching with ambiguity resolution.
- **5D — Tier 3:** SKU affinity model from Tier1/2 history and weighted attribution.
- **5E — Tier 4 + Worker:** blended fallback, full run worker, coverage metrics, idempotent persistence.

---

## Phase 6: Profit & Returns Engine
**Goal:**  
Implement immutable profit snapshots using PFAM’s canonical formula and return-lag modeling.

**Scope (What we're building):**
- Return-rate computation service (`90d/180d`, manual override precedence).
- Profit calculator using `Decimal` and integer cents output.
- Return reserve behavior for orders `<45 days` and actual refunds for older orders.
- Profit windows: daily + rolling 7/14/30.
- Recompute trigger when COGS or return data changes.

**Out of Scope (What we're NOT building yet):**
- Automation execution.
- Frontend charting.

**Prerequisites:**
- Phase 5 complete.

**Acceptance Criteria:**
- [ ] Profit equation matches spec components exactly.
- [ ] Manual campaign spot-check within ±1%.
- [ ] Re-run job does not create duplicate snapshots.

**Files/Folders to be created or modified:**
- `pfam-backend/app/services/profit/calculator.py`
- `pfam-backend/app/services/profit/return_rates.py`
- `pfam-backend/app/workers/calculate_profit.py`

**Cursor Prompt:**  
Attribution tiers 1-4 are complete. Build the PFAM profit and returns engines now using the official formula from docs. Reference `@PFAM_SRS_v2.docx`, `@PFAM_Product_Requirements_Document.docx`, and `@PFAM_Implementation_Plan_v1.docx`.

Implement `app/services/profit/calculator.py` and `app/services/profit/return_rates.py`. Use Decimal for all intermediate math; persist money in integer cents. Formula: Attributed Revenue - Ad Spend - Attributed COGS - Estimated Returns - Platform Fees.

Add `app/workers/calculate_profit.py` to compute and upsert daily and rolling metrics per ad set into `profit_metrics`. Implement return reserve (<45 days) and actual refunds (>=45 days), plus recomputation trigger semantics.
Do not build anything outside this scope. Ask me before making assumptions.

**Micro-Phases (execute in order):**
- **6A — Return Rates:** trailing 90/180 computation, overrides, reason categories, reserve labels.
- **6B — Core Profit Calc:** Decimal-safe implementation of every formula component in cents.
- **6C — Profit Snapshots:** daily/rolling computations, upsert idempotency, recompute on COGS/returns changes.

---

## Phase 7: Rules Engine & Action Execution
**Goal:**  
Enable profit-based automation safely with strong guardrails, idempotency, and full traceability.

**Scope (What we're building):**
- Rule condition evaluator with AND/OR logic and rolling windows.
- Guardrails: min orders, min spend, max actions/day, duplicate prevention window.
- Action execution worker for pause/budget updates.
- Append-only audit trail for every success/failure and reversal.
- Backtest endpoint (non-executing).

**Out of Scope (What we're NOT building yet):**
- Advanced UI polish.

**Prerequisites:**
- Phase 6 complete.

**Acceptance Criteria:**
- [ ] Rule triggers correctly on negative-profit conditions.
- [ ] Guardrails block low-data unsafe actions.
- [ ] Duplicate firing prevented by idempotency strategy.
- [ ] Every action/reversal appends an audit log event.

**Files/Folders to be created or modified:**
- `pfam-backend/app/services/rules/evaluator.py`
- `pfam-backend/app/workers/execute_action.py`
- `pfam-backend/app/routers/rules.py`
- `pfam-backend/app/routers/audit_log.py`

**Cursor Prompt:**  
Profit metrics are already being generated. Build PFAM automation rules and action execution now with safety-first behavior. Reference `@PFAM_SRS_v2.docx`, `@PFAM_Product_Requirements_Document.docx`, and `@PFAM_Design_Doc_v1.docx`.

Implement rules evaluator service in `app/services/rules/evaluator.py` supporting metric conditions, AND/OR logic, and windows 1/3/7/14/30 days. Add guardrails and idempotency checks. Build action worker `app/workers/execute_action.py` for pause/budget changes with retries and API response capture.

Create CRUD + toggle + backtest APIs in `app/routers/rules.py` and audit browsing/reversal in `app/routers/audit_log.py`. Keep audit log append-only and tenant-scoped.
Do not build anything outside this scope. Ask me before making assumptions.

**Micro-Phases (execute in order):**
- **7A — Rule Model + CRUD:** conditions schema validation, draft-by-default behavior, backtest endpoint stub.
- **7B — Evaluator + Guardrails:** windowed metric evaluation, min order/spend/max-actions checks, idempotency lockout.
- **7C — Action Execution:** platform calls, retries, audit append-only writes, undo/reverse flow, backtest finalize.

---

## Phase 8: Dashboard APIs & Core UI
**Goal:**  
Deliver the first complete user-visible PFAM experience: overview and campaign control center with real data.

**Scope (What we're building):**
- Overview API and campaigns/products endpoints.
- Frontend pages for `overview`, `campaigns`, and slide-in campaign detail panel.
- KPI cards, profit trend line, platform tiles, activity feed.
- Campaign table with sorting/filtering and attribution confidence indicators.

**Out of Scope (What we're NOT building yet):**
- Full settings suite.
- Export/report generation jobs.

**Prerequisites:**
- Phase 7 complete.

**Acceptance Criteria:**
- [ ] Overview KPIs match backend aggregates.
- [ ] Campaign table defaults to worst net-profit first.
- [ ] Right panel shows profit breakdown + attribution detail.
- [ ] Empty/loading states follow design patterns.

**Files/Folders to be created or modified:**
- `pfam-backend/app/routers/dashboard.py`
- `pfam-backend/app/routers/campaigns.py`
- `pfam-backend/app/routers/products.py`
- `pfam-frontend/src/app/(dashboard)/overview/page.tsx`
- `pfam-frontend/src/app/(dashboard)/campaigns/page.tsx`
- `pfam-frontend/src/features/campaigns/*`

**Cursor Prompt:**  
Rules and audit backend are complete. Build PFAM dashboard APIs and core frontend views now. Reference `@PFAM_Design_Doc_v1.docx`, `@PFAM_SRS_v2.docx`, and `@PFAM_Product_Requirements_Document.docx`.

Backend: implement overview, campaigns, campaign profit breakdown, ad-set attributed orders, and SKU profitability endpoints with strict `org_id` filtering and money in cents.  
Frontend: implement `overview` and `campaigns` pages using shadcn/ui + Recharts + React Query. Include KPI row, platform tiles, profit trend chart (break-even line), activity feed, sortable campaign table, and right-side detail panel.

Follow design tokens/semantics (profit colors, confidence chips, loading skeletons, empty states, responsive behavior).  
Do not build anything outside this scope. Ask me before making assumptions.

**Micro-Phases (execute in order):**
- **8A — Dashboard APIs:** overview/campaigns/products endpoints, Redis cache, org-scoped filters.
- **8B — Overview UI:** KPI row, platform tiles, trend chart, activity feed, sync bar states.
- **8C — Campaigns UI:** sortable/filterable table, row panel with profit breakdown + attribution inspector.

---

## Phase 9: Settings, COGS, Notifications, Reports
**Goal:**  
Add operational features required for daily use: data quality controls, team ops, alerting, and exports.

**Scope (What we're building):**
- COGS management APIs (Shopify import, CSV upload, manual overrides).
- Settings pages: connectors, COGS, team, notifications, org preferences.
- Notification service (Email/Slack/Webhook) + history.
- CSV/PDF export jobs to R2 with signed URL delivery.

**Out of Scope (What we're NOT building yet):**
- Stripe billing flow.
- Tier 5 ML.

**Prerequisites:**
- Phase 8 complete.

**Acceptance Criteria:**
- [ ] COGS changes trigger historical profit recompute.
- [ ] Notifications deliver and retry correctly.
- [ ] Exports complete and signed URLs expire correctly.

**Files/Folders to be created or modified:**
- `pfam-backend/app/routers/cogs.py`
- `pfam-backend/app/routers/notifications.py`
- `pfam-backend/app/routers/reports.py`
- `pfam-backend/app/services/notifications.py`
- `pfam-backend/app/services/exports.py`
- `pfam-frontend/src/app/(dashboard)/settings/*`

**Cursor Prompt:**  
Core dashboard is live. Build PFAM operational settings, COGS workflows, notifications, and reports. Reference `@PFAM_SRS_v2.docx`, `@PFAM_Product_Requirements_Document.docx`, and `@PFAM_Design_Doc_v1.docx`.

Implement backend routers/services for COGS CRUD + CSV import + Shopify import, notifications channel delivery/history/settings, and CSV/PDF report export jobs with R2 uploads + signed URLs.

Implement frontend settings pages under `src/app/(dashboard)/settings/` for connectors, COGS, team, notifications, and organization configuration. Include validation feedback and role-aware actions.
Do not build anything outside this scope. Ask me before making assumptions.

**Micro-Phases (execute in order):**
- **9A — Settings + COGS:** COGS CRUD/import flows and core settings pages (team/org/connectors).
- **9B — Notifications:** channel settings, delivery workers, retry handling, in-app notification history.
- **9C — Reports/Exports:** CSV/PDF generation jobs, R2 signed URL workflow, export status polling.

---

## Phase 10: Billing, Onboarding, and Hardening
**Goal:**  
Complete monetization and first-run UX, then harden the platform for production reliability and compliance.

**Scope (What we're building):**
- Stripe checkout, portal, webhook handling, billing status sync.
- 5-step onboarding wizard with resumable progress.
- E2E and integration test coverage for critical paths.
- Observability baseline: Sentry + key metrics + alerting hooks.
- Launch checklist validation (tenant isolation, precision, idempotency, RBAC).

**Out of Scope (What we're NOT building yet):**
- Tier 5 training pipeline.

**Prerequisites:**
- Phase 9 complete.

**Acceptance Criteria:**
- [ ] Stripe events update org billing safely and idempotently.
- [ ] Onboarding resumes at last incomplete step.
- [ ] Critical test suite passes.
- [ ] Launch checklist items are all validated.

**Files/Folders to be created or modified:**
- `pfam-backend/app/routers/billing.py`
- `pfam-backend/app/routers/webhooks/stripe.py`
- `pfam-frontend/src/app/(dashboard)/settings/billing/page.tsx`
- `pfam-frontend/src/app/(dashboard)/onboarding/page.tsx`
- `pfam-backend/tests/*`
- `pfam-frontend/tests/*`

**Cursor Prompt:**  
PFAM has core product features complete. Build billing + onboarding and finish production hardening. Reference `@PFAM_SRS_v2.docx`, `@PFAM_Product_Requirements_Document.docx`, and `@PFAM_Implementation_Plan_v1.docx`.

Implement Stripe checkout/portal/subscription endpoints and webhook consumer with signature verification + idempotent event handling. Build onboarding wizard pages for Shopify, ad account connects, COGS setup, first rule, and completion state with persisted progress.

Add tests for tenant isolation, money precision (cents), sync idempotency, guardrails, and role permissions. Wire basic observability (errors + key metrics) required for pre-launch confidence.
Do not build anything outside this scope. Ask me before making assumptions.

**Micro-Phases (execute in order):**
- **10A — Stripe Billing:** checkout, portal, webhook verification, plan state sync, payment-failure handling.
- **10B — Onboarding:** 5-step resumable wizard with connector/COGS/first-rule path.
- **10C — Hardening:** test suite expansion, observability baseline, launch checklist sign-off.

---

## Phase 11: Tier 5 ML Attribution
**Goal:**  
Add ML-based attribution as a controlled enhancement after enough Tier 1/2 labeled data exists.

**Scope (What we're building):**
- Feature engineering pipeline from labeled attribution data.
- XGBoost training workflow, evaluation gates, model versioning, artifact storage.
- Weekly retrain job and safe promotion logic.
- Runtime Tier 5 inference in attribution orchestrator with confidence threshold fallback to Tier 4.

**Out of Scope (What we're NOT building yet):**
- New non-attribution ML features.

**Prerequisites:**
- Phase 10 complete.
- At least 500 Tier 1/2 labeled orders.

**Acceptance Criteria:**
- [ ] Model meets minimum quality threshold before promotion.
- [ ] Inference only used above confidence threshold.
- [ ] Graceful fallback to Tier 4 when model unavailable/low confidence.

**Files/Folders to be created or modified:**
- `pfam-backend/app/services/attribution/tier5_ml.py`
- `pfam-backend/app/ml/train_model.py`
- `pfam-backend/app/workers/train_ml_model.py`
- `pfam-backend/app/services/attribution/orchestrator.py`

**Cursor Prompt:**  
PFAM is in production with tiers 1-4 attribution and enough labeled data. Build Tier 5 ML attribution now as a controlled incremental upgrade. Reference `@PFAM_SRS_v2.docx`, `@PFAM_Product_Requirements_Document.docx`, and `@PFAM_Implementation_Plan_v1.docx`.

Implement feature engineering, XGBoost training/evaluation/versioning, and weekly retrain worker. Add model serving/inference in `tier5_ml.py` and orchestrator integration so Tier 5 is attempted after Tier 3 and before Tier 4 fallback. Apply confidence threshold gate and safe degradation when model is missing or not confident.

Ensure full auditability of model version, metrics, and retraining events.
Do not build anything outside this scope. Ask me before making assumptions.

---

## Vibe Coding Tips
- Finish one phase completely before touching the next; avoid “just one extra feature.”
- Keep prompts phase-specific and include only relevant files in Cursor context.
- Run tests and manual acceptance checks at phase end; do not trust green compile alone.
- Commit after each phase with a crisp message tied to phase objective.
- Validate tenant isolation and money precision repeatedly (these are non-negotiable).
- Treat retries/idempotency/audit logging as first-class behavior, not cleanup work.
- Keep feature flags or draft toggles for risky automation paths.
- If any requirement is ambiguous, stop and ask before implementing assumptions.
