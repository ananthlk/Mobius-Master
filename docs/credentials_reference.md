# Mobius Credentials Reference

Single place to look up credential sources for **dev**, **staging**, and **prod**.  
**Do not store actual passwords or API keys in this file.** Use Secret Manager, `.env` (gitignored), or local files excluded from version control.

---

## Environment Overview

| Env | GCP Project | Cloud SQL | Redis | Services |
|-----|-------------|-----------|-------|----------|
| **dev** | mobiusos-new (or local) | Local / shared dev instance | localhost:6379 | Local (mstart) |
| **staging** | mobius-staging-mobius | Cloud SQL (staging) | Memorystore 10.121.0.3 | Cloud Run |
| **prod** | mobiusos-new (or prod project) | Cloud SQL (prod) | Memorystore | Cloud Run / GKE |

---

## Dev

| Item | Value / Source |
|------|----------------|
| **GCP project** | mobiusos-new |
| **Cloud SQL (if used)** | Connection name or host:port from infra |
| **Postgres host** | localhost or 34.59.175.121 (shared dev) |
| **Postgres user** | postgres or mobius_app |
| **Postgres password** | In `mobius-config/.env` or per-module `.env` — do not commit |
| **Redis** | redis://localhost:6379/0 |
| **GCS bucket** | mobius-rag-uploads-mobiusos |
| **Vertex project** | mobiusos-new |
| **BigQuery** | mobiusos-new, mobius_rag_dev |
| **JWT_SECRET** | mobius-config or mobius-chat `.env` |
| **SECRET_KEY (OS)** | mobius-os/backend `.env` |

**Env source:** `mobius-config/.env`, `mobius-config/.env.example`. Use `inject_env.sh` or `run_with_shared_env.sh` to load into modules.

---

## Staging

| Item | Value / Source |
|------|----------------|
| **GCP project** | mobius-staging-mobius |
| **Region** | us-central1 |
| **Cloud SQL connection** | mobius-staging-mobius:us-central1:mobius-platform-staging-db |
| **Databases** | mobius, mobius_rag, mobius_chat, mobius_user |
| **Postgres user** | mobius_app |
| **Postgres passwords** | Secret Manager (see below) |
| **Redis** | redis://10.121.0.3:6379/0 (Memorystore; VPC required) |
| **GCS bucket** | mobius-rag-uploads-staging |
| **Vertex** | mobius-staging-mobius, us-central1 |

### Staging Secret Manager

| Secret Name | Purpose |
|-------------|---------|
| db-password-mobius | mobius DB |
| db-password-mobius-rag | mobius_rag DB |
| db-password-mobius-chat | mobius_chat DB |
| db-password-mobius-user | mobius_user DB |
| app-secret-key | Flask SECRET_KEY (mobius-os) |
| jwt-secret | JWT signing (shared) |
| chat-database-url-staging | Full CHAT_DATABASE_URL for DBT sync |

### Retrieve Staging Secrets

```bash
export STAGING_PROJECT_ID=mobius-staging-mobius

# Individual passwords
gcloud secrets versions access latest --secret=db-password-mobius --project="$STAGING_PROJECT_ID"
gcloud secrets versions access latest --secret=db-password-mobius-rag --project="$STAGING_PROJECT_ID"
gcloud secrets versions access latest --secret=db-password-mobius-chat --project="$STAGING_PROJECT_ID"
gcloud secrets versions access latest --secret=db-password-mobius-user --project="$STAGING_PROJECT_ID"
gcloud secrets versions access latest --secret=app-secret-key --project="$STAGING_PROJECT_ID"
gcloud secrets versions access latest --secret=jwt-secret --project="$STAGING_PROJECT_ID"
gcloud secrets versions access latest --secret=chat-database-url-staging --project="$STAGING_PROJECT_ID"
```

### Staging Service URLs

| Service | URL |
|---------|-----|
| Module Hub | https://module-hub-1067520608482.us-central1.run.app |
| Mobius OS | https://mobius-os-backend-1067520608482.us-central1.run.app |
| Mobius RAG | https://mobius-rag-1067520608482.us-central1.run.app |
| Mobius Chat | https://mobius-chat-api-1067520608482.us-central1.run.app |
| Web Scraper | https://mobius-skills-scraper-1067520608482.us-central1.run.app |
| DBT Job UI | https://mobius-dbt-ui-1067520608482.us-central1.run.app |

---

## Prod

| Item | Value / Source |
|------|----------------|
| **GCP project** | mobiusos-new (or dedicated prod project) |
| **Cloud SQL** | Prod instance connection name |
| **Databases** | mobius, mobius_rag, mobius_chat, mobius_user |
| **Secrets** | Secret Manager in prod project |
| **Redis** | Memorystore (record host from GCP) |
| **GCS bucket** | prod bucket name |
| **Vertex** | Prod project, region, index IDs |

Create a parallel Secret Manager inventory in prod and document in this section when prod is configured.

---

## Local Credentials File (Optional)

To maintain a local copy of resolved values for convenience:

1. Copy `credentials.env.template` to `credentials.local.env`
2. Fill in values (or run the gcloud commands above and paste)
3. Add `credentials.local.env` to `.gitignore` — **never commit it**
4. Source when needed: `set -a && source credentials.local.env && set +a`

---

## Related Docs

- [DATA_SCHEMA_AND_CREDENTIALS.md](DATA_SCHEMA_AND_CREDENTIALS.md) — per-module env vars
- [staging_iam_and_secrets.md](staging_iam_and_secrets.md) — staging Secret Manager setup
- [staging_deployment_status.md](staging_deployment_status.md) — staging service URLs and status
