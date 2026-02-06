# Mobius DB Inventory

Per-module database usage as of the parent-root migration. Used to propose what is "common" (candidate for one DB) vs what stays separate.

---

## mobius-chat

| Item | Value |
|------|--------|
| **Role** | Chat app: RAG metadata (read-only) for published docs; optional local clone for dev. |
| **Env vars** | `CHAT_RAG_DATABASE_URL` (or `RAG_DATABASE_URL`, `CHAT_DATABASE_URL`). Optional copy-from-RAG: `RAG_SOURCE_DATABASE_URL`, `RAG_DATABASE_URL`. |
| **Schema / DB name** | Typically one DB (e.g. `mobius_chat`) with tables below. |
| **Tables** | **001_rag_schema.sql:** `documents`, `chunks`, `chunk_embeddings`, `facts` (optional clone for dev). **002_published_rag_metadata.sql:** `published_rag_metadata` (from MOBIUS-DBT sync), `sync_runs`. |
| **Dependencies** | Chat expects `published_rag_metadata` (and optionally Vertex index) to be populated by **mobius-dbt** `sync_mart_to_chat.py`. Same DB URL must be used by Chat and by dbt sync. |

---

## mobius-os

| Item | Value |
|------|--------|
| **Role** | Backend app: sidecar, patients, tasks, resolution plans, evidence, billing, scheduling, etc. |
| **Env vars** | `DATABASE_MODE` (local | cloud). Local: `POSTGRES_HOST_LOCAL`, `POSTGRES_PORT_LOCAL`, `POSTGRES_DB_LOCAL` (default `mobius`), `POSTGRES_USER_LOCAL`, `POSTGRES_PASSWORD_LOCAL`. Cloud: `POSTGRES_HOST_CLOUD`, etc., or `CLOUDSQL_CONNECTION_NAME` for Unix socket. Optional: `ENABLE_FIRESTORE`, Firestore DB names. |
| **Schema / DB name** | Single DB (e.g. `mobius`) — all app tables in one schema. |
| **Tables** | Many tables via Alembic: tenant, roles, users, auth, patient_context, patient_snapshot, resolution_plan, plan_step, step_answer, evidence, payment_probability, task_template, task_instance, appointments, orders, billing, messages, milestones, user_alert, etc. (See `backend/app/models/` and `migrations/versions/`.) |
| **Dependencies** | None on other Mobius modules. Standalone app DB. |

---

## mobius-rag

| Item | Value |
|------|--------|
| **Role** | RAG app: document ingestion, chunking, extraction, embeddings, publish pipeline. |
| **Env vars** | `DATABASE_URL` (e.g. `postgresql+asyncpg://user:pass@host/mobius_rag`). `ENV` (dev | prod) selects default URL. |
| **Schema / DB name** | Single DB (e.g. `mobius_rag`) — all RAG tables. |
| **Tables** | `documents`, `document_pages`, `hierarchical_chunks`, `chunking_results`, `chunking_jobs`, `chunking_events`, `llm_configs`, `embedding_jobs`, `chunk_embeddings`, `publish_events`, `rag_published_embeddings`, `extracted_facts`, `processing_errors`. |
| **Dependencies** | None on Chat or OS. **mobius-dbt** reads `rag_published_embeddings` (Postgres) for ingest to BigQuery landing. |

---

## mobius-dbt

| Item | Value |
|------|--------|
| **Role** | ETL: RAG Postgres → BigQuery landing → mart; sync mart → Chat Postgres + Vertex AI Vector Search. |
| **Reads** | **Postgres (RAG):** `rag_published_embeddings` (env: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB` default `mobius_rag`, `POSTGRES_USER`, `POSTGRES_PASSWORD`). **BigQuery:** landing `landing_rag.rag_published_embeddings`, mart `mobius_rag.published_rag_embeddings` (env: `BQ_PROJECT`, `BQ_DATASET`). |
| **Writes** | **BigQuery:** landing (ingest script), mart (dbt run), optional `sync_runs`. **Postgres (Chat):** `published_rag_metadata`, `sync_runs` (env: `CHAT_DATABASE_URL` — must match Chat’s `CHAT_RAG_DATABASE_URL`). **Vertex AI:** vector index upsert (env: `VERTEX_PROJECT`, `VERTEX_REGION`, `VERTEX_INDEX_ID`, `VERTEX_INDEX_ENDPOINT_ID`). |
| **Dependencies** | Reads from mobius-rag Postgres; writes to same Postgres DB that mobius-chat reads (published_rag_metadata). |

---

## mobius-user

| Item | Value |
|------|--------|
| **Role** | Shared user/auth: tenants, users, sessions, preferences, activities. Own database. |
| **Env vars** | `USER_DATABASE_URL` (e.g. `postgresql://user:pass@host/mobius_user`). `JWT_SECRET` (must match across mobius-os and mobius-chat). |
| **Schema / DB name** | Single DB (`mobius_user`) — all user tables. |
| **Tables** | `tenant`, `role`, `app_user`, `auth_provider_link`, `user_session`, `activity`, `user_activity`, `user_preference`. |
| **Dependencies** | None. Consumed by mobius-os and mobius-chat for auth. Cross-references use `user_id` (UUID) only; no cross-DB FKs. |

---

## Data flow summary

```
mobius-rag (Postgres)  ----[ingest_rag_to_landing.py]---->  BigQuery landing_rag
                                                                 |
                                                                 v
mobius-dbt (dbt run)  <---- landing_rag  ----  mart: published_rag_embeddings
                                                                 |
                    [sync_mart_to_chat.py]
                                                                 |
         +----------------------------+---------------------------+
         v                            v                           v
  Chat Postgres              Vertex AI Vector Search       BQ sync_runs
  (published_rag_metadata)   (embeddings + filter metadata)

mobius-chat reads: CHAT_RAG_DATABASE_URL → published_rag_metadata + Vertex
mobius-os: own Postgres (mobius) — no shared tables with RAG/Chat.
mobius-user: own Postgres (mobius_user) — shared auth; mobius-os and mobius-chat connect for login/validate.
```

---

## Env vars quick reference

| Module     | Primary DB URL / config |
|-----------|---------------------------|
| mobius-chat | `CHAT_RAG_DATABASE_URL` |
| mobius-os   | `POSTGRES_*_LOCAL` / `POSTGRES_*_CLOUD`, `DATABASE_MODE`, optional `CLOUDSQL_CONNECTION_NAME` |
| mobius-rag  | `DATABASE_URL` |
| mobius-dbt  | RAG read: `POSTGRES_HOST`, `POSTGRES_DB` (mobius_rag), etc.; Chat write: `CHAT_DATABASE_URL`; BQ: `BQ_PROJECT`, `BQ_DATASET`; Vertex: `VERTEX_*` |
| mobius-user | `USER_DATABASE_URL` (mobius_user DB); `JWT_SECRET` (shared) |

---

## Migrations

For a single entrypoint to run all DB migrations (chat, rag, os, user) in dev or prod, see **[mobius-migrations/](../mobius-migrations/)**. Use `python mobius-migrations/run_migrations.py --env dev|prod [--module chat|rag|os|user]` with the appropriate env vars set (see [DATA_SCHEMA_AND_CREDENTIALS.md](DATA_SCHEMA_AND_CREDENTIALS.md)).
