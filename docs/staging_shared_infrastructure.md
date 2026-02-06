# Staging Shared Infrastructure Provisioning

Use this checklist after the staging project is created ([docs/staging_gcp_project.md](staging_gcp_project.md)). It mirrors production infrastructure (Cloud SQL, GCS, Vertex AI, Redis) but runs in the isolated staging project.

---

## 1. Cloud SQL (PostgreSQL 15)

### 1.1 Create Instance

```bash
export STAGING_PROJECT_ID=mobius-staging
export REGION=us-central1
export STAGING_SQL_INSTANCE=mobius-platform-staging-db

gcloud sql instances create "$STAGING_SQL_INSTANCE" \
  --project="$STAGING_PROJECT_ID" \
  --database-version=POSTGRES_15 \
  --tier=db-custom-1-3840 \
  --region="$REGION" \
  --storage-size=20GB \
  --storage-auto-increase
```

### 1.2 Create Databases and Users

```bash
for db in mobius mobius_rag mobius_chat mobius_user; do
  gcloud sql databases create "$db" \
    --instance="$STAGING_SQL_INSTANCE" \
    --project="$STAGING_PROJECT_ID"
done

gcloud sql users create mobius_app \
  --instance="$STAGING_SQL_INSTANCE" \
  --project="$STAGING_PROJECT_ID" \
  --password="$(openssl rand -base64 20)"
```

Store generated secrets in Secret Manager (see next section).

### 1.3 Enable Private IP (recommended)

```bash
gcloud compute addresses create staging-google-managed-services \
  --global \
  --purpose=VPC_PEERING \
  --prefix-length=16 \
  --network=default \
  --project="$STAGING_PROJECT_ID"

gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=staging-google-managed-services \
  --network=default \
  --project="$STAGING_PROJECT_ID"

gcloud sql instances patch "$STAGING_SQL_INSTANCE" \
  --project="$STAGING_PROJECT_ID" \
  --network=default \
  --no-assign-public-ip
```

### 1.4 pgvector Extension for RAG

```bash
gcloud sql connect "$STAGING_SQL_INSTANCE" \
  --database=mobius_rag \
  --user=postgres \
  --project="$STAGING_PROJECT_ID" \
  --command="CREATE EXTENSION IF NOT EXISTS vector;"
```

---

## 2. Storage Buckets

Create buckets with staging suffixes to avoid collisions:

```bash
gsutil mb -p "$STAGING_PROJECT_ID" -l "$REGION" gs://mobius-rag-uploads-staging/
gsutil mb -p "$STAGING_PROJECT_ID" -l "$REGION" gs://mobius-shared-assets-staging/
gsutil lifecycle set lifecycle.json gs://mobius-rag-uploads-staging/
```

> Optional: Apply IAM bindings to restrict access (e.g., only staging platform SA + ops).

---

## 3. Vertex AI Resources

1. **LLM Model** – reuse the same public Model ID as production (e.g., `publishers/google/models/gemini-1.5-pro`). No extra work required other than ensuring the staging project has Vertex API enabled.
2. **Vector Search Index + Endpoint**
   ```bash
   export STAGING_VERTEX_LOCATION=us-central1

   gcloud alpha ai index-endpoints create \
     --project="$STAGING_PROJECT_ID" \
     --region="$STAGING_VERTEX_LOCATION" \
     --display-name="mobius-chat-staging-endpoint"

   gcloud alpha ai indexes create \
     --project="$STAGING_PROJECT_ID" \
     --region="$STAGING_VERTEX_LOCATION" \
     --display-name="mobius-chat-staging-index" \
     --description="Staging embeddings for chat" \
     --tree-ah-config "leafNodeEmbeddingCount=1000,leafNodesToSearchPercent=7" \
     --dimensions=1536 \
     --distance-measure-type="COSINE"

   # Deploy index to endpoint
   gcloud alpha ai index-endpoints deploy-index INDEX_ENDPOINT_ID \
     --deployed-index-id="mobius-chat-staging" \
     --project="$STAGING_PROJECT_ID" \
     --region="$STAGING_VERTEX_LOCATION" \
     --index="INDEX_ID" \
     --dedicated-resources "minReplicaCount=1,maxReplicaCount=1,machineSpec.machineType=e2-standard-2"
   ```

Record `INDEX_ENDPOINT_ID` and `DEPLOYED_INDEX_ID` for environment variables (`VERTEX_INDEX_ENDPOINT_ID`, `VERTEX_DEPLOYED_INDEX_ID`).

---

## 4. Redis (Cloud Memorystore)

RAG workers and scraper use Redis for queues. Provision a staging instance:

```bash
gcloud redis instances create mobius-staging-redis \
  --project="$STAGING_PROJECT_ID" \
  --region="$REGION" \
  --tier=basic \
  --size=1 \
  --redis-version=redis_6_x \
  --connect-mode=PRIVATE_SERVICE_ACCESS \
  --authorized-network=default
```

Store the resulting host IP in staging `.env` files (`REDIS_URL=redis://<ip>:6379/0`).

---

## 5. Artifact Registry (optional but recommended)

If you prefer Artifact Registry over Container Registry:

```bash
gcloud artifacts repositories create mobius-apps \
  --repository-format=Docker \
  --location="$REGION" \
  --project="$STAGING_PROJECT_ID"

gcloud auth configure-docker "$REGION-docker.pkg.dev"
```

Update deploy scripts to push to the staging repository.

---

## 6. Record Outputs

Create `docs/release_logs/<date>-staging-infra.md` with:

- Cloud SQL connection name
- Database user credentials location (Secret Manager IDs)
- Bucket names
- Vertex index/endpoint IDs
- Redis host
- Artifact Registry repository

These values feed into staging `.env` files via `mobius-config`.

When complete, proceed to service account/Secret Manager setup and Cloud Run deployments.
