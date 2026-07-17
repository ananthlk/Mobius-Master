# Credentialing & Roster
> Keep an accurate master list of your organization's providers, and prove which of them are enrolled and payable under FL Medicaid — from a single upload.

## Purpose

**Roster** is the source-of-truth list of the clinicians who work for a provider organization. You upload your provider list (Excel or CSV), and the system parses it, diffs it against the existing master roster, and commits a change-tracked record per provider (identity, credential, taxonomy, license, Medicaid ID, employment status). From there, each provider can be validated against external registries — NPPES (the national provider registry), Florida Medicaid PML (enrollment), and the FL Medicaid taxonomy list (billing eligibility) — with the results and any data-quality flags stored back on the roster.

**Credentialing** answers the money question: *is this provider actually enrolled and payable?* In this product, a "credentialing run" is a reconciliation between two views of an organization's providers — the roster the org uploaded (internal) and the providers Mobius independently finds billing under the org from Medicaid claims and address data (external). Every provider (NPI) is tagged `in_both`, `external_only` (billing under the org but not on the roster — ghost-billing risk), or `internal_only` (on the roster but not found enrolled/billing — validate why). The run produces a waterfall audit report (guaranteed / at-risk / missing / taxonomy-opportunity buckets) with the enrollment status featured throughout. Roster feeds credentialing: a clean, validated roster is the internal input to the credentialing reconciliation.

## Audience

- **Provider-organization admins / credentialing staff** — the primary users. They maintain the roster, upload updated provider lists, term/reactivate providers, and run credentialing checks to confirm enrollment and catch compliance gaps.
- **Mobius internal operators / analysts** — kick off full credentialing runs for an org, review decisions/blockers, and read the audit report. Note: the split between self-serve org users and Mobius-operated runs is a positioning/UX distinction, not a technical boundary — neither front-end (Providr roster UI or the credentialing-home console) enforces authentication, login, or roles in the current code, and both read a shared task/run feed. Access control is not yet implemented.

## Capabilities

> Joining your org — self-claim → pending → approve — SHIPPED 2026-07-15 (User Manager agent); see the *Invites, set-password & joining your org* section of the user-and-auth doc. It was previously listed as planned here.

### Ask in chat — the primary access point (2026-07)
**Chat is now the front door for credentialing questions**; the roster UI remains for deep work, reached via a chip. Backed by the `check_provider_credentialing` MCP tool:

- **Single-provider profile** — ask about a provider (by NPI) and get: NPPES validation status + taxonomy on file, FL Medicaid PML enrollment status + next revalidation date, compliance results with severity labels, license number / Medicaid ID / specialty, the last 3 change events, and a **readiness verdict**: clean · review_needed · action_required · incomplete. The answer includes a structured **credentialing card** (provider name, org, status, flags with severity, action link) rendered by the chat UI alongside the text.
- **Org panel summary** — ask without an NPI ("credentialing report for [org]", "how is [org]'s panel doing?", "NPPES errors for [org]") and get the verdict count breakdown, validation coverage per source (NPPES / PML / compliance — how many checked, when last run), and a **providers-needing-attention list** with per-provider issue summaries and deep links.
- **Open Credentialing Report chip** — credentialing-keyword questions carry an action chip into the full roster UI. Links are chips now; inline URLs no longer appear in the response text.
- **Appeals link** — appeal-related questions surface an Appeals Agent link chip (appeals rules/playbook/letter tools are wired in chat).
- **Tasks** — credentialing runs create tasks (`kind=credentialing`, `audience=provider`) visible in the chat task UI.

### Roster (provider-roster-credentialing service — the "Providr" app)
- Upload a provider roster from Excel/CSV; the parser normalizes names, credentials, taxonomy, license, and Medicaid IDs (including dual/pending/missing handling).
- Two-phase upload: **preview a diff** (adds/changes/terms vs. current master) before committing, or single-shot **ingest** (parse + commit in one call).
- Master roster view per org with **Active / Termed** tabs and per-provider detail drawer.
- Add a provider manually; **term / reactivate / suspend / mark on-leave** a provider (status change is logged as a change event).
- **Run checks** per provider or across the whole org (refresh-all).
- **NPPES validation** — flags name mismatch, deactivated NPI, taxonomy mismatch.
- **FL Medicaid PML validation** — enrollment status, Medicaid-ID consistency, revalidation-overdue; flags `pml_not_found`, `pml_inactive`, `pml_medicaid_id_mismatch`, `pml_revalidation_overdue`.
- **Taxonomy billing validation** against the FL Medicaid approved-taxonomy list (~826 codes); flags codes not billable.
- **Compliance check** across the roster — surfaces termed providers still active in NPPES/PML (ghost-billing risk) and active providers missing from PML (enrollment gap).
- **Gap analysis** — compares the org's market reference (`org_npi`) against the active roster into three buckets: confirmed, new-in-roster (new hire), unrostered (billing without a credentialing record).
- **Provider intelligence profile** — one card aggregating roster record + NPPES + PML + compliance + change history.
- **Freshness** view — last-checked timestamps and coverage % per check type.
- Change-event log per org / per provider.

### Credentialing (reconciliation runs + audit report)
> **Owner correction 2026-07-14:** the batch report pipeline described below is the legacy path — per the module owner it has been removed in favor of the real-time DB profile read behind `check_provider_credentialing` (chat-first, above). The old MCP tools (`run_credentialing_report`, `run_roster_reconciliation_report`, `validate_credentialing_step`, `ask_credentialing_npi`, `lookup_npi`, `find_org_locations`, `find_associated_providers_at_locations`) are disconnected and no longer exist (NB: a same-named `lookup_npi` is LIVE in the FL-Medicaid analytics manifest — a distinct market-data identity tool over `billing_npi_profiles`, not this retired credentialing one; see skills.md); "credentialing generates a PDF report" no longer describes current behavior. The reconciliation *model* (in_both / external_only / internal_only, waterfall buckets) remains the conceptual frame. Sections kept below for the roster-UI surfaces that still exist; treat run/PDF mechanics as historical until re-verified.
- Start a **credentialing run** for an organization by name in one of two modes: **autopilot** (runs the full pipeline end-to-end in the background) or **copilot** — "Step-by-step (co-pilot)" — which runs one step at a time and pauses for the user to validate each step before advancing (`POST /chat/credentialing-runs/{id}/validate`). These are the only two modes in code (`mode: Literal["autopilot", "copilot"]`). The API request default is `copilot`; the credentialing-home "New run" dropdown defaults to autopilot ("Full credentialing run").
- Pipeline: identify org locations → find associated/billing providers → PML enrollment validation → opportunity sizing, with a reconciliation status tagged on every NPI.
- **Reconciliation status** (`in_both` / `external_only` / `internal_only`) tagged on every provider and featured throughout the report.
- **Panel Credentialing Audit Report** — waterfall structure (Section A enrolled/guaranteed, B at-risk, C missing/unenrolled, D taxonomy-opportunity, E benchmarking vs. DOGE/All FL Medicaid claims), executive summary, issues across the panel, per-provider profiles; exportable as PDF. The full pipeline runs 11 steps: org ID → provider association → location rollup → PML validation → opportunity sizing → rate-gap analysis → benchmarking → AI draft (up to 3 retries) → validation → composition → charts + PDF export.
- **Ask** questions against a completed run / report (`/report-runs/{id}/ask`) and against financial strategy.
- Operational hub of **active runs, decisions pending, and blockers**, with per-task "Ask Mobius" and "Mark resolved" actions.
- Compare report runs and view the latest run per org.

## Navigation & Access

Two front-ends cover these features (ports are the local-dev defaults from the launcher):

- **Providr / Provider Hub** (roster + per-org checks) — static app served by the `provider-roster-credentialing` service at `http://localhost:8011/roster-ui/`.
  - `roster.html` — **Roster** (master list, Active/Termed tabs, add/term, Run Checks)
  - `run.html` — **Credentialing Checks**
  - `report.html` — **Panel Credentialing Audit Report**
  - `org.html` — **Org Profile**; `intelligence.html` — **Org Intelligence**; `tables.html` — **Reference Data**; `displacement.html`, `story.html` — market analyses
  - The app's `index.html` links back to a **Main Dashboard** and out to the **Pipeline** (chat service).
  - **Architecture schematic ↗** — a header link on the Providr admin surface (live 2026-07-17, rev 00066) opens the fleet-ratified platform schematic (`https://mobius-chat-ortabkknqa-uc.a.run.app/platform`) in a new tab: every module in five columns, User + Technical lenses, honest live/partial/planned status. The role-appropriate admin front door to the map (everyone else reaches it via the chat sidebar's Platform tile).
- **Credentialing home / operational console** — `landing/credentialing-home.html` (titled "Credentialing — Mobius"). Tabs/filters: **Active runs · Decisions pending · Blockers · Completed runs**. "New run" panel takes an org name + mode and starts a run; run cards deep-link to the **roster workflow** feed (`roster-workflow.html?run_id=…`, workflow base `http://localhost:3999`). Related landing pages: `org-profile.html`, `roster-preview.html`, `roster-workflow.html`, `workflow-explorer.html`.
- **Launcher entry points** (`landing/index.html`): a **Credentialing** worker card linking to Provider Hub / Org / Roster (`:8011/roster-ui/…`) and Pipeline (`:8000/pipeline`); a top-nav "Provider Hub" link.

API surface (service base, roster router prefix `/roster`): `POST /roster/{org}/upload` (preview), `/commit`, `/ingest`; `GET /roster/{org}`, `/{npi}`, `/events`, `/flags`, `/freshness`, `/gap`, `/{npi}/intelligence`; `POST /{org}/validate/{nppes|pml|taxonomy}`, `/{org}/compliance`; `PUT /{org}/{npi}/status`. Credentialing runs are driven through the chat backend (`POST /chat/credentialing-runs`, `…/{id}/validate`) and reporting router (`/roster-reconciliation-report/from-bq`, `/report-runs/*`). A skill interface exposes `POST /skill/roster/ask`, `POST /skill/credentialing/ask`, and `POST /skill/ask` (auto-routes via classifier) for chat; `GET /skill/schema` for introspection.

## Key User Workflows

1. **Upload / update the roster**
   1. Open Provider Hub → Roster (`:8011/roster-ui/roster.html`) and load your org (org name → slug).
   2. Upload your provider list (Excel/CSV). Review the parsed diff preview (adds / changes / terms).
   3. Commit. Providers are written to the master roster with change events recorded.

2. **Validate providers & catch compliance gaps**
   1. From the roster, click **Run Checks** on a provider, or **Refresh all** for the whole org.
   2. This runs NPPES, PML, and taxonomy validation and stores snapshots + flags.
   3. Open the **compliance** view to see ghost-billing risks (termed but still active in NPPES/PML) and enrollment gaps (active but missing from PML). Fix flagged providers or update their status.

3. **Add or term a provider**
   1. In the roster, use **+ Add Provider** to add manually, or open a provider's detail drawer.
   2. Use **Term Provider** (or the status control) to set active / termed / suspended / leave. The change is logged and the provider moves to the Termed tab.

4. **Run a full credentialing check for an org**
   1. In Credentialing home (`landing/credentialing-home.html`), click **New run**, enter the org name, pick a mode, and **Start run →**.
   2. Follow the live run feed (`roster-workflow.html?run_id=…`): locations → associated providers → PML validation → opportunity sizing, with each NPI tagged in-both / external-only / internal-only.
   3. Resolve any **decisions pending** and **blockers** from the hub cards ("Ask Mobius" / "Mark resolved").
   4. Open the **Panel Credentialing Audit Report** to see the A/B/C/D waterfall and per-provider profiles; export to PDF or **Ask** follow-up questions.

## Integrations

- **Postgres (skill-owned tables)** — `provider_roster` master (FK to `org_profile`), plus `provider_nppes_snapshot`, `provider_pml_snapshot`, `provider_compliance_flags`, `org_npi`, `briefing_modules` (org narrative/story content, migration 028), and NPPES-provenance tables (migrations 015–029).
- **BigQuery** — reads Medicaid claims / billing (referred to internally as **DOGE**, staged as `stg_doge`) plus PML/TML staging tables (`stg_pml`, `stg_tml`, `stg_ppl`) to build the external roster and opportunity sizing; a BQ↔mart sync migration (027) exists. Dataset names are **not hard-coded** — they are resolved from environment variables. The landing (staging) dataset comes from `BQ_LANDING_MEDICAID_DATASET` (dev default `landing_medicaid_npi_dev`) and the marts dataset from `BQ_MARTS_MEDICAID_DATASET` (dev default `mobius_medicaid_npi_dev`). The name `landing_credentialing` does **not** appear anywhere in this service's code; the "co-owned `landing_credentialing` dataset" described in internal module-sync notes is not confirmed by code. Confirm the live dataset ids in the deploy environment.
- **NPPES registry** (live lookups) and **FL Medicaid PML / TML** (enrollment + billable-taxonomy reference).
- **Chat / Pipeline service** (`mobius-chat`, port 8000) — hosts the `/chat/credentialing-runs` endpoints that the credentialing-home console calls, and consumes the `/skill/roster/ask` + `/skill/credentialing/ask` skill endpoints. The workflow feed runs on a separate front-end (port 3999).
<!-- INTERNAL NOTE (not for user-facing docs): internal module-sync notes flag a possible DOGE double-compute concern between credentialing and roster and the absence of a scheduling cron. This is an open, unverified data-integrity risk, not a documented product behavior — do not surface it to users until a human confirms and it is resolved or owned. -->
- **DOGE / Medicaid billing** is read from BigQuery to compute the external (billing) view of the roster and opportunity sizing.

## Not yet available (planned)
- **Task status signals back from runs** — `emit_signal` client + waterfall wiring (`source_ref=run_id`): tasks are created via `bulk_import_tasks` v1 today, but they don't auto-update when a credentialing run completes.
- **Per-org private document store** — `POST /org/{slug}/doc-store/provision` is built (instant-RAG/Vault contract locked) but waits on the provisioner URL from RAG/Instant-RAG.
- **Org-registry enforcement** — org validation runs in warn mode (unresolved orgs are logged); per-writer enforcement pending Ananth's review (~2026-07-16).
- **Richer credentialing modal** — a UI modal with richer navigation of credentialing data (flagged by Ananth; frontend work not started).

## Doc-readiness notes

- **Owner inventory folded 2026-07-14** (Roster & Credentialing agent). Verified live before folding: `check_provider_credentialing` + 4 `appeals_*` tools in the dev skills manifest; old tool names absent as tools; `credentialing_card` + action chips present in the served chat bundle (rev 00448). NOT re-verified against service code: removal of the batch report/PDF pipeline (owner-attributed; see correction note above). Known manifest bug reported to owner: two stale "use ask_credentialing_npi" cross-references remain in other tools' guidance.
- **Primary audience tag:** mixed (leaning **user** for Roster; the Credentialing run console reads as **user/operator mixed**).
- **Solid (grounded in code):** roster upload/diff/commit flow; NPPES/PML/taxonomy validation and their flag names; compliance and gap buckets; status lifecycle; the credentialing = reconciliation model and A/B/C/D waterfall report; the two front-ends and their routes; the skill-interface split (roster = "who are my clinicians", credentialing = "are they enrolled/payable").
- **Resolved against code:**
  - Run **modes** — exactly two: `autopilot` (full pipeline) and `copilot` (step-by-step, validate per step). Confirmed in `mobius-chat/app/api/credentialing.py`.
  - **Self-serve vs. internal-operator** — not a code-enforced boundary: neither front-end has auth/login/roles. It is a UX/positioning distinction only.
  - **BigQuery dataset ids** — env-derived (`BQ_LANDING_MEDICAID_DATASET`, `BQ_MARTS_MEDICAID_DATASET`; dev defaults `landing_medicaid_npi_dev` / `mobius_medicaid_npi_dev`). `landing_credentialing` is NOT a literal in this repo.
  - `roster-workflow.html` (and `credentialing-home.html`, `roster-preview.html`, `workflow-explorer.html`) in `landing/` **are symlinks** into a git worktree (`.claude/worktrees/intelligent-archimedes/landing/…`), confirmed via `ls -la`. Treat their canonical source as that worktree, not `landing/` proper; confirm they are actually deployed before documenting as shipped.
- **Still needs a human:**
  - The **DOGE double-compute** concern and missing cron — an open, unverified internal risk; do not document as behavior (see internal note above).
  - **Ports/URLs** here are local-dev launcher defaults; the production URLs/menu paths need confirming.
- **Where the code lives (paths):**
  - Backend service: `/Users/ananth/Mobius/mobius-skills/provider-roster-credentialing/` — `provider_skill/main.py` (FastAPI app), `provider_skill/sub_skills/roster/routes.py` (roster API), `provider_skill/sub_skills/skill_interface/routes.py` (`/skill/roster|credentialing/ask`), `provider_skill/sub_skills/reporting/routes.py` (audit report + report-runs), `provider_skill/reconciliation_credentialing_flow.py` (credentialing = reconciliation), `provider_skill/roster_handler.py` (roster logic).
  - Roster/credentialing UI (Providr): `provider-roster-credentialing/static/*.html` (`roster.html`, `run.html`, `report.html`, `org.html`, `intelligence.html`, `index.html`).
  - Operational console + workflow UI: `/Users/ananth/Mobius/landing/credentialing-home.html`, `org-profile.html`, `roster-preview.html`, `roster-workflow.html`, `workflow-explorer.html`; launcher card in `landing/index.html`.
  - Data model: `provider-roster-credentialing/migrations/015_provider_roster.sql` (+ 016–029).
  - Specs: `provider-roster-credentialing/docs/RECONCILIATION_AS_CREDENTIALING_SPEC.md`, `WHY_CREDENTIALING_RUNS_DIFFER.md`, `OPPORTUNITY_SIZING_METHODOLOGY.md`, `ORG_SEARCH_API_CONTRACT.md`.
