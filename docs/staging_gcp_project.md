# Staging GCP Project Bootstrap

Purpose: spin up a dedicated staging foundation (`mobius-staging`) that mirrors the production architecture while remaining isolated. Complete this checklist before provisioning shared infrastructure or deploying services.

---

## 1. Prerequisites

| Item | Details |
| --- | --- |
| GCP organization access | Ability to create projects, link billing accounts, and manage IAM. |
| Billing account | Use the same billing account as production unless finance requests a separate one. |
| `gcloud` CLI | Install and authenticate: `gcloud auth login` + `gcloud auth application-default login`. |
| Project naming | Recommended: **`mobius-staging`** (ID `mobius-staging` if available). Record in `docs/release_logs`. |

---

## 2. Create and Initialize Project

```bash
# Replace values if a different name/ID is needed
export STAGING_PROJECT_ID=mobius-staging

# Create project under the Mobius org/folder
gcloud projects create "$STAGING_PROJECT_ID" \
  --name="Mobius Staging" \
  --set-as-default

# Link billing
gcloud beta billing projects link "$STAGING_PROJECT_ID" \
  --billing-account <BILLING_ACCOUNT_ID>

# Set default project for subsequent commands
gcloud config set project "$STAGING_PROJECT_ID"
```

---

## 3. Enable Core APIs

Enable the same baseline APIs used in production (see `[mobius-os/backend/PRODUCTION_CONFIG.md](../mobius-os/backend/PRODUCTION_CONFIG.md)` and `[mobius-rag/docs/GCP_DEPLOYMENT.md](../mobius-rag/docs/GCP_DEPLOYMENT.md)`):

```bash
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  containerregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  compute.googleapis.com \
  monitoring.googleapis.com \
  logging.googleapis.com \
  redis.googleapis.com
```

> Keep the command idempotent; re-running in the future will confirm APIs remain active.

---

## 4. Align IAM Baseline

1. **Identify core service accounts** required in staging (mirrors production guidance):
   - Cloud Build SA: `${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com`
   - Cloud Run default compute SA: `${PROJECT_NUMBER}-compute@developer.gserviceaccount.com`
   - Dedicated platform SA (created in Section 5)

2. Grant the same roles called out in production docs:
   ```bash
   PROJECT_ID=$(gcloud config get-value project)
   PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

   gcloud projects add-iam-policy-binding "$PROJECT_ID" \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/run.admin"

   gcloud projects add-iam-policy-binding "$PROJECT_ID" \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/cloudsql.client"

   gcloud projects add-iam-policy-binding "$PROJECT_ID" \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"

   gcloud projects add-iam-policy-binding "$PROJECT_ID" \
     --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
     --role="roles/cloudsql.client"

   gcloud projects add-iam-policy-binding "$PROJECT_ID" \
     --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

3. For human operators, add staging-specific viewer/editor roles as needed (e.g., `roles/viewer`, `roles/editor`, `roles/iam.serviceAccountTokenCreator`). Keep parity with production RBAC.

---

## 5. Create the Staging Platform Service Account

```bash
gcloud iam service-accounts create mobius-platform-staging \
  --display-name="Mobius Platform (staging)"

gcloud projects add-iam-policy-binding "$STAGING_PROJECT_ID" \
  --member="serviceAccount:mobius-platform-staging@${STAGING_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding "$STAGING_PROJECT_ID" \
  --member="serviceAccount:mobius-platform-staging@${STAGING_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding "$STAGING_PROJECT_ID" \
  --member="serviceAccount:mobius-platform-staging@${STAGING_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding "$STAGING_PROJECT_ID" \
  --member="serviceAccount:mobius-platform-staging@${STAGING_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/redis.viewer"
```

> Do **not** create JSON keys unless automation requires them. Prefer Workload Identity or Secret Manager.

---

## 6. Record Project Metadata

- Document project ID, billing account, and owners in `docs/release_logs/<date>-staging.md`.
- Update shared tooling (e.g., Terraform or scripts) with the new project ID.
- Notify the team in release planning so the staging environment is the new dry-run target.

Once all steps complete, hand off to shared infrastructure provisioning (Cloud SQL, GCS, Vertex, Redis) per the staging plan.
