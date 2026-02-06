# Production Migration Checklist

**Date:** 2026-02-04  
**Target Project:** `mobiusos-new`  
**Region:** `us-central1`

---

## Executive Summary: Staging → Production Gap

| Item | Staging | Production | Action Required |
|------|---------|------------|-----------------|
| **Services** | 10 services | 2 services | Deploy 8 new services |
| **Redis** | ✅ Memorystore | ❌ Not enabled | Enable API + create instance |
| **VPC Connector** | ✅ `mobius-redis-connector` | ❌ Not enabled | Enable API + create connector |
| **Vertex AI** | ✅ Enabled | ❓ Check | Enable if missing |
| **Cloud SQL** | Private IP | Public IP | Consider private for security |

---

## Phase 1: Infrastructure Prerequisites

### 1.1 Enable Required APIs

```bash
export PROD_PROJECT=mobiusos-new

gcloud services enable redis.googleapis.com --project=$PROD_PROJECT
gcloud services enable vpcaccess.googleapis.com --project=$PROD_PROJECT
gcloud services enable aiplatform.googleapis.com --project=$PROD_PROJECT
gcloud services enable secretmanager.googleapis.com --project=$PROD_PROJECT
```

### 1.2 Create Redis (Memorystore)

```bash
gcloud redis instances create mobius-redis \
  --project=$PROD_PROJECT \
  --region=us-central1 \
  --tier=basic \
  --size=1 \
  --redis-version=redis_7_0 \
  --connect-mode=private-service-access

# Get the private IP after creation
gcloud redis instances describe mobius-redis \
  --project=$PROD_PROJECT \
  --region=us-central1 \
  --format="value(host)"
```

### 1.3 Create VPC Connector

```bash
gcloud compute networks vpc-access connectors create mobius-redis-connector \
  --project=$PROD_PROJECT \
  --region=us-central1 \
  --network=default \
  --range=10.8.0.0/28 \
  --min-instances=2 \
  --max-instances=10
```

### 1.4 Create Secrets (if not exist)

```bash
# List existing secrets
gcloud secrets list --project=$PROD_PROJECT

# Create any missing secrets
# gcloud secrets create jwt-secret --project=$PROD_PROJECT
# echo -n "your-secret-value" | gcloud secrets versions add jwt-secret --data-file=- --project=$PROD_PROJECT
```

---

## Phase 2: Database Migrations

### 2.1 Chat Database

```bash
# Connect to production Cloud SQL
gcloud sql connect mobius-platform-db --user=postgres --project=$PROD_PROJECT

# Run migrations:
# - 013_chat_progress_events.sql (for live streaming)
# - Ensure mobius_chat database exists
# - Ensure published_rag_metadata table exists
```

### 2.2 RAG Metadata Sync

The `published_rag_metadata` table must be populated for RAG to work:

```bash
# Option 1: Run dbt sync from mobius-dbt
cd mobius-dbt
python scripts/sync_mart_to_chat.py --dest prod

# Option 2: Copy from staging if Vertex index is shared
# Export from staging, import to production
```

---

## Phase 3: Deploy Services

### Critical Configuration Lessons from Staging:

| Config | Why | Applies To |
|--------|-----|------------|
| `--no-cpu-throttling` | Workers run background threads; without this, CPU is only allocated during HTTP requests | All workers |
| `--min-instances=1` | Workers must always be running to poll Redis | All workers |
| `--vpc-connector` | Required to reach Redis private IP | All services using Redis |
| `--vpc-egress=private-ranges-only` | Route only private IPs through VPC | All services with VPC connector |

### 3.1 Mobius Chat API

```bash
export REDIS_URL="redis://<REDIS_IP>:6379/0"
export CLOUDSQL_CONNECTION=mobiusos-new:us-central1:mobius-platform-db
export PLATFORM_SA=<service-account>@mobiusos-new.iam.gserviceaccount.com

gcloud run deploy mobius-chat-api \
  --project=$PROD_PROJECT \
  --region=us-central1 \
  --image=gcr.io/$PROD_PROJECT/mobius-chat-api:latest \
  --service-account=$PLATFORM_SA \
  --add-cloudsql-instances=$CLOUDSQL_CONNECTION \
  --set-env-vars="QUEUE_TYPE=redis,REDIS_URL=$REDIS_URL,CHAT_RAG_DATABASE_URL=postgresql://..." \
  --set-secrets="JWT_SECRET=jwt-secret:latest" \
  --vpc-connector=mobius-redis-connector \
  --vpc-egress=private-ranges-only \
  --min-instances=1 \
  --allow-unauthenticated
```

### 3.2 Mobius Chat Worker ⚠️ CRITICAL CONFIG

```bash
gcloud run deploy mobius-chat-worker \
  --project=$PROD_PROJECT \
  --region=us-central1 \
  --image=gcr.io/$PROD_PROJECT/mobius-chat-api:latest \
  --service-account=$PLATFORM_SA \
  --add-cloudsql-instances=$CLOUDSQL_CONNECTION \
  --set-env-vars="QUEUE_TYPE=redis,REDIS_URL=$REDIS_URL,CHAT_RAG_DATABASE_URL=...,VERTEX_PROJECT_ID=$PROD_PROJECT,VERTEX_LOCATION=us-central1,VERTEX_MODEL=gemini-2.5-flash,LLM_PROVIDER=vertex,VERTEX_INDEX_ENDPOINT_ID=<prod-endpoint-id>,VERTEX_DEPLOYED_INDEX_ID=<prod-deployed-index-id>" \
  --set-secrets="JWT_SECRET=jwt-secret:latest" \
  --vpc-connector=mobius-redis-connector \
  --vpc-egress=private-ranges-only \
  --min-instances=1 \
  --max-instances=1 \
  --no-cpu-throttling \
  --timeout=3600 \
  --command="python" \
  --args="-m,uvicorn,app.worker_server:app,--host,0.0.0.0,--port,8080"
```

### 3.3 Mobius Skills Scraper API

```bash
gcloud run deploy mobius-skills-scraper \
  --project=$PROD_PROJECT \
  --region=us-central1 \
  --image=gcr.io/$PROD_PROJECT/mobius-skills-scraper:latest \
  --service-account=$PLATFORM_SA \
  --set-env-vars="REDIS_URL=$REDIS_URL,GCS_BUCKET=mobius-rag-uploads" \
  --vpc-connector=mobius-redis-connector \
  --vpc-egress=private-ranges-only \
  --min-instances=1 \
  --no-cpu-throttling \
  --allow-unauthenticated
```

### 3.4 Mobius Skills Scraper Worker ⚠️ CRITICAL CONFIG

```bash
gcloud run deploy mobius-skills-scraper-worker \
  --project=$PROD_PROJECT \
  --region=us-central1 \
  --image=gcr.io/$PROD_PROJECT/mobius-skills-scraper:latest \
  --service-account=$PLATFORM_SA \
  --set-env-vars="REDIS_URL=$REDIS_URL,GCS_BUCKET=mobius-rag-uploads" \
  --vpc-connector=mobius-redis-connector \
  --vpc-egress=private-ranges-only \
  --min-instances=1 \
  --max-instances=1 \
  --no-cpu-throttling \
  --timeout=3600 \
  --command="uvicorn" \
  --args="app.worker_server:app,--host,0.0.0.0,--port,8080"
```

### 3.5 RAG Chunking Worker ⚠️ CRITICAL CONFIG

```bash
gcloud run deploy mobius-rag-chunking-worker \
  --project=$PROD_PROJECT \
  --region=us-central1 \
  --image=gcr.io/$PROD_PROJECT/mobius-rag-worker:latest \
  --service-account=$PLATFORM_SA \
  --add-cloudsql-instances=$CLOUDSQL_CONNECTION \
  --set-env-vars="WORKER_TYPE=chunking,REDIS_URL=$REDIS_URL,..." \
  --vpc-connector=mobius-redis-connector \
  --vpc-egress=private-ranges-only \
  --min-instances=1 \
  --max-instances=1 \
  --no-cpu-throttling \
  --timeout=3600
```

### 3.6 RAG Embedding Worker ⚠️ CRITICAL CONFIG

```bash
gcloud run deploy mobius-rag-embedding-worker \
  --project=$PROD_PROJECT \
  --region=us-central1 \
  --image=gcr.io/$PROD_PROJECT/mobius-rag-worker:latest \
  --service-account=$PLATFORM_SA \
  --add-cloudsql-instances=$CLOUDSQL_CONNECTION \
  --set-env-vars="WORKER_TYPE=embedding,REDIS_URL=$REDIS_URL,..." \
  --vpc-connector=mobius-redis-connector \
  --vpc-egress=private-ranges-only \
  --min-instances=1 \
  --max-instances=1 \
  --no-cpu-throttling \
  --timeout=3600
```

### 3.7 DBT Job UI

```bash
gcloud run deploy mobius-dbt-ui \
  --project=$PROD_PROJECT \
  --region=us-central1 \
  --image=gcr.io/$PROD_PROJECT/mobius-dbt-ui:latest \
  --service-account=$PLATFORM_SA \
  --set-env-vars="BQ_PROJECT=$PROD_PROJECT,..." \
  --set-secrets="POSTGRES_PASSWORD=db-password-mobius-rag:latest" \
  --allow-unauthenticated=false
```

### 3.8 Module Hub

```bash
gcloud run deploy module-hub \
  --project=$PROD_PROJECT \
  --region=us-central1 \
  --image=gcr.io/$PROD_PROJECT/module-hub:latest \
  --service-account=$PLATFORM_SA \
  --set-env-vars="ENV=prod,MOBIUS_OS_URL=...,MOBIUS_CHAT_URL=...,..." \
  --allow-unauthenticated
```

---

## Phase 4: Verification Checklist

### 4.1 Infrastructure

- [ ] Redis instance is RUNNING: `gcloud redis instances describe mobius-redis --project=$PROD_PROJECT --region=us-central1`
- [ ] VPC connector is READY: `gcloud compute networks vpc-access connectors describe mobius-redis-connector --project=$PROD_PROJECT --region=us-central1`
- [ ] All secrets created

### 4.2 Services Health

```bash
# Check all services running
gcloud run services list --project=$PROD_PROJECT --region=us-central1

# Health checks
curl https://mobius-chat-api-xxx.run.app/health
curl https://mobius-skills-scraper-xxx.run.app/health
curl https://mobius-rag-xxx.run.app/health
```

### 4.3 Worker Verification

Check logs for each worker - they should show:

```
# Chat Worker
[WORKER] run_worker starting queue_type=redis
[WORKER] Redis connected for queue
[WORKER] Worker listening for chat requests

# Scraper Worker
[SCRAPER WORKER] Starting scraper worker, consuming from mobius:scraper:requests
[SCRAPER WORKER] Scraper worker started in background thread

# RAG Workers
Starting chunking worker...
Starting embedding worker...
```

### 4.4 End-to-End Tests

- [ ] Chat: Submit a question, verify worker picks it up, response appears
- [ ] RAG: Upload document, verify chunking → embedding → searchable
- [ ] Scraper: Submit URL, verify worker processes it

---

## Common Issues & Fixes

### Issue: "Waiting for worker..." in Chat UI

**Cause:** API and worker not sharing Redis, or VPC connector missing  
**Fix:**
1. Verify both have `QUEUE_TYPE=redis` and same `REDIS_URL`
2. Verify both have `--vpc-connector`
3. Check worker logs for "Worker listening"

### Issue: Worker starts then shuts down

**Cause:** Missing `--no-cpu-throttling`  
**Fix:** Redeploy with `--no-cpu-throttling`

### Issue: RAG returns 0 results

**Cause:** `published_rag_metadata` table empty or missing  
**Fix:** Run dbt sync or copy data from staging

### Issue: Service can't reach Redis

**Cause:** Missing VPC connector  
**Fix:** Deploy with `--vpc-connector=mobius-redis-connector --vpc-egress=private-ranges-only`

---

## Services to Deploy (Priority Order)

1. **Infrastructure** - Redis, VPC connector, secrets
2. **mobius-chat-api** + **mobius-chat-worker** - Core chat functionality
3. **mobius-rag** (already deployed) - Verify configuration
4. **mobius-rag-chunking-worker** + **mobius-rag-embedding-worker**
5. **mobius-skills-scraper** + **mobius-skills-scraper-worker**
6. **mobius-dbt-ui** - Pipeline management
7. **module-hub** - Dashboard

---

## Rollback Plan

If issues occur after deployment:

```bash
# Rollback to previous revision
gcloud run services update-traffic <service-name> \
  --project=$PROD_PROJECT \
  --region=us-central1 \
  --to-revisions=<previous-revision>=100
```

---

## Notes from Staging Debugging

1. **CPU Throttling was the #1 issue** - Workers appeared to start but never processed jobs because background threads were CPU-starved

2. **VPC Connector was #2 issue** - Scraper API couldn't push to Redis without it

3. **Worker Server Pattern** - Workers need HTTP health endpoint for Cloud Run; we created `worker_server.py` that runs Uvicorn + spawns worker thread

4. **RAG Data Sync** - Vertex AI Vector Search had vectors but Postgres `published_rag_metadata` was empty → RAG found matches but couldn't return content
