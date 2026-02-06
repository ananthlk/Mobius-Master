# Staging IAM & Secret Manager Setup

This guide extends the staging infrastructure work by configuring service accounts, Secret Manager entries, and environment files that map to staging credentials. Follow after completing [docs/staging_shared_infrastructure.md](staging_shared_infrastructure.md).

---

## 1. Service Accounts

Two tiers are recommended:

| Service Account | Purpose | Notes |
| --- | --- | --- |
| `mobius-platform-staging@` | Default runtime identity for Cloud Run services, workers, and batch jobs. | Already created in [docs/staging_gcp_project.md](staging_gcp_project.md); ensure roles remain `cloudsql.client`, `storage.objectAdmin`, `aiplatform.user`, `redis.viewer`. |
| `mobius-cicd-staging@` (optional) | Dedicated CI/CD identity for Cloud Build triggers deploying to staging. | Grants more granular permissions without using the project default Cloud Build SA. |

### 1.1 Optional CI/CD Service Account

```bash
export STAGING_PROJECT_ID=mobius-staging

gcloud iam service-accounts create mobius-cicd-staging \
  --project="$STAGING_PROJECT_ID" \
  --display-name="Mobius CI/CD (staging)"

for role in roles/run.admin roles/cloudsql.client roles/secretmanager.secretAccessor roles/artifactregistry.writer; do
  gcloud projects add-iam-policy-binding "$STAGING_PROJECT_ID" \
    --member="serviceAccount:mobius-cicd-staging@${STAGING_PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done
```

Create a workload identity binding or add this account as the execution identity in Cloud Build triggers.

---

## 2. Secret Manager Inventory

Create secrets mirroring production key names so scripts can switch environments by project. Suggested naming:

| Secret Name | Purpose | Source |
| --- | --- | --- |
| `db-password-mobius` | Cloud SQL `mobius` database password for `mobius_app` user. | Generate random using `openssl rand -base64 20`. |
| `db-password-mobius-rag` | Password for RAG DB if using separate user. |
| `db-password-mobius-chat` | Chat database user password (if separate). |
| `db-password-mobius-user` | `mobius_user` database password. |
| `app-secret-key` | Flask secret for `mobius-os`. |
| `jwt-secret` | Shared JWT secret for `mobius-user`. |
| `vertex-service-account` (optional) | Service account key JSON if Vertex requires file-based auth (prefer Workload Identity). |
| `gcs-service-account` (optional) | For workers needing direct key files. |

### 2.1 Creating Secrets

```bash
create_secret () {
  local name=$1
  local value=$2
  echo -n "$value" | gcloud secrets create "$name" \
    --project="$STAGING_PROJECT_ID" \
    --data-file=-
}

create_secret db-password-mobius "$(openssl rand -base64 20)"
create_secret db-password-mobius-rag "$(openssl rand -base64 20)"
create_secret db-password-mobius-chat "$(openssl rand -base64 20)"
create_secret db-password-mobius-user "$(openssl rand -base64 20)"
create_secret app-secret-key "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
create_secret jwt-secret "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

> Use `gcloud secrets versions add` to rotate secrets later.

### 2.2 Grant Access

```bash
for secret in db-password-mobius db-password-mobius-rag db-password-mobius-chat db-password-mobius-user app-secret-key jwt-secret; do
  gcloud secrets add-iam-policy-binding "$secret" \
    --project="$STAGING_PROJECT_ID" \
    --member="serviceAccount:mobius-platform-staging@${STAGING_PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

Add the CI/CD account if used:

```bash
for secret in ...; do
  gcloud secrets add-iam-policy-binding "$secret" \
    --project="$STAGING_PROJECT_ID" \
    --member="serviceAccount:mobius-cicd-staging@${STAGING_PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

---

## 3. Environment Files (`mobius-config`)

1. Copy `mobius-config/.env.example` to `mobius-config/.env.staging`.
2. Populate with staging values:
   ```env
   GCP_PROJECT_ID=mobius-staging
   CLOUDSQL_CONNECTION_NAME=mobius-staging:us-central1:mobius-platform-staging-db
   MOBIUS_DATABASE_URL=postgresql+psycopg2://mobius_app:${DB_PASSWORD_MOBIUS}@/cloudsql/${CLOUDSQL_CONNECTION_NAME}/mobius
   DATABASE_URL=postgresql+asyncpg://mobius_app:${DB_PASSWORD_MOBIUS_RAG}@/cloudsql/${CLOUDSQL_CONNECTION_NAME}/mobius_rag
   CHAT_DATABASE_URL=postgresql://mobius_app:${DB_PASSWORD_MOBIUS_CHAT}@/cloudsql/${CLOUDSQL_CONNECTION_NAME}/mobius_chat
   USER_DATABASE_URL=postgresql://mobius_app:${DB_PASSWORD_MOBIUS_USER}@/cloudsql/${CLOUDSQL_CONNECTION_NAME}/mobius_user
   REDIS_URL=redis://<memorystore-ip>:6379/0
   GCS_BUCKET=mobius-rag-uploads-staging
   VERTEX_PROJECT_ID=mobius-staging
   VERTEX_LOCATION=us-central1
   VERTEX_INDEX_ENDPOINT_ID=<staging-endpoint-id>
   VERTEX_DEPLOYED_INDEX_ID=<staging-deployed-index-id>
   JWT_SECRET=projects/mobius-staging/secrets/jwt-secret
   SECRET_KEY=projects/mobius-staging/secrets/app-secret-key
   ```
3. Use `mobius-config/env_helper.py` to inject staging env into each module when deploying.

---

## 4. Secret Projection in Cloud Run

When deploying services, mount Secret Manager references as environment variables:

```bash
gcloud run deploy mobius-os-backend \
  --project="$STAGING_PROJECT_ID" \
  --region=us-central1 \
  --image=gcr.io/$STAGING_PROJECT_ID/mobius-os-backend:<tag> \
  --set-secrets=SECRET_KEY=app-secret-key:latest \
  --set-secrets=POSTGRES_PASSWORD_CLOUD=db-password-mobius:latest \
  --set-env-vars="DATABASE_MODE=cloud,CLOUDSQL_CONNECTION_NAME=${CLOUDSQL_CONNECTION_NAME},..." \
  --service-account=mobius-platform-staging@${STAGING_PROJECT_ID}.iam.gserviceaccount.com \
  --add-cloudsql-instances="${CLOUDSQL_CONNECTION_NAME}"
```

Replicate for RAG, Chat, DBT runner, scraper, etc., substituting the correct secrets.

---

## 5. Audit & Documentation

After setup:
- Run `gcloud secrets list --project="$STAGING_PROJECT_ID"` and verify expected secrets.
- Document secret names, rotation schedule, and owners in `docs/release_logs/<date>-staging-infra.md`.
- Ensure `docs/production_build_checklist.md` Section 2 references staging `.env` or Secret Manager for parity checks.

This completes staging IAM and secret preparation. Proceed to deploying services on Cloud Run.
