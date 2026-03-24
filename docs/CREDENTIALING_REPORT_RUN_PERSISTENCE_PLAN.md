# Credentialing Report Run Persistence Plan

## Goal

Persist **every output of every step** for each credentialing report run, keyed by a **report creation id**, so we can:

- **Study** pipeline behavior, compare runs, and debug.
- **Fetch** a specific run by id (e.g. "show me the Aspire report from March 11").
- **Audit** what was produced (step CSVs, final report MD/PDF) without relying on chat response payload or in-memory store.

**Storage:** PostgreSQL for durability across restarts and multi-instance deployments.

---

## Scope

- **In scope:** Provider Roster / Credentialing pipeline (Steps 1–11). Each *run* produces:
  - Step outputs: identify_org, find_locations, find_associated_providers, org_benchmark, find_services_by_location, historic_billing_patterns, step_6 (PML), step_7 (missing PML), opportunity_sizing, build_report (draft, validation, compose, charts).
  - Final artifacts: report markdown, report PDF (optional), summary metrics.
- **Out of scope (for this plan):** Chat turn persistence (handled by existing PERSISTENCE_PLAN); this plan focuses on *report run* as a first-class entity. Chat can store `report_run_id` on the turn and resolve details via API.

---

## OrgStore vs report-run persistence (reconciliation)

There are **two persistence layers** that coexist and serve different purposes:

| Layer | Purpose | Scope |
|-------|---------|--------|
| **OrgStore** | Org-level stable values (org_benchmark, step1_benchmarks). Read-through cache so run 2 reuses run 1’s benchmark and produces identical numbers. | Per org_slug; shared across runs. |
| **Report-run persistence** | Run-level audit trail. Every step output and final doc stored per `report_run_id`. | Per run; immutable after completion. |

**Reconciliation rule:** Step outputs **always record the actual values used** in that run, regardless of source (OrgStore cache or fresh compute). This is required for audit: if someone fetches run 2 and the benchmark step has no output, they cannot tell what benchmark drove the numbers.

- When a step **computes** values: write a `ReportStepOutput` row with the computed content as usual; `cache_hit = false` (default).
- When a step **reads from OrgStore** (e.g. run 2 reads org_benchmark): still write a `ReportStepOutput` row with `content_type = 'json'`, `content` = the cached value that was actually used, and `cache_hit = true`. The row is the record of “this run used this benchmark”; it does not silently omit the step.

Implementing this in Phase 1 (before or with first deployment) avoids ambiguity and supports the study/audit use case from day one.

---

## Entity Model

```
ReportRun (1) ──┬── (1..n) ReportStepOutput   (one row per step, with csv_content / json_content)
                ├── (0..1) ReportSummary      (aggregate metrics: A/B/C counts, totals, readiness)
                └── (0..2) ReportDocument    (final_md, final_pdf — by type)
```

- **ReportRun:** One row per report creation. Identified by `report_run_id` (UUID). Captures org_name, org_slug, who triggered it (optional), when, status.
- **ReportStepOutput:** One row per pipeline step. Stores step_id, label, content (inline) or content_url (object storage), content_type, row_count, sort_order, and cache_hit when the step used OrgStore. Allows exact replay and comparison.
- **ReportSummary:** One row per run; denormalized totals (e.g. guaranteed, at_risk, missing, provider counts) for listing/filtering without parsing CSVs.
- **ReportDocument:** One row per document type per run (e.g. `final_md`, `final_pdf`). Small content inline; large (e.g. PDFs 2–5MB) offloaded to object storage in Phase 5 with URL stored.

---

## PostgreSQL Schema (proposed)

```sql
-- Report run: one per credentialing report creation
CREATE TABLE credentialing_report_runs (
    report_run_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_name        TEXT NOT NULL,
    org_slug        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running',  -- running | completed | failed | cancelled | stale
    error_message   TEXT,
    triggered_by    TEXT,          -- optional: correlation_id or user/session id from chat
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);
-- status: cancelled = run interrupted mid-pipeline; stale = OrgStore was invalidated after this run

CREATE INDEX idx_report_runs_org_slug ON credentialing_report_runs(org_slug);
CREATE INDEX idx_report_runs_created_at ON credentialing_report_runs(created_at DESC);

-- Per-step output: every step’s CSV (or JSON) stored here.
-- Large outputs (> ~50KB): write to object storage from day one, set content_url; content NULL.
-- Small outputs: store inline in content; content_url NULL.
CREATE TABLE credentialing_report_step_outputs (
    id              BIGSERIAL PRIMARY KEY,
    report_run_id   UUID NOT NULL REFERENCES credentialing_report_runs(report_run_id) ON DELETE CASCADE,
    step_id         TEXT NOT NULL,
    label           TEXT NOT NULL,
    content_type    TEXT NOT NULL DEFAULT 'csv',  -- csv | json
    content         TEXT,                         -- NULL when content_url is set (large output)
    content_url     TEXT,                         -- object storage URL when content length > threshold
    row_count       INT NOT NULL DEFAULT 0,
    sort_order      SMALLINT NOT NULL,
    cache_hit       BOOLEAN NOT NULL DEFAULT false,  -- true when step used OrgStore (cached value)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_step_outputs_run_step ON credentialing_report_step_outputs(report_run_id, step_id);
CREATE INDEX idx_step_outputs_run ON credentialing_report_step_outputs(report_run_id);

-- Summary metrics per run (for listing and filters)
CREATE TABLE credentialing_report_summaries (
    report_run_id   UUID PRIMARY KEY REFERENCES credentialing_report_runs(report_run_id) ON DELETE CASCADE,
    guaranteed      NUMERIC(18,2),
    at_risk         NUMERIC(18,2),
    missing         NUMERIC(18,2),
    taxonomy_opt    NUMERIC(18,2),
    rate_gap        NUMERIC(18,2),
    total_opportunity NUMERIC(18,2),
    provider_count_a INT,
    provider_count_b INT,
    provider_count_c INT,
    location_count  INT,
    readiness_score NUMERIC(5,2),
    summary_json    JSONB,        -- full summary from pipeline for flexibility
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Final documents: markdown and optional PDF.
-- content_bytes: PDFs are 2–5MB for large orgs; treat as temporary — move to object storage in Phase 5.
CREATE TABLE credentialing_report_documents (
    id              BIGSERIAL PRIMARY KEY,
    report_run_id   UUID NOT NULL REFERENCES credentialing_report_runs(report_run_id) ON DELETE CASCADE,
    document_type   TEXT NOT NULL,   -- final_md | final_pdf
    content         TEXT,            -- for final_md
    content_bytes   BYTEA,           -- for final_pdf; Phase 5: replace with content_url to object storage
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_report_docs_run_type ON credentialing_report_documents(report_run_id, document_type);
CREATE INDEX idx_report_docs_run ON credentialing_report_documents(report_run_id);
```

---

## Where to persist

**Recommendation:** Persist in the **provider-roster-credentialing** service (or a small persistence service it calls). Reasons:

- Single source of truth for report runs.
- All step outputs and final docs are produced there (or via its API).
- Chat becomes a client: it triggers a run (getting `report_run_id` back) and can store that id on the turn; fetching “that run” is a GET to the credentialing API with `report_run_id`.

**Alternative:** Persist from mobius-chat after the orchestrator completes (write all `roster_step_outputs` + final MD/PDF to Postgres). That duplicates storage logic in chat and ties persistence to the chat path; CLI or other clients would not persist unless they also call chat. Prefer **persistence inside the credentialing pipeline/API**.

---

## Setup (how to enable persistence)

1. **Database URL**  
   The provider-roster-credentialing process must see either `CHAT_RAG_DATABASE_URL` or `CREDENTIALING_REPORT_DB_URL` (e.g. from `mobius-config/.env`). The skill loads `mobius-config/.env` when run from the repo.

2. **Auto-enable**  
   Persistence turns **on** when a DB URL is set. To disable, set `CREDENTIALING_REPORT_PERSISTENCE_ENABLED=0` (or `false`/`no`).

3. **Run migrations**  
   **Preferred:** `./mstart` runs credentialing migrations automatically after mobius-chat migrations, using the same `CHAT_RAG_DATABASE_URL` (including via Cloud SQL Proxy when applicable). So if you start the stack with mstart, the DB is already connected and migrations run without a separate step.  
   **Manual:** If you're not using mstart or need to run migrations alone:
   ```bash
   cd mobius-skills/provider-roster-credentialing && uv run python scripts/run_migrations.py
   ```
   The script loads `mobius-config/.env` so no need to export the URL first. When connecting directly to Cloud SQL (e.g. 34.135.72.145) times out, use mstart so the proxy is up and the URL is rewritten to 127.0.0.1:5433.

4. **Restart the skill**  
   After env and migrations are in place, restart the provider-roster-credentialing API. New report runs will create a row, emit "Storing this report for future use." in chat, and persist steps + summary + final MD/PDF on completion.

5. **Verify a run persisted**  
   After running a report, list runs for the org (provider-roster-credentialing must be running, e.g. via mstart):
   ```bash
   curl -s "http://localhost:8011/report-runs?org_slug=circles-of-care&limit=5" | jq .
   ```
   If persistence is on and the run completed, you'll see `runs` with at least one entry and `report_run_id`, `status`, `created_at`. If you see `"detail": "Report run persistence is disabled"` (503), check that the skill was started with `CHAT_RAG_DATABASE_URL` set (and, when using mstart, the skill now gets the proxy URL so it can connect).

6. **End-to-end: produce report and verify persistence**  
   From a host where the DB is reachable:
   ```bash
   # Terminal 1: start the skill (loads mobius-config/.env)
   cd mobius-skills/provider-roster-credentialing && uv run uvicorn app.main:app --port 8010

   # Terminal 2: run migrations, run report, verify GET /report-runs
   cd mobius-skills/provider-roster-credentialing && uv run python scripts/run_report_and_verify_persistence.py "Circles of Care"
   ```
   The script runs migrations, runs the orchestrator for the given org, then calls `GET /report-runs?org_slug=...` to confirm the run was stored. If the DB is unreachable, migrations and persistence will fail; the report still completes but is not stored.

---

## API surface (provider-roster-credentialing)

- **Create run (start):**  
  `POST /report-runs`  
  Body: `{ "org_name": "...", "triggered_by": "optional-correlation-id" }`  
  Response: `{ "report_run_id": "uuid", "org_slug": "...", "status": "running" }`

- **Append step output:**  
  `PUT /report-runs/{report_run_id}/steps`  
  Body: `{ "step_id": "...", "label": "...", "content_type": "csv"|"json", "content": "...", "content_url": "..." (optional), "row_count": N, "sort_order": K, "cache_hit": false|true }`  
  For steps with output size > ~50KB, client writes to object storage and sends `content_url`; `content` may be omitted or truncated. Idempotent per (report_run_id, step_id) if using upsert.

- **Complete run / set summary and documents:**  
  `PUT /report-runs/{report_run_id}/complete`  
  Body: `{ "status": "completed", "summary": { ... }, "final_md": "...", "final_pdf_base64": "..." }`  
  Writes `credentialing_report_summaries` and `credentialing_report_documents`.

- **Get run (for “fetch a particular run”):**  
  `GET /report-runs/{report_run_id}`  
  Response: run row + step_outputs (list) + summary + documents (final_md, final_pdf if present).

- **List runs (for study / UI):**  
  `GET /report-runs?org_slug=aspire-health&from=...&to=...&limit=50`  
  Response: list of runs with summary fields (no full step content); client can GET by id for full detail.

- **Compare two runs (for study / delta):**  
  `GET /report-runs/compare?run_a={uuid}&run_b={uuid}`  
  Response: side-by-side summary fields (guaranteed, at_risk, missing, readiness_score, provider counts, etc.) for both runs. Avoids client-side double GET + diff.

- **Time-series / scoring:**  
  The schema supports first-class time-series use cases (FL BH readiness median, score trending, delta reports) without a dedicated endpoint. Example query:
  ```sql
  SELECT r.created_at, s.readiness_score, s.guaranteed, s.total_opportunity, s.provider_count_a
  FROM credentialing_report_runs r
  JOIN credentialing_report_summaries s USING (report_run_id)
  WHERE r.org_slug = 'aspire-health' AND r.status = 'completed'
  ORDER BY r.created_at DESC;
  ```
  This drives median readiness across orgs, run-over-run deltas, and trend dashboards. Document this in API docs so consumers treat it as a supported pattern, not an afterthought.

- **Fail run:**  
  `PUT /report-runs/{report_run_id}/complete` with `status: "failed"`, `error_message: "..."`.

---

## Integration with chat

1. When chat triggers a credentialing report:
   - Chat calls the credentialing API (e.g. existing report-from-steps flow). The **credentialing service** creates the run (`POST /report-runs`), runs the pipeline, and **inside the credentialing service** writes each step via `PUT .../steps` and completion via `PUT .../complete`. The orchestrator **never** calls the persistence endpoints directly; it only invokes the credentialing API, which performs persistence as part of its own flow.
   - Credentialing API returns `report_run_id` in the response; chat stores that in its turn payload (and in DB if desired).
2. Chat stores `report_run_id`. The full step outputs and documents live in the report-run store only.
3. “Fetch a particular run”: Frontend or user asks “show me run X” → call `GET /report-runs/{report_run_id}` and display steps + final report. Chat can also show a link or embed using this API.

---

## Implementation phases

| Phase | Scope |
|-------|--------|
| **1. Schema + write path** | Add PostgreSQL schema (migration); implement `POST /report-runs`, `PUT .../steps`, `PUT .../complete` in provider-roster-credentialing; persist step outputs (with cache_hit when from OrgStore) and summary/documents. **OrgStore reconciliation:** when a step reads from OrgStore, still write a step output row with the cached value and `cache_hit = true`. |
| **2. Read API** | Implement `GET /report-runs/{id}`, `GET /report-runs` (list with filters), and `GET /report-runs/compare?run_a=&run_b=`. Document time-series query pattern (readiness_score, summary fields by org_slug and created_at). |
| **3. Orchestrator integration** | **Definitive:** Persistence calls happen **inside the credentialing service only**. The credentialing API creates the run, runs the pipeline, and after each step (or at end) writes step output and completion to the report-run store. The chat orchestrator never calls the persistence endpoints directly; it only invokes the credentialing API, which performs persistence as part of its own flow. |
| **4. Chat payload** | Include `report_run_id` in chat response payload and optionally in turn persistence so the UI can “View run” / “Download report from run”. |
| **5. Object storage (planned)** | **Planned, not optional.** From day one, step outputs larger than ~50KB are written to object storage (S3/GCS); store URL in `content_url`, leave `content` NULL. PDFs (2–5MB) in `content_bytes` are temporary; Phase 5 moves them to object storage and adds `content_url` (or equivalent) to `credentialing_report_documents`. Schema is already designed for this (nullable content, content_url on step_outputs). |

---

## Cross-run stability (OrgStore) — known gaps

- **step1_benchmarks:** Written on first `/benchmarks-export` with `org_slug`; subsequent runs read from store so D uplifts and benchmarks stay locked. Ensure OrgStore write is not silently failing (e.g. log on `set_org` failure).
- **hcpcs_billing:** Not in OrgStore read path yet — HCPCS table (e.g. T1017 claim counts) can vary run-over-run until cached per org.
- **A provider count / roster_snapshot:** Provider discovery (steps 3 + 6) may not be fully covered by a single roster snapshot; run-over-run drops (e.g. TOVAR, CLEMENT) can occur until roster_snapshot is populated and used for A/B/C inputs.

---

## Configuration

- **Database URL:** e.g. `CREDENTIALING_REPORT_DB_URL` or reuse existing chat/rag Postgres URL with a dedicated schema (e.g. `credentialing`) to keep tables separate.
- **Feature flag:** Optional `CREDENTIALING_REPORT_PERSISTENCE_ENABLED=true` to turn on writes and reads without breaking existing flows.

---

## Success criteria

- Every report run has a unique `report_run_id`.
- Every step’s output (CSV or JSON) is stored and retrievable by run id; steps that used OrgStore have a step output row with the cached value and `cache_hit = true`.
- Final report (markdown and PDF if generated) is stored and retrievable by run id.
- A user (or system) can list runs by org and time range, fetch any run by id, and compare two runs (e.g. run_a vs run_b) for study or re-download.
- Large step outputs (> ~50KB) and eventually large PDFs use object storage with URLs in the schema; no painful migration later.

This plan keeps persistence focused on report runs in PostgreSQL while allowing chat to remain a client that references runs by id and fetches details when needed.
