# Staging Cloud Run Deployments

Deploy each Mobius service into the staging project after infrastructure and secrets are configured. All commands assume:

```bash
export STAGING_PROJECT_ID=mobius-staging-mobius
export REGION=us-central1
export CLOUDSQL_CONNECTION_NAME=mobius-staging-mobius:us-central1:mobius-platform-staging-db
export PLATFORM_SA=mobius-platform-staging@${STAGING_PROJECT_ID}.iam.gserviceaccount.com
export REDIS_HOST=10.121.0.3
export REDIS_URL=redis://10.121.0.3:6379/0
```

---

## 1. Mobius OS Backend

Build and deploy using the existing script (`mobius-os/deploy.sh`). The script currently defaults to production project; override with env vars:

```bash
cd mobius-os

GCP_PROJECT_ID=$STAGING_PROJECT_ID \
REGION=$REGION \
CLOUDSQL_INSTANCE=$CLOUDSQL_CONNECTION_NAME \
./deploy.sh deploy
```

If the script requires interactive password input, preload from Secret Manager:

```bash
DB_PASSWORD=$(gcloud secrets versions access latest --secret=db-password-mobius --project="$STAGING_PROJECT_ID")

gcloud run deploy mobius-os-backend \
  --project="$STAGING_PROJECT_ID" \
  --region="$REGION" \
  --image=gcr.io/$STAGING_PROJECT_ID/mobius-os-backend:$(git rev-parse --short HEAD) \
  --add-cloudsql-instances="$CLOUDSQL_CONNECTION_NAME" \
  --set-env-vars="DATABASE_MODE=cloud,GCP_PROJECT_ID=$STAGING_PROJECT_ID,CLOUDSQL_CONNECTION_NAME=$CLOUDSQL_CONNECTION_NAME" \
  --set-secrets="SECRET_KEY=app-secret-key:latest,POSTGRES_PASSWORD_CLOUD=db-password-mobius:latest" \
  --service-account="$PLATFORM_SA" \
  --allow-unauthenticated
```

---

## 2. Mobius RAG Backend + Workers

### 2.1 Backend (FastAPI)

```bash
cd mobius-rag

DATABASE_PASSWORD=$(gcloud secrets versions access latest --secret=db-password-mobius-rag --project="$STAGING_PROJECT_ID")

./deploy/deploy_cloudrun.sh \
  --project "$STAGING_PROJECT_ID" \
  --region "$REGION" \
  --database-password "$DATABASE_PASSWORD" \
  --cloud-sql-instance "$CLOUDSQL_CONNECTION_NAME" \
  --service-account "$PLATFORM_SA" \
  --bucket mobius-rag-uploads-staging \
  --vertex-project "$STAGING_PROJECT_ID" \
  --vertex-location "us-central1" \
  --vertex-index-id "<staging-index-id>"
```

Ensure the script supports flag overrides; otherwise, adapt by editing env vars before running.

### 2.2 Workers (Chunking & Embedding)

Workers are long-running processes; options:

- **Cloud Run Jobs/Services**: containerize worker entrypoints (`./mragw`, `./mrage`). Deploy with `--max-instances=1 --cpu=1 --memory=512Mi --timeout=3600`.
- **Compute Engine**: reuse systemd units from `mobius-rag/deploy/systemd/` on a staging VM.

For Cloud Run example:

```bash
gcloud run deploy mobius-rag-chunking-worker \
  --image=gcr.io/$STAGING_PROJECT_ID/mobius-rag-worker:<tag> \
  --project="$STAGING_PROJECT_ID" \
  --region="$REGION" \
  --service-account="$PLATFORM_SA" \
  --set-env-vars="WORKER_TYPE=chunking,REDIS_URL=$REDIS_URL,..." \
  --set-secrets="DATABASE_URL=db-password-mobius-rag:latest" \
  --add-cloudsql-instances="$CLOUDSQL_CONNECTION_NAME" \
  --timeout=3600 \
  --max-instances=1
```

Repeat for embedding worker with `WORKER_TYPE=embedding`.

---

## 3. Mobius Chat (API + Worker)

**One-command deploy (recommended):** From repo root, set `STAGING_PROJECT_ID`, `REGION`, `CLOUDSQL_CONNECTION_NAME`, `PLATFORM_SA`, and `REDIS_URL` (or `REDIS_HOST`), then run:

```bash
./scripts/deploy_mobius_chat_staging.sh
```

This builds the image and deploys both API and worker with VPC connector and shared Redis so the UI does not stay on "Waiting for worker…".

### 3.1 Build image

```bash
cd mobius-chat
gcloud builds submit --project="$STAGING_PROJECT_ID" --tag=gcr.io/$STAGING_PROJECT_ID/mobius-chat-api:$(git rev-parse --short HEAD)
```

### 3.2 Deploy API

The API must use **QUEUE_TYPE=redis** and the **same REDIS_URL** as the worker, and must be able to reach Redis (private IP). Use a VPC connector so the API can LPUSH to the same Redis the worker BRPOPs from.

```bash
gcloud run deploy mobius-chat-api \
  --project="$STAGING_PROJECT_ID" \
  --region="$REGION" \
  --image=gcr.io/$STAGING_PROJECT_ID/mobius-chat-api:<tag> \
  --service-account="$PLATFORM_SA" \
  --add-cloudsql-instances="$CLOUDSQL_CONNECTION_NAME" \
  --set-env-vars="CHAT_RAG_DATABASE_URL=postgresql://mobius_app@/cloudsql/$CLOUDSQL_CONNECTION_NAME/mobius_chat,QUEUE_TYPE=redis,REDIS_URL=$REDIS_URL" \
  --set-secrets="JWT_SECRET=jwt-secret:latest" \
  --vpc-connector=mobius-redis-connector \
  --vpc-egress=private-ranges-only \
  --allow-unauthenticated
```

### 3.3 Deploy Worker

Worker needs: **same REDIS_URL as the API**, VPC connector to reach Redis, Cloud SQL for DB, **VERTEX_PROJECT_ID=mobiusos-new** (LLM is in that project), min-instances=1 so it stays running to poll Redis, and **--no-cpu-throttling** (CPU always allocated) because the worker runs a background Redis consumer thread.

```bash
DB_PASS=$(gcloud secrets versions access latest --secret=db-password-mobius-chat --project="$STAGING_PROJECT_ID")
# Host format: /cloudsql/PROJECT:REGION:INSTANCE with colons URL-encoded as %3A
CHAT_DB_URL="postgresql://mobius_app:${DB_PASS}@/mobius_chat?host=%2Fcloudsql%2F${CLOUDSQL_CONNECTION_NAME//:/%3A}"

gcloud run deploy mobius-chat-worker \
  --project="$STAGING_PROJECT_ID" \
  --region="$REGION" \
  --image=gcr.io/$STAGING_PROJECT_ID/mobius-chat-api:latest \
  --service-account="$PLATFORM_SA" \
  --add-cloudsql-instances="$CLOUDSQL_CONNECTION_NAME" \
  --set-env-vars="CHAT_RAG_DATABASE_URL=${CHAT_DB_URL},QUEUE_TYPE=redis,REDIS_URL=$REDIS_URL,VERTEX_PROJECT_ID=mobiusos-new,VERTEX_LOCATION=us-central1,VERTEX_MODEL=gemini-2.5-flash,LLM_PROVIDER=vertex,VERTEX_INDEX_ENDPOINT_ID=4513040034206580736,VERTEX_DEPLOYED_INDEX_ID=endpoint_mobius_chat_publi_1769989702095" \
  --set-secrets="JWT_SECRET=jwt-secret:latest" \
  --max-instances=1 \
  --min-instances=1 \
  --no-cpu-throttling \
  --timeout=3600 \
  --network=default \
  --subnet=default \
  --vpc-connector=mobius-redis-connector \
  --vpc-egress=private-ranges-only \
  --command="python" \
  --args="-m,uvicorn,app.worker_server:app,--host,0.0.0.0,--port,8080"
```

> **Critical:** `--no-cpu-throttling` enables "CPU always allocated". Without this, Cloud Run only allocates CPU during HTTP request processing. The worker's background Redis consumer thread would be starved of CPU and jobs would hang.

Grant staging SA Vertex access in mobiusos-new: `gcloud projects add-iam-policy-binding mobiusos-new --member="serviceAccount:${PLATFORM_SA}" --role="roles/aiplatform.user"`

#### If the UI stays on "Waiting for worker…"

- **API and worker must share the same Redis.** Both need `QUEUE_TYPE=redis` and the same `REDIS_URL`. If the API uses the default `memory` queue, it enqueues in-process and no worker (separate service) will see the request.
- **Both must reach Redis.** Redis at private IP (e.g. `10.121.0.3`) is only reachable via VPC. Deploy both API and worker with `--vpc-connector=mobius-redis-connector` and `--vpc-egress=private-ranges-only`.
- **Check worker logs.** After redeploying with the latest code, worker logs should show: `run_worker starting queue_type=redis`, then `Redis connected for queue (host=..., request_key=mobius:chat:requests)`, then `Worker listening for chat requests`. When a request is picked up you should see `Received chat request correlation_id=...`. If you see `Redis connection failed` or no "Worker listening" line, the worker cannot reach Redis (connector/network).
- **Where to view:** Cloud Console → Logging → Logs Explorer, or Cloud Run → mobius-chat-worker → Logs. Filter by `resource.labels.service_name="mobius-chat-worker"`. To see only request/stream messages, filter by text: `Received chat request` or `Worker listening` or `[thinking]`. Repetitive "[RAG config] env" lines were downgraded to DEBUG so they don’t flood the log.

#### Worker messages not reaching frontend (API can write to Redis, worker picked up, but no UI update)

Two possibilities:

1. **Worker’s response never reaches Redis**  
   The worker must log **"Response published for &lt;cid&gt;"** after it finishes. The response is written to Redis at that moment (key `mobius:chat:response:{correlation_id}`). If the worker is **shut down** (e.g. "Shutting down" / "Finished server process") **before** that log line, the response is never in Redis and the frontend will never get it (stream stays pending, polling returns "pending").  
   **Fix:** Response is now published to Redis **first** (before clear_progress/store_response), so even if the worker is killed right after, the answer is already in Redis and the frontend can get it via polling.

2. **Frontend loses the stream connection**  
   If the EventSource connection drops (proxy timeout, load balancer, etc.) before the API sends the "completed" event, the frontend falls back to **polling** GET /chat/response/{id}. The UI shows "Reconnecting…" while polling. As long as the worker has logged "Response published", the next poll will return the response and the UI will show the answer.

**Check:** In worker logs, search for "Response published for" for the correlation_id you’re waiting on. If it’s missing, the worker was recycled or crashed before finishing.

#### Live stream (thinking / progress) – DB progress like RAG

Chat progress is now stored in **PostgreSQL** (`chat_progress_events`) when the queue is Redis, and the API stream **polls the DB** (like RAG’s `chunking_events`). No Redis subscribe from the API. Run the new migration before or after deploying:

- Apply `mobius-chat/db/schema/013_chat_progress_events.sql` against the chat DB (same DB as `chat_turns`). If you use `scripts/run_chat_migrations_staging.sh`, ensure it includes `013_chat_progress_events.sql`.

---

## 4. Mobius DBT Job UI

```bash
cd mobius-dbt
gcloud builds submit --project="$STAGING_PROJECT_ID" --tag=gcr.io/$STAGING_PROJECT_ID/mobius-dbt-ui:$(git rev-parse --short HEAD)

gcloud run deploy mobius-dbt-ui \
  --project="$STAGING_PROJECT_ID" \
  --region="$REGION" \
  --image=gcr.io/$STAGING_PROJECT_ID/mobius-dbt-ui:<tag> \
  --service-account="$PLATFORM_SA" \
  --set-env-vars="BQ_PROJECT=$STAGING_PROJECT_ID,POSTGRES_HOST=$CLOUDSQL_CONNECTION_NAME,..." \
  --set-secrets="POSTGRES_PASSWORD=db-password-mobius-rag:latest,CHAT_DATABASE_PASSWORD=db-password-mobius-chat:latest" \
  --allow-unauthenticated=false
```

Schedule `scripts/land_and_dbt_run.sh` via Cloud Scheduler/Cloud Build if desired (use staging env vars).

---

## 5. Mobius Skills (Web Scraper)

```bash
cd mobius-skills/web-scraper
gcloud builds submit --project="$STAGING_PROJECT_ID" --tag=gcr.io/$STAGING_PROJECT_ID/mobius-skills-scraper:$(git rev-parse --short HEAD)

gcloud run deploy mobius-skills-scraper \
  --project="$STAGING_PROJECT_ID" \
  --region="$REGION" \
  --image=gcr.io/$STAGING_PROJECT_ID/mobius-skills-scraper:<tag> \
  --service-account="$PLATFORM_SA" \
  --set-env-vars="REDIS_URL=$REDIS_URL,GCS_BUCKET=mobius-rag-uploads-staging" \
  --allow-unauthenticated=false
```

Optionally deploy worker variant if the scraper has asynchronous processing.

---

## 6. Module Hub (Landing Dashboard)

Use the provided script with staging variables:

```bash
cd /Users/ananth/Mobius

GCP_PROJECT_ID=$STAGING_PROJECT_ID \
GCP_REGION=$REGION \
MOBIUS_OS_URL=https://mobius-os-backend-staging-xxx.run.app \
MOBIUS_CHAT_URL=https://mobius-chat-api-staging-xxx.run.app \
MOBIUS_RAG_BACKEND_URL=https://mobius-rag-staging-xxx.run.app \
MOBIUS_RAG_FRONTEND_URL=https://mobius-rag-frontend-staging-xxx.run.app \
MOBIUS_DBT_URL=https://mobius-dbt-ui-staging-xxx.run.app \
MOBIUS_SCRAPER_URL=https://mobius-skills-scraper-staging-xxx.run.app \
MOBIUS_REDIS_HOST=10.121.0.3 \
MOBIUS_REDIS_PORT=6379 \
./scripts/deploy_module_hub_cloudrun.sh
```

Set `ENV=prod` to disable destructive actions in the dashboard.

---

## 7. Frontend Builds (if applicable)

- `mobius-os/extension`: Build and upload artifacts to staging storage or distribution channel as needed.
- `mobius-chat` frontend: Ensure `frontend/static/app.js` is part of the API image or served from Module Hub.

---

## 8. Post-Deployment Verification

1. Collect Cloud Run URLs:
   ```bash
   gcloud run services list --project="$STAGING_PROJECT_ID" --region="$REGION"
   ```
2. Update `docs/release_logs/<date>-staging-deploy.md` with service URLs and revision IDs.
3. Run health checks:
   ```bash
   curl https://mobius-os-backend-.../health
   curl https://mobius-rag-.../health
   curl https://mobius-chat-api-.../health
   ```
4. Ensure Module Hub reflects all services with green status.

Proceed to configure CI/CD triggers for automated staging deployments once manual verification passes.
