# Credentialing Report Persistence — Implementation Summary

**Branch:** `credentialing-report-persistence`  
**Plan:** [CREDENTIALING_REPORT_RUN_PERSISTENCE_PLAN.md](CREDENTIALING_REPORT_RUN_PERSISTENCE_PLAN.md)

---

## What Was Implemented

### 1. Schema and persistence layer (provider-roster-credentialing)

- **`migrations/001_credentialing_report_runs.sql`**  
  Creates:
  - `credentialing_report_runs` (report_run_id, org_name, org_slug, status, error_message, triggered_by, created_at, completed_at)
  - `credentialing_report_step_outputs` (report_run_id, step_id, label, content_type, content, content_url, row_count, sort_order, cache_hit)
  - `credentialing_report_summaries` (report_run_id, guaranteed, at_risk, missing, provider counts, readiness_score, summary_json)
  - `credentialing_report_documents` (report_run_id, document_type, content, content_bytes)

- **`app/report_run_persistence.py`**  
  - Feature flag: `CREDENTIALING_REPORT_PERSISTENCE_ENABLED` (env: 1/true/yes).
  - DB URL: `CREDENTIALING_REPORT_DB_URL` or `CHAT_RAG_DATABASE_URL`.
  - Optional dependency: `psycopg2` (graceful no-op if missing or URL unset).
  - APIs: `create_run`, `append_step`, `append_steps_batch`, `complete_run`, `get_run`, `list_runs`, `compare_runs`.
  - Step content >50KB: `content` left NULL, `content_url` reserved for Phase 5 (object storage).

### 2. Report-runs HTTP API (provider-roster-credentialing)

- **POST /report-runs** — Create run; body: `{ "org_name", "triggered_by"? }`; returns `{ report_run_id, org_slug, status }`.
- **PUT /report-runs/{report_run_id}/steps** — Upsert steps; body: list of `{ step_id, label, csv_content?, content?, row_count, sort_order, content_type?, cache_hit? }`.
- **PUT /report-runs/{report_run_id}/complete** — Set status, summary, optional step_outputs, final_md, final_pdf_base64.
- **GET /report-runs/{report_run_id}** — Full run with step_outputs, summary, documents.
- **GET /report-runs** — List with query params: `org_slug`, `from_ts`, `to_ts`, `limit`.
- **GET /report-runs/compare?run_a=&run_b=** — Side-by-side run_a and run_b.

All report-runs endpoints return 503 when persistence is disabled (flag or no DB).

### 3. Integration

- **Report-from-steps (single-call)**  
  - `ReportFromStepsRequest` has optional `report_run_id`.
  - On success, if `report_run_id` is set: `append_steps_batch` of current `step_outputs`, then `complete_run` with summary from context and `final_md` / `pdf_base64` from result; response includes `report_run_id`.

- **Compose response**  
  - `/report-from-steps/compose` now returns `summary` (guaranteed, at_risk, missing, provider_count_a/b/c, location_count, readiness_score, etc.) for use by the orchestrator.

- **Orchestrator (mobius-chat)**  
  - At start of Step 11 (build report): **POST /report-runs** with `org_name`; store `state.report_run_id`.
  - After compose: store `state.report_summary` from compose response.
  - After charts-pdf success: **PUT /report-runs/{report_run_id}/complete** with `step_outputs` (from state), `summary`, `final_md`, `final_pdf_base64`.
  - `OrchestratorState`: added `report_run_id`, `report_summary`.
  - Tool agent puts `report_run_id` in `extra_out`; resolve sets `ctx.report_run_id`; integrate adds `report_run_id` to payload.

- **Pipeline context**  
  - `PipelineContext` has `report_run_id: str | None = None`.

### 4. Tests

- **provider-roster-credentialing**
  - `tests/test_report_run_persistence.py`: persistence disabled (create_run returns None, list_runs empty), and `_org_slug` helper.
  - All 25 passed, 3 skipped (existing); new persistence tests: 2 passed.

- **mobius-chat**
  - 246 passed, **2 failed** (pre-existing):  
    `test_tool_isolation_v11.py::TestAnswerToolEntityIsolation::test_npi_lookup_uses_question_entity_not_active_payer`  
    `test_tool_isolation_v11.py::TestAnswerToolEntityIsolation::test_npi_lookup_aspire_not_united`  
  - Failures are about `search_org_names` mock / tool name, not report persistence.

---

## How to Run With Persistence

1. **Apply migration** (once per DB):
   ```bash
   psql "$CREDENTIALING_REPORT_DB_URL" -f mobius-skills/provider-roster-credentialing/migrations/001_credentialing_report_runs.sql
   ```

2. **Install psycopg2** (if not present):
   ```bash
   pip install psycopg2-binary
   ```

3. **Enable and point at DB**:
   ```bash
   export CREDENTIALING_REPORT_PERSISTENCE_ENABLED=true
   export CREDENTIALING_REPORT_DB_URL="postgresql://user:pass@host:5432/dbname"
   ```

4. Start provider-roster-credentialing API and trigger a report (chat or CLI).  
   - With persistence enabled and DB reachable: run is created at start of Step 11, steps and summary/documents written on completion.  
   - Response payload includes `report_run_id`; you can **GET /report-runs/{id}** to fetch the run.

---

## Not Done in This Branch (per plan)

- **OrgStore reconciliation:** Steps that read from OrgStore do not yet write a step output row with `cache_hit=true` and the cached value (to be added in Phase 1 follow-up).
- **Object storage (Phase 5):** Step content >50KB still leaves `content` NULL and `content_url` unused; PDFs stored in `content_bytes`; no S3/GCS yet.
- **`cancelled` / `stale` status:** Schema allows them; API does not set them (optional later).

---

## Files Touched

| Repo / path | Change |
|-------------|--------|
| **mobius-skills/provider-roster-credentialing** | |
| `migrations/001_credentialing_report_runs.sql` | New |
| `app/report_run_persistence.py` | New |
| `app/main.py` | ReportRun models, report-runs routes, report-from-steps persistence, compose returns summary |
| `tests/test_report_run_persistence.py` | New |
| **mobius-chat** | |
| `app/services/roster_credentialing_orchestrator.py` | report_run_id, report_summary; POST /report-runs at start Step 11; PUT .../complete at end |
| `app/services/tool_agent.py` | extra_out["report_run_id"] |
| `app/stages/integrate.py` | payload["report_run_id"] |
| `app/stages/resolve.py` | ctx.report_run_id from extra_out |
| `app/pipeline/context.py` | report_run_id field |
| **docs** | |
| `docs/CREDENTIALING_REPORT_PERSISTENCE_IMPLEMENTATION_SUMMARY.md` | This file |
