# Staging Deployment Status

Project: **mobius-staging-mobius** | Region: **us-central1**

---

## Deployed Services

| Module | Component | Status | URL |
|--------|-----------|--------|-----|
| **Module Hub** | Landing dashboard | ✅ Deployed | https://module-hub-1067520608482.us-central1.run.app |
| **Mobius OS** | Backend (Flask API) | ✅ Deployed | https://mobius-os-backend-1067520608482.us-central1.run.app |
| **Mobius RAG** | Backend + frontend (FastAPI + Vite) | ✅ Deployed | https://mobius-rag-1067520608482.us-central1.run.app |
| **Mobius RAG** | Chunking worker | ✅ Deployed | (internal) |
| **Mobius RAG** | Embedding worker | ✅ Deployed | (internal) |
| **Mobius Chat** | API + frontend (FastAPI serves static) | ✅ Deployed | https://mobius-chat-api-1067520608482.us-central1.run.app |
| **Mobius Chat** | Worker | ✅ Deployed | https://mobius-chat-worker-1067520608482.us-central1.run.app |
| **Web Scraper** | API | ✅ Deployed | https://mobius-skills-scraper-1067520608482.us-central1.run.app |
| **Web Scraper** | Worker | ✅ Deployed | https://mobius-skills-scraper-worker-1067520608482.us-central1.run.app |
| **Mobius DBT** | Job UI | ✅ Deployed | https://mobius-dbt-ui-1067520608482.us-central1.run.app |

---

## Infrastructure

| Resource | Details |
|----------|---------|
| **Cloud SQL** | `mobius-staging-mobius:us-central1:mobius-platform-staging-db` |
| **Redis** | `redis://10.121.0.3:6379/0` |
| **GCS bucket** | `mobius-rag-uploads-staging` |
| **Vertex AI Index Endpoint** | `6304346785993195520` |
| **Vertex AI Deployed Index** | `mobius_chat_staging_1770153134390` |
| **Vertex AI Vectors** | 0 (empty - RAG will return no results until populated) |

---

## Chat Worker Vertex AI Config (Fixed 2026-02-04)

Staging Chat Worker now correctly points to staging Vertex AI:
```
VERTEX_PROJECT_ID=mobius-staging-mobius
VERTEX_INDEX_ENDPOINT_ID=6304346785993195520
VERTEX_DEPLOYED_INDEX_ID=mobius_chat_staging_1770153134390
```

---

## Quick Reference

**Module Hub (dashboard):** https://module-hub-1067520608482.us-central1.run.app  

**Health checks:**
- OS: `curl https://mobius-os-backend-1067520608482.us-central1.run.app/health`
- RAG: `curl https://mobius-rag-1067520608482.us-central1.run.app/health`
- Chat: `curl https://mobius-chat-api-1067520608482.us-central1.run.app/health`
- Scraper: `curl https://mobius-skills-scraper-1067520608482.us-central1.run.app/health`
- DBT UI: `curl https://mobius-dbt-ui-1067520608482.us-central1.run.app/config`

---

## Known Limitations

1. **Vertex AI Index Empty**: Staging RAG/Chat won't return search results until the Vertex AI index is populated via DBT sync.
2. **Separate from Production**: Staging has its own databases, Redis, and Vertex AI index - fully isolated from production.
