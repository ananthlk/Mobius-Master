# Production Parity Checklist

Apply these same steps when promoting to production. They were required for staging Chat to work.

---

## Quick Fix: Worker DB Migrations (Staging)

If Chat or RAG workers fail due to missing tables (`relation "chat_threads" does not exist`, extraction returns 0 facts):

```bash
# 1. Start Cloud SQL Proxy (in a separate terminal)
cloud-sql-proxy mobius-staging-mobius:us-central1:mobius-platform-staging-db --port 5433 &
sleep 3

# 2. Run both Chat and RAG migrations
./scripts/run_all_worker_migrations_staging.sh
```

Requires: `gcloud` configured with access to `mobius-staging-mobius` and Secret Manager. Chat needs `psycopg2-binary`; RAG uses `uv run` (mobius-rag has pyproject.toml). Alternatively, run Chat migrations via Cloud Run Job: `gcloud run jobs execute mobius-chat-migrate --project=mobius-staging-mobius --region=us-central1 --wait`

---

## 1. Chat Database Migrations

**Problem:** Chat API failed with `relation "chat_threads" does not exist` because migrations were never run on the target database.

**Fix:** Run mobius-chat DB migrations against the production `mobius_chat` database **before** deploying Chat services.

### Option A: Cloud Run Job (recommended)

```bash
# Create the job once
gcloud run jobs create mobius-chat-migrate \
  --project=PROJECT_ID \
  --region=REGION \
  --image=gcr.io/PROJECT_ID/mobius-chat-api:latest \
  --set-cloudsql-instances=PROJECT_ID:REGION:INSTANCE_NAME \
  --set-env-vars="CHAT_RAG_DATABASE_URL=postgresql://USER:PASSWORD@/mobius_chat?host=%2Fcloudsql%2FPROJECT_ID%3AREGION%3AINSTANCE_NAME" \
  --command="python" \
  --args="-m,app.db.run_migrations" \
  --service-account=PLATFORM_SA \
  --task-timeout=300

# Execute before each release that may include new migrations
gcloud run jobs execute mobius-chat-migrate --project=PROJECT_ID --region=REGION --wait
```

### Option B: Local with Cloud SQL Proxy (or use script)

```bash
# Terminal 1: Start proxy
cloud-sql-proxy PROJECT_ID:REGION:INSTANCE_NAME --port 5433 &
sleep 3

# Terminal 2: Run migrations (script auto-fetches password from Secret Manager)
./scripts/run_chat_migrations_staging.sh
# Or manually:
# export DB_PASS=$(gcloud secrets versions access latest --secret=db-password-mobius-chat --project=PROJECT_ID)
# CHAT_RAG_DATABASE_URL="postgresql://mobius_app:${DB_PASS}@127.0.0.1:5433/mobius_chat" python -m app.db.run_migrations
```

**When:** Before first Chat deploy, and whenever new `db/schema/*.sql` files are added.

---

## 2. RAG Database Migrations (Workers)

**Problem:** RAG chunking and embedding workers use PostgreSQL (`mobius_rag`) for `chunking_jobs`, `chunking_results`, `documents`, `document_pages`, `hierarchical_chunks`, `extracted_facts`, `embedding_jobs`, etc. If these tables or columns are missing, workers fail (e.g. "relation does not exist" or extraction returns 0 facts).

**Fix:** Ensure `mobius_rag` has schema created and migrations applied **before** deploying RAG workers.

### Option A: RAG API startup (automatic)

The RAG backend runs `Base.metadata.create_all` and startup migrations on first request. If the RAG API is deployed and receives traffic, it will create/update the schema. **Caveat:** Workers may start before the API; ensure API is hit at least once, or use Option B.

### Option B: Run migrations explicitly (recommended for workers)

```bash
# Terminal 1: Start Cloud SQL Proxy
cloud-sql-proxy PROJECT_ID:REGION:INSTANCE_NAME --port 5433 &
sleep 3

# Terminal 2: Run RAG migrations (script auto-fetches password)
./scripts/run_rag_migrations_staging.sh
# Uses mobius-rag/run_staging_migrations.py (create_all + full migration set)
```

### Worker → Database mapping

| Worker | Database | Key tables |
|--------|----------|------------|
| Chat worker | `mobius_chat` | chat_threads, chat_turns, chat_turn_messages, chat_state |
| RAG chunking worker | `mobius_rag` | chunking_jobs, chunking_results, documents, document_pages, hierarchical_chunks, extracted_facts |
| RAG embedding worker | `mobius_rag` | embedding_jobs, chunk_embeddings |

**When:** Before first RAG worker deploy; re-run if new migrations are added.

---

## 3. Redis Connectivity (VPC Egress)

**Problem:** Cloud Run services could not reach Memorystore Redis (private IP) because they run in Google-managed network by default.

**Fix:** Deploy Chat API and Chat worker with **Direct VPC egress** so traffic to Redis (private IP) is routed through the VPC.

### Prerequisites

- Redis instance in same VPC as Cloud Run (typically `default` network)
- Subnet `/26` or larger in the Redis region (e.g. `default` in us-central1)
- Cloud Run Service Agent has `roles/compute.networkUser` on the project

### Deploy with VPC egress

Add to **every** `gcloud run deploy` for services that use Redis (Chat API, Chat worker, Scraper):

```
--network=default \
--subnet=default \
--vpc-egress=private-ranges-only
```

Example for Chat API:

```bash
gcloud run deploy mobius-chat-api \
  ... \
  --network=default \
  --subnet=default \
  --vpc-egress=private-ranges-only \
  --set-env-vars="...,REDIS_URL=redis://REDIS_IP:6379/0"
```

**When:** Required for any Cloud Run service that connects to Memorystore Redis.

### Alternative: VPC Connector

If Direct VPC egress does not work (e.g. connectivity timeouts), use a Serverless VPC Access connector:

```bash
# Create connector (needs unused /28 subnet)
gcloud compute networks vpc-access connectors create mobius-redis-connector \
  --region=REGION \
  --network=default \
  --range=10.8.0.0/28

# Deploy with connector
gcloud run deploy mobius-chat-api \
  ... \
  --vpc-connector=mobius-redis-connector \
  --vpc-egress=private-ranges-only
```

---

## 4. Summary of Staging Changes (2026-02-04)

| Step | What | Why |
|------|------|-----|
| Chat migrations | Ran `mobius-chat/db/schema/*.sql` via Cloud Run Job or `scripts/run_chat_migrations_staging.sh` | `chat_threads` and related tables did not exist |
| RAG migrations | Run `scripts/run_rag_migrations_staging.sh` (uses `mobius-rag/run_staging_migrations.py`) | Chunking/embedding workers need `chunking_jobs`, `extracted_facts`, etc. |
| **All worker migrations** | `scripts/run_all_worker_migrations_staging.sh` | Single script: Chat + RAG migrations; requires proxy + Secret Manager access |
| Direct VPC egress | Added `--network=default --subnet=default --vpc-egress=private-ranges-only` to Chat API and Chat worker | Cloud Run could not reach Redis at 10.121.0.3 |
| Migration job | Created `mobius-chat-migrate` Cloud Run Job | Repeatable way to run Chat migrations without local proxy |

---

## 5. Pre-Production Checklist

Before deploying to production:

- [ ] Run Chat migrations against production `mobius_chat` (Section 1, Option A or B)
- [ ] Run RAG init_db + migrations against production `mobius_rag` (Section 2) if workers are used
- [ ] Ensure Redis is in same VPC as Cloud Run (or use connector)
- [ ] Deploy Chat API with `--network` and `--subnet` for VPC egress
- [ ] Deploy Chat worker with `--network` and `--subnet` for VPC egress
- [ ] Deploy RAG workers with correct `DATABASE_URL` pointing to migrated `mobius_rag`
- [ ] Deploy Scraper with VPC egress if it uses Redis
- [ ] Verify POST /chat returns 200 and worker processes (poll /chat/response/{id})

---

## Related Docs

- [staging_cloud_run_deployments.md](staging_cloud_run_deployments.md)
- [staging_deployment_status.md](staging_deployment_status.md)
- [credentials_reference.md](credentials_reference.md)
