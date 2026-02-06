# Production Deployment Status

Project: **mobiusos-new** | Region: **us-central1**

---

## Deployed Services

| Module | Component | Status | URL | Min Instances |
|--------|-----------|--------|-----|---------------|
| **Module Hub** | Landing dashboard | ✅ Deployed | https://module-hub-374396621405.us-central1.run.app | 0 |
| **Mobius OS** | Backend (Flask API) | ✅ Deployed | https://mobius-os-backend-374396621405.us-central1.run.app | 0 |
| **Mobius RAG** | Backend + frontend (FastAPI + Vite) | ✅ Deployed | https://mobius-rag-374396621405.us-central1.run.app | 0 |
| **Mobius RAG** | Chunking worker | ✅ Deployed | https://mobius-rag-chunking-worker-374396621405.us-central1.run.app | 0 |
| **Mobius RAG** | Embedding worker | ✅ Deployed | https://mobius-rag-embedding-worker-374396621405.us-central1.run.app | 0 |
| **Mobius Chat** | API + frontend (FastAPI serves static) | ✅ Deployed | https://mobius-chat-api-374396621405.us-central1.run.app | 1 |
| **Mobius Chat** | Worker | ✅ Deployed | https://mobius-chat-worker-374396621405.us-central1.run.app | 1 |
| **Web Scraper** | API | ✅ Deployed | https://mobius-skills-scraper-374396621405.us-central1.run.app | 0 |
| **Web Scraper** | Worker | ✅ Deployed | https://mobius-skills-scraper-worker-374396621405.us-central1.run.app | 0 |
| **Mobius DBT** | Job UI | ✅ Deployed | https://mobius-dbt-ui-374396621405.us-central1.run.app | 0 |

---

## Infrastructure

| Resource | Status | Details |
|----------|--------|---------|
| **Redis (Memorystore)** | ✅ Ready | `10.30.217.227:6379` |
| **VPC Connector** | ✅ Ready | `mobius-redis-connector` |
| **Cloud SQL** | ✅ Ready | `mobiusos-new:us-central1:mobius-platform-db` (db-f1-micro, ~25 connections) |
| **Secrets** | ✅ Ready | `app-secret-key`, `db-password`, `jwt-secret` |
| **GCS Bucket** | ✅ Ready | `mobius-rag-uploads-mobiusos` |
| **Vertex AI Index** | ✅ Ready | 8,128 vectors, endpoint `4513040034206580736` |

---

## Quick Reference

**Module Hub (dashboard):** https://module-hub-374396621405.us-central1.run.app

**Health checks:**
- OS: `curl https://mobius-os-backend-374396621405.us-central1.run.app/health`
- RAG: `curl https://mobius-rag-374396621405.us-central1.run.app/health`
- Chat: `curl https://mobius-chat-api-374396621405.us-central1.run.app/health`
- Scraper: `curl https://mobius-skills-scraper-374396621405.us-central1.run.app/health`
- DBT UI: `curl https://mobius-dbt-ui-374396621405.us-central1.run.app/config`

---

## Worker Configuration (Critical Settings)

Chat workers (always on):
- `--no-cpu-throttling` (CPU always allocated for background threads)
- `--min-instances=1` (always running to poll Redis)
- `--vpc-connector=mobius-redis-connector` (access to Redis private IP)
- `--vpc-egress=private-ranges-only` (route private IPs through VPC)

Non-critical workers (scale to 0):
- `--min-instances=0` (cold start ~10-30s when first accessed)
- RAG chunking/embedding workers, scraper workers

---

## Post-Deployment Fixes (2026-02-04)

### 1. RAG Frontend - Scraper Integration
**Issue:** Production RAG frontend missing "Scrape from URL" option
**Fix:** Rebuilt frontend with environment variables:
```bash
VITE_API_BASE="" \
VITE_SCRAPER_API_BASE=https://mobius-skills-scraper-374396621405.us-central1.run.app \
npm run build
```

### 2. Database Connection Exhaustion
**Issue:** `FATAL: remaining connection slots are reserved for non-replication superuser connections`
**Cause:** Cloud SQL `db-f1-micro` tier has ~25 max connections; too many services with min-instances=1
**Fix:** Reduced min-instances to 0 on non-critical services:
- mobius-rag-chunking-worker
- mobius-rag-embedding-worker
- mobius-skills-scraper
- mobius-skills-scraper-worker

### 3. Progress Events Not Streaming
**Issue:** Chat UI not showing live "thinking" progress - `events=0` in logs
**Cause:** `chat_progress_events` table missing in production database
**Fix:** Ran migration:
```sql
CREATE TABLE IF NOT EXISTS chat_progress_events (
    id BIGSERIAL PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_progress_events_correlation_created
    ON chat_progress_events(correlation_id, created_at ASC, id ASC);
```

---

## Staging vs Production Comparison

| Config | Staging | Production |
|--------|---------|------------|
| **Project** | `mobius-staging-mobius` | `mobiusos-new` |
| **Cloud SQL** | `mobius-platform-staging-db` | `mobius-platform-db` |
| **Redis** | `10.121.0.3:6379` | `10.30.217.227:6379` |
| **Vertex Index Endpoint** | `6304346785993195520` | `4513040034206580736` |
| **Vertex Deployed Index** | `mobius_chat_staging_1770153134390` | `endpoint_mobius_chat_publi_1769989702095` |
| **Vertex Vectors** | 0 (empty) | 8,128 |
| **GCS Bucket** | `mobius-rag-uploads-staging` | `mobius-rag-uploads-mobiusos` |

---

## Known Limitations

1. **Cloud SQL Tier**: `db-f1-micro` has limited connections (~25). Consider upgrading to `db-g1-small` for more headroom.
2. **Cold Starts**: Non-critical workers scale to 0 and have ~10-30s cold start latency.
3. **Staging RAG**: Vertex AI index is empty - RAG won't return results until populated.

---

## Deployment Date

**2026-02-04**
