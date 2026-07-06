# Mobius OS
> A context-aware browser extension that surfaces the "why won't this get paid?" story on the patient/claim you're already looking at — inside your existing EMR/CRM, without switching apps.

## Purpose
Mobius OS is an AI-native browser extension that layers on top of the third-party applications a revenue-cycle or front-desk team already uses (EMR, scheduler/CRM). As you navigate to a patient or claim, it detects the record in context and surfaces a compact **System Response**: a payment-probability read, the specific factors ("bottlenecks") blocking payment, and the concrete step needed to clear them. It presents this information without demanding action — you can acknowledge it, act on it, note it, hand it to a teammate, or ignore it.

Per the Phase 1 PRD, Mobius is explicitly a **response + acknowledgement system**, not a task manager, workflow engine, or system of record. It never owns the underlying record; it observes what you're doing, computes a recommendation, and records whether you acknowledged it. The extension exposes this through progressively larger surfaces — a floating **Mini** widget, an expanded **Sidecar** panel, and a **Chat** conversation — backed by a Flask/PostgreSQL service.

## Audience
Revenue-cycle and clinic operations staff working inside an EMR or scheduling system. Onboarding and task-visibility are keyed to a user's configured **activities** (role-like tags), so the same extension shows different work to different people:
- **Front-desk / schedulers** — appointment confirmation, patient outreach, check-in (`schedule_appointments`, `patient_outreach`, `check_in_patients`)
- **Eligibility specialists** — insurance verification, coverage/benefits checks (`verify_eligibility`)
- **Billing / claims specialists** — claim submission, denial rework, payment posting, collections (`submit_claims`, `rework_denials`, `post_payments`, `patient_collections`)
- **Clinical staff** — prior authorization, documentation, referral coordination (`prior_authorization`, `document_notes`, `coordinate_referrals`)
- **Admins** — bypass activity filtering and see **all** tasks across roles

## Capabilities
- **In-context record detection** — recognizes the patient/claim you're viewing on a supported page and surfaces relevant state automatically.
- **Mini widget** — compact floating surface showing a personalized greeting, the current record's status (proceed / pending / error indicator), and activity-filtered quick actions.
- **Sidecar panel** — expanded view centered on **bottlenecks/factors** blocking payment, with per-factor cards, evidence, alerts, and a cross-patient alert inbox.
- **Payment-probability + resolution model (L1–L4)** — L1 payment probability, L2 multi-step resolution plans, L3 individual plan steps (questions/actions), L4 supporting evidence and source facts.
- **Question-by-question resolution** — answer plan-step questions (e.g. "Insurance card on file?", "Is coverage currently active?"), add notes, submit/skip/escalate steps.
- **Task assignment & handoff** — own a task, assign (single or bulk) to a teammate, reassign, or escalate; users see "waiting on another team member" when a step belongs to a different activity.
- **Activity-based task filtering** — each user sees only the plan steps whose `assignable_activities` overlap their configured activities (admins see all). Note: in the current seed data (`backend/scripts/seed_production_12.py`) only scheduling, outreach, and eligibility plan steps are seeded — no plan step is assignable to the billing/claims activities (`submit_claims`, `rework_denials`, `post_payments`, `patient_collections`), so a claims-only user currently sees no tasks. See "Not yet available (planned)" below.
- **Chat mode** — conversational surface for asking questions in context; includes a "thinking" display, guidance/next-step actions, and thumbs-up/down feedback. Chat is the extension's default in-page mode and is wired end-to-end (input → `sendChatMessage` → backend `/api/v1/modes/chat`).
- **Corpus / knowledge search skill** — a backend skills API (`POST /api/v1/skills/corpus_search`) that proxies to the mobius-rag corpus-search service. It is called by the decision agents and is available to other services (chat, extension), but it is **not exposed as a user-facing search entry point in the extension UI** — the extension source contains no reference to it.
- **Personalized onboarding & preferences** — set preferred name, activities, tone, greeting on/off, AI experience level, and autonomy levels for routine vs. sensitive tasks (automatic / confirm-first).
- **Per-domain activation** — the extension popup lets you allow or disallow Mobius on the current site's domain.
- **Acknowledgement audit trail** — every system response and its acknowledgement (or absence) is event-logged for auditability.

## Navigation & Access
- **Install/load** — Chrome extension loaded from `extension/dist` (Developer mode → Load unpacked); production build ships as a packaged extension.
- **Extension popup** — toolbar icon opens a popup used to allow/deny Mobius on the current domain (`mobius.allowedDomains`).
- **In-page surfaces** (injected by the content script on allowed pages):
  - **Mini** — the floating widget; the default compact surface.
  - **Sidecar** — the expanded panel (opened from Mini).
  - **Chat** — conversational surface within the extension.
- **Header / mode badge** — a `ModeBadge` renders whatever mode string it's handed. In the shipping extension only **Chat** is a wired mode (`getUiDefaultsForMode` in `extension/src/utils/uiDefaults.ts` has a single `case 'chat'`; everything else falls through to the default layout). The other named modes (Eligibility, Front Desk, Backend, Email Drafter) appear only in `components-list.md` and `ui-mockup.html` — they are not distinct live modes. See "Not yet available (planned)".
- **Settings & footer** — gear/settings button opens preferences; footer shows user details and a preferences panel (LLM choice, agent mode).
- **Mock demo pages** — the backend serves `/mock-emr` and `/mock-crm` for demoing detection without a real EMR/CRM.

> Note: "Pipeline" and "Provider Hub" launcher cards referenced in recent commits live in the separate **landing/** module (`landing/index.html`), **not** in mobius-os. They are shortcuts on the platform landing page, not features of this extension.

## Key User Workflows

1. **Turn Mobius on for a site and see a record**
   1. Load/install the extension.
   2. Navigate to your EMR/scheduler and open the toolbar popup; allow Mobius on that domain.
   3. Open a patient/claim page — the Mini widget appears with a greeting, the record's status indicator, and quick actions filtered to your activities.

2. **Resolve a payment bottleneck via the Sidecar**
   1. From Mini, expand into the Sidecar for the current patient.
   2. Review the factor/bottleneck cards and their evidence (L2–L4).
   3. Answer the open plan-step question(s), add a note if needed, and submit — or skip/escalate.
   4. If the step isn't yours, hand it off by assigning it to the responsible teammate.

3. **Triage across patients from the alert inbox**
   1. Open the user alerts view (cross-patient alerts).
   2. Pick up an unacknowledged system response, mark alerts read, and act or reassign.
   3. Use bulk assign to distribute several tasks to teammates at once.

4. **Onboard and personalize**
   1. Register / sign in (email or Google).
   2. Complete onboarding: preferred name, your activities, tone, greeting, AI experience level, and autonomy for routine vs. sensitive tasks.
   3. Adjust later via the settings/preferences panel; your activities determine which tasks you'll see going forward.

## Integrations
- **Host applications** — injects into third-party EMR and CRM/scheduler web apps (with mock EMR/CRM pages provided for demos).
- **Backend service** — Flask API on Cloud Run + Cloud SQL (PostgreSQL 15), Secret Manager, Cloud Build; optional Firestore. Local dev server on `http://localhost:5001`.
- **Auth** — email/password and Google sign-in; JWT access/refresh tokens.
- **Skills / corpus search** — `POST /api/v1/skills/corpus_search` (`backend/app/api/skills.py`) is a thin proxy over `backend/app/services/corpus_search.py`, which calls the **mobius-rag** service at `POST /api/skills/v1/corpus_search` (base URL from the `RAG_API_URL` env var). It is used by the decision agents and available to other services; it is not surfaced in the extension UI.
- **Landing / launcher** — Mobius OS is one surface in the broader Mobius platform whose landing page (separate `landing/` module) links to Chat, Pipeline, Provider Hub, and Credentialing.

## Not yet available (planned)
These are described in mockups/docs or scaffolded in code but are **not shipped** as end-user features in the current build. Do not present them as available capabilities.

- **Multi-mode workflow badge** — the mockups (`ui-mockup.html`, `components-list.md`) show Eligibility / Front Desk / Backend / Email Drafter modes, but only **Chat** is a wired mode in the extension. The `ModeBadge` component displays whatever string it is given and there is no live mode-switching UI (the mode-change hook in `content.ts` is an example comment, not wired). Planned — not shipped.
- **Billing / claims tasks** — the billing/claims activities exist and can be assigned to a user, but no plan steps are seeded for them, so claims-only users currently see no work. `USER_TASK_MAPPING.md` flags this explicitly ("Claire Claims — No Tasks Defined") and recommends adding PlanSteps with `assignable_activities: ["submit_claims","rework_denials","post_payments","patient_collections"]`. Planned — not shipped.
- **User-facing corpus / knowledge search** — the corpus-search skill is a backend proxy consumed by the decision agents; there is no search box or knowledge-search entry point in the extension UI. Planned — not shipped as a user surface.
- **Legacy Sidecar endpoints** — `backend/app/modes/sidecar.py` is explicitly marked legacy and retained only for backwards compatibility; the current UI uses the bottleneck-focused API in `backend/app/api/sidecar.py`. Legacy endpoints are not part of the shipping product surface.
- **`post_payments` / `patient_collections` activity codes** — used in the seed script but not present in the canonical `ACTIVITY_CODES` list (`backend/app/models/activity.py`); treat as provisional until reconciled.

## Doc-readiness notes
- **Primary audience tag:** mixed (user-facing product story is clear, but current artifacts — PRD, README, USER_TASK_MAPPING, components-list — are written for the build team).
- **What's solid:**
  - Core concept and surfaces (Mini / Sidecar / Chat) and the response→acknowledgement model are well-specified in the Phase 1 PRD.
  - Role/activity → task-visibility mapping is documented in detail (USER_TASK_MAPPING.md).
  - Auth, onboarding, preferences, and the resolution/assignment API are concrete in code.
  - Deployment/architecture is well-documented.
- **Resolved against code (see "Not yet available (planned)"):**
  - **Workflow modes** — only Chat is wired; the other named modes are mockup/docs-only.
  - **New vs. legacy Sidecar** — `backend/app/modes/sidecar.py` is explicitly legacy; `backend/app/api/sidecar.py` (bottleneck-focused, `/api/v1/sidecar/*` + `/api/v1/user/alerts`) is the current API and both blueprints register in `backend/server.py`.
  - **Chat** — wired and user-exposed as the default in-page mode.
  - **Corpus search** — backend proxy to mobius-rag; not a user-facing UI surface.
  - **Billing/claims tasks** — activities exist but no plan steps are seeded, so claims-only users see no tasks.
- **Gaps a human must fill:**
  - Confirm supported/target EMR & CRM applications by name. [UNVERIFIED: the mock EMR/CRM pages emulate several styles (epic, cerner, allscripts, athena, netsmart, qualifacts, etc.), but real supported hosts are a product/GTM decision not determinable from code.]
  - Confirm the default Mini → Sidecar → Chat entry gestures for end users (code shows Chat as the default in-page surface; explicit open/expand gestures should be confirmed by exercising the built extension).
  - Screenshots of the real (non-mockup) Mini and Sidecar surfaces.
