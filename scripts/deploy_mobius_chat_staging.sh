#!/usr/bin/env bash
# Deploy Mobius Chat API and Worker to staging with shared Redis (VPC connector).
# Fixes "Waiting for worker…" by ensuring API and worker use QUEUE_TYPE=redis,
# same REDIS_URL, and both reach Redis via mobius-redis-connector.
#
# Usage:
#   export STAGING_PROJECT_ID=mobius-staging-mobius REGION=us-central1
#   export CLOUDSQL_CONNECTION_NAME=mobius-staging-mobius:us-central1:mobius-platform-staging-db
#   export PLATFORM_SA=mobius-platform-staging@${STAGING_PROJECT_ID}.iam.gserviceaccount.com
#   export REDIS_URL=redis://10.121.0.3:6379/0
#   ./scripts/deploy_mobius_chat_staging.sh
#
# Optional: BUILD_TAG=my-tag (default: git rev-parse --short HEAD)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

: "${STAGING_PROJECT_ID:?Set STAGING_PROJECT_ID}"
: "${REGION:=us-central1}"
: "${CLOUDSQL_CONNECTION_NAME:?Set CLOUDSQL_CONNECTION_NAME}"
: "${PLATFORM_SA:?Set PLATFORM_SA}"
if [[ -z "${REDIS_URL:-}" ]]; then
  if [[ -n "${REDIS_HOST:-}" ]]; then
    REDIS_URL="redis://${REDIS_HOST}:6379/0"
  else
    echo "Set REDIS_URL (or REDIS_HOST)" >&2
    exit 1
  fi
fi

TAG="${BUILD_TAG:-$(git rev-parse --short HEAD)}"
IMAGE="gcr.io/${STAGING_PROJECT_ID}/mobius-chat-api:${TAG}"

echo "Building mobius-chat image ${IMAGE}..."
cd mobius-chat
gcloud builds submit --project="$STAGING_PROJECT_ID" --tag="$IMAGE"
cd "$REPO_ROOT"

# API needs same Cloud SQL URL format as worker: host in query string (?host=%2Fcloudsql%2F...) and password
DB_PASS=$(gcloud secrets versions access latest --secret=db-password-mobius-chat --project="$STAGING_PROJECT_ID")
CLOUDSQL_HOST="${CLOUDSQL_CONNECTION_NAME//:/%3A}"
CHAT_DB_URL="postgresql://mobius_app:${DB_PASS}@/mobius_chat?host=%2Fcloudsql%2F${CLOUDSQL_HOST}"

API_ENV="CHAT_RAG_DATABASE_URL=${CHAT_DB_URL},QUEUE_TYPE=redis,REDIS_URL=${REDIS_URL}"

echo "Deploying mobius-chat-api (with VPC connector for Redis, Cloud SQL for recent searches / threads)..."
gcloud run deploy mobius-chat-api \
  --project="$STAGING_PROJECT_ID" \
  --region="$REGION" \
  --image="$IMAGE" \
  --service-account="$PLATFORM_SA" \
  --add-cloudsql-instances="$CLOUDSQL_CONNECTION_NAME" \
  --set-env-vars="$API_ENV" \
  --set-secrets="JWT_SECRET=jwt-secret:latest" \
  --clear-network \
  --vpc-connector=mobius-redis-connector \
  --vpc-egress=private-ranges-only \
  --allow-unauthenticated

echo "Deploying mobius-chat-worker (same Redis, same Cloud SQL, VPC connector, CPU always allocated, RAG enabled)..."
# RAG: Vertex AI Vector Search index in mobiusos-new project (8k+ document vectors)
VERTEX_INDEX_ENDPOINT_ID="4513040034206580736"
VERTEX_DEPLOYED_INDEX_ID="endpoint_mobius_chat_publi_1769989702095"
WORKER_ENV="CHAT_RAG_DATABASE_URL=${CHAT_DB_URL},QUEUE_TYPE=redis,REDIS_URL=${REDIS_URL},VERTEX_PROJECT_ID=mobiusos-new,VERTEX_LOCATION=us-central1,VERTEX_MODEL=gemini-2.5-flash,LLM_PROVIDER=vertex,VERTEX_INDEX_ENDPOINT_ID=${VERTEX_INDEX_ENDPOINT_ID},VERTEX_DEPLOYED_INDEX_ID=${VERTEX_DEPLOYED_INDEX_ID}"

# --no-cpu-throttling is CRITICAL: worker runs a background Redis consumer thread.
# Without CPU always allocated, Cloud Run throttles CPU when no HTTP traffic,
# starving the background thread and causing jobs to hang.
gcloud run deploy mobius-chat-worker \
  --project="$STAGING_PROJECT_ID" \
  --region="$REGION" \
  --image="$IMAGE" \
  --service-account="$PLATFORM_SA" \
  --add-cloudsql-instances="$CLOUDSQL_CONNECTION_NAME" \
  --set-env-vars="$WORKER_ENV" \
  --set-secrets="JWT_SECRET=jwt-secret:latest" \
  --max-instances=1 \
  --min-instances=1 \
  --no-cpu-throttling \
  --timeout=3600 \
  --clear-network \
  --vpc-connector=mobius-redis-connector \
  --vpc-egress=private-ranges-only \
  --allow-unauthenticated \
  --command="python" \
  --args="-m,uvicorn,app.worker_server:app,--host,0.0.0.0,--port,8080"

echo "Done. Check worker logs for: run_worker starting queue_type=redis, Redis connected, Worker listening for chat requests."
