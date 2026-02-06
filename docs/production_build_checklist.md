# Production Build Checklist

Purpose: single source of truth to prep a production build across the Mobius platform. Each row contains a `[ ]` checkbox slot, owner (role-level), the concrete action, and links to the authoritative files/scripts so the build team can execute quickly.

> ✅ **How to use this document**
>
> 1. Work top-to-bottom; do not kick off the GCP build until sections 1–5 are fully checked.
> 2. Record evidence (command output, PR URLs, screenshots) in the `Notes` column as you go.
> 3. When all boxes are checked, hand this doc to the release commander for final approval, then trigger the build/deploy jobs.

---

## 1. Repository Readiness & Freeze

| Check | Owner | Action / Verification | Notes |
| --- | --- | --- | --- |
| [ ] | Mobius OS backend lead | `cd mobius-os && git fetch origin && git status --short` → confirm `main` is clean, all fixes merged. If not, chase PR owners before freeze. | Backend deploy via `deploy.sh`; see `mobius-os/README.md`. |
| [ ] | Mobius OS extension lead | `cd mobius-os/extension && npm run build && npm run lint`. Publish updated bundle or confirm no change. | Uses `mobius-design/tokens.css`; ensure branding assets unchanged. |
| [ ] | Mobius RAG lead | `cd mobius-rag && git fetch origin && git status`. Ensure backend (`app/`), workers, and frontend have no pending commits. | Deployment scripts: `deploy/deploy_cloudrun.sh`, `deploy/vm_setup.sh`. |
| [ ] | Mobius Chat lead | `cd mobius-chat && git fetch origin && git status`. Verify API + worker + frontend consistent. | Queue scripts `mchatc` / `mchatcw`; frontend entry `frontend/src/app.ts`. |
| [ ] | Mobius DBT lead | `cd mobius-dbt && git fetch origin && git status`. Confirm `models/` + `scripts/` match latest contracts. | Reference `docs/CONTRACT_REVIEW_AND_SIGNOFF.md`. |
| [ ] | Mobius Auth package lead | `cd mobius-auth && git fetch origin && git status`. Ensure package version bumped if changes shipped. | Consumers pin to local `file:` path; update release notes if API changed. |
| [ ] | Mobius Skills (scraper) lead | `cd mobius-skills/web-scraper && git fetch origin && git status`. Confirm API + worker parity. | Check `requirements.txt`, `mscrapew`, `POST /scrape` endpoints. |
| [ ] | Mobius QA lead | `cd mobius-qa && git fetch origin && git status`. Ensure question set + adjudicator config committed. | Files: `mobius-chat-qa/chat_bot_config.yaml`, `chat_bot_questions.yaml`. |
| [ ] | Mobius User service lead | `cd mobius-user && git fetch origin && git status`. Confirm migrations + shared auth models finalized. | Library consumed by Chat + OS; verify version tag. |
| [ ] | Release commander | Run `ls /Users/ananth/Mobius/.mobius_logs` to ensure no dev servers running via `mstop`. | Logs: `mobius-chat-api.log`, etc. Stop stray processes before build. |

---

## 2. Production Configuration & Secrets

Source of truth: `mobius-config/.env.example` plus module-specific `.env.example` files.

| Check | Owner | Action / Verification | Notes |
| --- | --- | --- | --- |
| [ ] | Config steward | `cd mobius-config && diff -u .env.example .env` → ensure `.env` present with prod values (Vertex, Cloud SQL, Redis, GCS). | Scripts: `inject_env.sh`, `run_with_shared_env.sh`. |
| [ ] | Chat + RAG ops | Sync `GOOGLE_APPLICATION_CREDENTIALS`, `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, `VERTEX_MODEL`, `VERTEX_INDEX_ENDPOINT_ID`, `VERTEX_DEPLOYED_INDEX_ID`, `CHAT_RAG_DATABASE_URL`. | References: `mobius-chat/docs/ENV.md`, `docs/PUBLISHED_RAG_SETUP.md`. |
| [ ] | OS backend ops | Verify `mobius-os/backend/.env` has `DATABASE_MODE=cloud`, `CLOUDSQL_CONNECTION_NAME`, `POSTGRES_*_CLOUD`, `SECRET_KEY`. | See `mobius-os/backend/PRODUCTION_CONFIG.md`. |
| [ ] | RAG ops | Confirm `mobius-rag/.env` uses prod `DATABASE_URL`, `GCS_BUCKET`, `VERTEX_*`, `LLM_PROVIDER`, `GOOGLE_APPLICATION_CREDENTIALS`. | Reference `mobius-rag/.env.example`. |
| [ ] | DBT ops | Check `mobius-dbt/.env` for `POSTGRES_HOST`, `POSTGRES_PASSWORD` (RAG source), `BQ_PROJECT`, `BQ_DATASET`, `CHAT_DATABASE_URL`, `VERTEX_*`. | Needed by `scripts/land_and_dbt_run.sh`. |
| [ ] | Auth ops | Ensure `mobius-user/.env` (or Secret Manager) has `USER_DATABASE_URL`, `JWT_SECRET`, token lifetimes. | `mobius-user/README.md`. |
| [ ] | Scraper ops | Validate `mobius-skills/web-scraper/.env` for `REDIS_URL`, `GCS_BUCKET`, `SCRAPER_API_BASE`. | API on :8002, worker via `./mscrapew`. |
| [ ] | Secret Manager admin | Confirm prod secrets mirrored in GCP Secret Manager and CI/CD service accounts have access. | Map .env keys → Secret Manager entries. |

---

## 3. Database Migration Plan

| Check | Owner | Action / Verification | Notes |
| --- | --- | --- | --- |
| [ ] | OS backend DB owner | `cd mobius-os/backend && alembic upgrade head` against prod clone. Ensure latest revisions under `backend/migrations/versions/*.py` deployed. | Key revisions dated 20260119–20260123 (plan context, agent columns, etc.). |
| [ ] | RAG DB owner | Inventory scripts under `mobius-rag/app/migrations/`. Run pending SQL/Python migration scripts in order (e.g., `add_publish_tables.py`, `add_extracted_facts_verification.py`). | Use `python -m app.migrations.<name>` or Alembic equivalent. |
| [ ] | User DB owner | `cd mobius-user && USER_DATABASE_URL=... alembic upgrade head`. | Files: `mobius-user/migrations/env.py`, `versions/001_initial_user_schema.py`. |
| [ ] | Chat DB owner | Apply `mobius-chat/db/schema/*.sql` (e.g., `002_published_rag_metadata.sql`) and ensure `dbt` sync will not drop prod data. | Reference `mobius-chat/docs/PUBLISHED_RAG_SETUP.md`. |
| [ ] | DBT pipeline owner | Validate BigQuery landing + mart schema via `dbt test`. Confirm `scripts/land_and_dbt_run.sh` migrations for Vertex + Postgres indexes accounted for. | See `mobius-dbt/docs/LANDING_SCHEMA_AND_INGESTION.md`. |
| [ ] | Rollback prep | Capture `pg_dump` for each prod DB (`mobius`, `mobius_rag`, `mobius_chat`, `mobius_user`) prior to applying migrations. | Store dumps in secure bucket. |

---

## 4. Deployment Verification Script (post-deploy smoke)

Suggested consolidated shell script (`verify_production.sh`). Run after staging deploy and again in prod.

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT=/Users/ananth/Mobius

# 1. Mobius OS API + extension
cd "$ROOT/mobius-os/backend" && pytest && curl -sf https://prod-os/api/v1/health
cd "$ROOT/mobius-os/extension" && npm run lint && npm run test

# 2. Mobius RAG backend + workers
cd "$ROOT/mobius-rag" && uv run pytest && curl -sf https://prod-rag/health

# 3. Mobius Chat API + worker
cd "$ROOT/mobius-chat" && pytest && python -m app.worker --check

# 4. RAG → Chat pipeline
cd "$ROOT/mobius-dbt" && ./scripts/land_and_dbt_run.sh --dry-run && dbt test

# 5. Auth library + user DB
cd "$ROOT/mobius-user" && pytest

# 6. Web scraper smoke
cd "$ROOT/mobius-skills/web-scraper" && pytest && curl -sf https://prod-scraper/scrape/health

# 7. Chat QA regression
cd "$ROOT/mobius-qa/mobius-chat-qa" && python chat_bot.py --limit 10 --report reports/smoke.md
```

> Replace URLs (`https://prod-*`) with actual load-balanced endpoints. Record pass/fail plus report links in release notes.

---

## 5. Build Requirements & Artifacts

| Module | Runtime / Tooling | Build / Test Commands | Artifacts / Deploy Target |
| --- | --- | --- | --- |
| `mobius-os/backend` | Python 3.13+, PostgreSQL 15+, gcloud CLI | `pip install -r requirements.txt`, `pytest`, `alembic upgrade head` | Cloud Run container via `deploy.sh` (uses `cloudbuild.yaml` + `backend/Dockerfile`) |
| `mobius-os/extension` | Node.js 18+, npm | `npm install`, `npm run build`, optional `npm run dev` for watch | Chrome extension bundle (`extension/dist/`) |
| `mobius-rag` | Python (uv/poetry), Node 18 for frontend | `uv pip install -r requirements.txt`, `uv run pytest`, `frontend/npm run build`, workers via `mrage`, `mragw` | Cloud Run / VM deploy scripts in `deploy/`, systemd units for workers |
| `mobius-chat` | Python 3.11+, Redis (optional), Node 18 for frontend | `pip install -r requirements.txt`, `pytest`, `frontend/npm run build`, `mchatc`/`mchatcw` for API/worker | FastAPI app on :8000, worker service, static frontend in `frontend/static/app.js` |
| `mobius-dbt` | Python 3.9+, dbt-bigquery, gcloud | `./scripts/install_dbt.sh`, `dbt build`, `python scripts/land_and_dbt_run.sh`, `python scripts/sync_mart_to_chat.py` | BigQuery datasets, Vertex index updates, job UI at port 6500 |
| `mobius-auth` | TypeScript, npm | `npm install`, `npm run build` (if applicable) | Package consumed via `file:../mobius-auth`, ensure version bump in `package.json` |
| `mobius-skills/web-scraper` | Python 3.11+, Redis, GCS | `pip install -r requirements.txt`, `pytest`, `uvicorn app.main:app`, `./mscrapew` | FastAPI service on :8002, worker deployment |
| `mobius-user` | Python 3.11+, Postgres | `pip install -e .[flask,fastapi,migrations]`, `pytest`, `alembic upgrade head` | Library + migration scripts; packaged wheel if needed |
| `mobius-qa/mobius-chat-qa` | Python 3.11+, same env vars as chat | `pip install -r requirements.txt`, `python chat_bot.py --limit N` | QA report markdown in `reports/` used for release sign-off |

---

## 6. GCP Build & Deployment Readiness

| Check | Owner | Action / Verification | Notes |
| --- | --- | --- | --- |
| [ ] | Infra lead | Confirm shared project (e.g., `mobiusos-new`) healthy: billing enabled, APIs (`sqladmin`, `storage`, `aiplatform`, `compute`, `run`) enabled. | Reference `mobius-rag/docs/GCP_DEPLOYMENT.md`. |
| [ ] | Infra lead | Cloud SQL instance (`mobius-platform-db`) sized, `pgvector` enabled, databases (`mobius`, `mobius_rag`, `mobius_chat`, `mobius_user`) provisioned. | Reset `postgres` password if unknown, record securely. |
| [ ] | Infra lead | Vertex AI resources ready: LLM model (`gemini-1.5-pro`), Vector Search index + endpoint IDs recorded. | Required by Chat + DBT sync. |
| [ ] | Storage lead | GCS buckets (e.g., `mobius-uploads-<project>`, `shared-assets`) exist with lifecycle policies. | RAG ingest + scraper rely on bucket paths. |
| [ ] | IAM lead | Shared service account `mobius-platform-sa` has `roles/cloudsql.client`, `roles/storage.objectAdmin`, `roles/aiplatform.user`. Keys stored in Secret Manager only. | If using Cloud Run, mount via Secret Manager references. |
| [ ] | Build engineer | Cloud Build triggers configured for `mobius-os` (backend) and `mobius-rag` (if using Cloud Run). Validate substitutions for `DATABASE_PASSWORD` before running `deploy/deploy_cloudrun.sh`. | OS uses root `cloudbuild.yaml`. |
| [ ] | Worker ops | Systemd units or Cloud Run Jobs for RAG chunking + embedding workers tested (`deploy/systemd/*.service`). | Ensure units reference latest commit hash or container tag. |
| [ ] | Networking | Firewall rules / load balancer entries updated for any new services. Validate health checks hitting `/health` endpoints. | Document URLs in release notes. |
| [ ] | Release commander | Schedule deployment window, communicate freeze, ensure rollback playbook (DB dumps + previous container tags) ready. | Reference Section 3 rollback prep. |

---

## 7. Sign-off & Build Trigger

1. **Section reviews:** Each owner signs off (digital initials) once their rows are checked.
2. **QA evidence:** Attach latest `mobius-qa` report and manual test notes.
3. **Change log:** Summarize commits included per repo (link to Git provider).
4. **Go / No-Go meeting:** Release commander reviews this checklist + monitoring plan before running production build scripts (`deploy.sh`, `deploy_cloudrun.sh`, `./scripts/land_and_dbt_run.sh`, etc.).
5. **Post-build monitoring:** Keep Master landing (`http://localhost:3999` or prod equivalent) open plus GCP logs for at least 30 minutes. Document incidents in `docs/TROUBLESHOOTING.md`.

When every checkbox is ✅ and build completes, archive this document (copy to release folder with date) for compliance traceability.
