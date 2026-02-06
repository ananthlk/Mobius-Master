# Mobius Data Schema and Credentials Reference

Single reference for per-module schemas and env vars. Source: [DB_INVENTORY.md](DB_INVENTORY.md), per-module `.env.example`, and schema definitions in each repo.

---

## 1. Per-module schema

### mobius-chat

| Item | Value |
|------|--------|
| **Database** | `mobius_chat` (PostgreSQL) |
| **Role** | Chat app: RAG metadata (read-only) for published docs; optional clone for dev. |
| **Tables** | `documents`, `chunks`, `chunk_embeddings`, `facts` (optional dev clone). `published_rag_metadata`, `sync_runs`. `chat_feedback`, `chat_turns`, `chat_turns_agent_cards`. |
| **Source of truth** | [mobius-chat/db/schema/](mobius-chat/db/schema/) — `001_rag_schema.sql`, `002_published_rag_metadata.sql`, `003_chat_feedback.sql`, `004_chat_turns.sql`, `005_chat_turns_agent_cards.sql`. |

---

### mobius-rag

| Item | Value |
|------|--------|
| **Database** | `mobius_rag` (PostgreSQL) |
| **Role** | RAG app: document ingestion, chunking, extraction, embeddings, publish pipeline. |
| **Tables** | `documents`, `document_pages`, `hierarchical_chunks`, `chunking_results`, `chunking_jobs`, `chunking_events`, `llm_configs`, `embedding_jobs`, `chunk_embeddings`, `publish_events`, `rag_published_embeddings`, `extracted_facts`, `processing_errors`. |
| **Source of truth** | [mobius-rag/app/migrations/](mobius-rag/app/migrations/) and startup SQL in [mobius-rag/app/main.py](mobius-rag/app/main.py). |

---

### mobius-dbt

| Item | Value |
|------|--------|
| **Database** | None (no own DB). Reads RAG Postgres and BigQuery; writes Chat Postgres, BigQuery mart, Vertex AI. |
| **Role** | ETL: RAG Postgres → BigQuery landing → mart; sync mart → Chat Postgres + Vertex AI Vector Search. |
| **Reads** | Postgres (RAG): `rag_published_embeddings`. BigQuery: landing `landing_rag.rag_published_embeddings`, mart `mobius_rag.published_rag_embeddings`. |
| **Writes** | BigQuery: landing (ingest script), mart (dbt run). Postgres (Chat): `published_rag_metadata`, `sync_runs`. Vertex AI: vector index. |
| **Source of truth** | [mobius-dbt/models/marts/chat_rag/schema.yml](mobius-dbt/models/marts/chat_rag/schema.yml), [mobius-dbt/docs/BIGQUERY_DATASETS.md](mobius-dbt/docs/BIGQUERY_DATASETS.md), [DB_INVENTORY.md](DB_INVENTORY.md). |

---

### mobius-os

| Item | Value |
|------|--------|
| **Database** | `mobius` (PostgreSQL) |
| **Role** | Backend app: sidecar, patients, tasks, resolution plans, evidence, billing, scheduling, etc. |
| **Tables** | tenant, role, app_user, application, policy_config, auth_provider_link, user_session; patient_identity_ref, patient_context, patient_snapshot; resolution_plan, plan_step, step_answer, plan_note, plan_modification, user_remedy; payment_probability, task_template, task_step, task_instance, step_instance, user_preference; user_alert, milestone, milestone_history, milestone_substep, user_owned_task; activity, user_activity; user_reported_issue; patient_ids; mock_emr; message_thread, message, message_attachment, message_recipient, message_template; patient_insurance, charge, claim, payment, patient_statement; clinical_order, lab_order, imaging_order, medication_order, referral_order; provider, provider_schedule, time_slot, schedule_exception; appointment, appointment_reminder; intake_form, insurance_verification, intake_checklist; invocation, session; event_log; detection_config; assignment; evidence (fact_source_link, plan_step_fact_link, raw_data, source_document, evidence); system_response, mini_submission. |
| **Source of truth** | [mobius-os/backend/app/models/](mobius-os/backend/app/models/) and migrations in `mobius-os/backend/migrations/versions/`. |

---

### mobius-user

| Item | Value |
|------|--------|
| **Database** | `mobius_user` (PostgreSQL) |
| **Role** | Shared user/auth: tenants, users, sessions, preferences, activities. Own database. |
| **Tables** | `tenant`, `role`, `app_user`, `auth_provider_link`, `user_session`, `activity`, `user_activity`, `user_preference`. |
| **Source of truth** | [Mobius-user/migrations/versions/001_initial_user_schema.py](Mobius-user/migrations/versions/001_initial_user_schema.py). |

---

## 2. Credentials and env vars

Grouped by concern. **Secret?** = Y if the value is sensitive (passwords, keys); N if it is a host/port/name.

### Database URLs (PostgreSQL)

| Variable | Module(s) | Purpose | Secret? |
|----------|-----------|---------|--------|
| `CHAT_RAG_DATABASE_URL` | mobius-chat | Chat DB (published_rag_metadata, sync_runs, chat tables). Must match dbt `CHAT_DATABASE_URL`. | Y (contains password) |
| `CHAT_DATABASE_URL` | mobius-dbt | Same as Chat DB; sync writes here. Must match mobius-chat `CHAT_RAG_DATABASE_URL`. | Y |
| `DATABASE_URL` | mobius-rag | RAG Postgres (mobius_rag). | Y |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | mobius-dbt | RAG Postgres read (mobius_rag). | Y (password) |
| `POSTGRES_HOST_LOCAL`, `POSTGRES_PORT_LOCAL`, `POSTGRES_DB_LOCAL`, `POSTGRES_USER_LOCAL`, `POSTGRES_PASSWORD_LOCAL` | mobius-os | Local Postgres (mobius). | Y |
| `POSTGRES_HOST_CLOUD`, etc. / `CLOUDSQL_CONNECTION_NAME` | mobius-os | Cloud Postgres. | Y |
| `DATABASE_MODE` | mobius-os | `local` or `cloud`. | N |
| `USER_DATABASE_URL` | mobius-user (consumed by mobius-os, mobius-chat) | User DB (mobius_user). | Y |

### GCP (Vertex, GCS, BigQuery)

| Variable | Module(s) | Purpose | Secret? |
|----------|-----------|---------|--------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Chat, RAG, dbt | Path to GCP service account JSON. | N (path); file content is secret |
| `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, `VERTEX_MODEL` | mobius-chat, mobius-rag | Vertex AI (LLM, embeddings). | N |
| `VERTEX_INDEX_ENDPOINT_ID`, `VERTEX_DEPLOYED_INDEX_ID` | mobius-chat | Vertex Vector Search endpoint and deployed index. | N |
| `VERTEX_PROJECT`, `VERTEX_REGION`, `VERTEX_INDEX_ID`, `VERTEX_INDEX_MODE`, `GCS_BUCKET`, `GCS_PREFIX` | mobius-dbt | Vertex index and GCS for batch index. | N |
| `BQ_PROJECT`, `BQ_DATASET` | mobius-dbt | BigQuery project and mart dataset. | N |
| `GCS_BUCKET` | mobius-rag | GCS bucket for RAG uploads. | N |

### JWT and auth

| Variable | Module(s) | Purpose | Secret? |
|----------|-----------|---------|--------|
| `JWT_SECRET` | mobius-user; consumed by mobius-os, mobius-chat | JWT signing. Must match across all apps sharing auth. | Y |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | mobius-user | Token lifetimes. | N |
| `DEFAULT_TENANT_ID`, `DEFAULT_TENANT_NAME` | mobius-user | Dev default tenant. | N |

### Queue (mobius-chat)

| Variable | Module(s) | Purpose | Secret? |
|----------|-----------|---------|--------|
| `QUEUE_TYPE` | mobius-chat | `memory` or Redis. | N |
| `REDIS_URL` | mobius-chat | Redis URL when QUEUE_TYPE uses Redis. | Y (can contain password) |

### Optional / app-specific

| Variable | Module(s) | Purpose | Secret? |
|----------|-----------|---------|--------|
| `CHAT_LLM_PROVIDER`, `CHAT_RAG_TOP_K`, `API_BASE_URL` | mobius-chat | LLM provider, RAG top-k, base URL. | N |
| `CHAT_LIVE_STREAM` | mobius-chat | Enable live streaming when worker is separate. | N |
| `ENV` | mobius-rag | dev or prod. | N |
| `LLM_PROVIDER`, `OLLAMA_*`, `OPENAI_API_KEY` | mobius-rag | LLM provider and keys. | Y (OpenAI key) |
| `ENABLE_FIRESTORE`, Firestore DB names | mobius-os | Firestore. | N |
| `FLASK_ENV`, `SECRET_KEY`, `GCP_CREDENTIALS_PATH`, `GCP_PROJECT_ID` | mobius-os | Flask and GCP. | Y (SECRET_KEY) |
| `ORIGIN_DEV_*`, `ORIGIN_PROD_*`, `DEST_DEV_*`, `DEST_PROD_*` | mobius-dbt | Job UI origin/destination env overrides. | Y if they contain passwords |

---

## 3. Where to set env

- **Per module:** Copy the module’s `.env.example` to `.env` in that module (e.g. `mobius-chat/.env`, `mobius-rag/.env`).
- **Shared:** [mobius-config](mobius-config/README.md) holds a canonical `.env.example` and scripts (`inject_env.sh`, `run_with_shared_env.sh`) to inject env into each module or run a module with shared env. Put GCP key in `mobius-config/credentials/` or the module’s `credentials/`.
- **Master landing:** No DB or external credentials; binds 127.0.0.1:3999 only (dev-only).
