#!/usr/bin/env bash
# Deploy Module Hub (landing/dashboard) to Cloud Run.
# Requires: gcloud CLI.
#
# Usage:
#   ./scripts/deploy_module_hub_cloudrun.sh
#
# Optional env vars (set before running to configure service URLs in production):
#   MOBIUS_OS_URL, MOBIUS_CHAT_URL, MOBIUS_RAG_BACKEND_URL, MOBIUS_RAG_FRONTEND_URL,
#   MOBIUS_DBT_URL, MOBIUS_SCRAPER_URL, MOBIUS_REDIS_HOST, MOBIUS_REDIS_PORT
#
# Example:
#   MOBIUS_OS_URL=https://os-xxx.run.app MOBIUS_CHAT_URL=https://chat-xxx.run.app ./scripts/deploy_module_hub_cloudrun.sh
#
set -e

PROJECT_ID="${GCP_PROJECT_ID:-mobiusos-new}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="module-hub"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Deploy Module Hub to Cloud Run ==="
echo "Project: $PROJECT_ID | Region: $REGION | Service: $SERVICE_NAME"
echo ""

gcloud services enable cloudbuild.googleapis.com run.googleapis.com --project="$PROJECT_ID" --quiet 2>/dev/null || true
gcloud auth configure-docker gcr.io --quiet 2>/dev/null || true

echo "Building and pushing image..."
gcloud builds submit --config=cloudbuild.module-hub.yaml --project="$PROJECT_ID" .

echo "Deploying to Cloud Run..."

# Build --set-env-vars: ENV=prod and PORT (Cloud Run sets PORT; we set ENV).
ENV_VARS="ENV=prod,PORT=8080"
if [[ -n "$MOBIUS_OS_URL" ]]; then ENV_VARS="${ENV_VARS},MOBIUS_OS_URL=${MOBIUS_OS_URL}"; fi
if [[ -n "$MOBIUS_CHAT_URL" ]]; then ENV_VARS="${ENV_VARS},MOBIUS_CHAT_URL=${MOBIUS_CHAT_URL}"; fi
if [[ -n "$MOBIUS_RAG_BACKEND_URL" ]]; then ENV_VARS="${ENV_VARS},MOBIUS_RAG_BACKEND_URL=${MOBIUS_RAG_BACKEND_URL}"; fi
if [[ -n "$MOBIUS_RAG_FRONTEND_URL" ]]; then ENV_VARS="${ENV_VARS},MOBIUS_RAG_FRONTEND_URL=${MOBIUS_RAG_FRONTEND_URL}"; fi
if [[ -n "$MOBIUS_DBT_URL" ]]; then ENV_VARS="${ENV_VARS},MOBIUS_DBT_URL=${MOBIUS_DBT_URL}"; fi
if [[ -n "$MOBIUS_SCRAPER_URL" ]]; then ENV_VARS="${ENV_VARS},MOBIUS_SCRAPER_URL=${MOBIUS_SCRAPER_URL}"; fi
if [[ -n "$MOBIUS_REDIS_HOST" ]]; then ENV_VARS="${ENV_VARS},MOBIUS_REDIS_HOST=${MOBIUS_REDIS_HOST}"; fi
if [[ -n "$MOBIUS_REDIS_PORT" ]]; then ENV_VARS="${ENV_VARS},MOBIUS_REDIS_PORT=${MOBIUS_REDIS_PORT}"; fi

gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --memory=256Mi \
  --cpu=1 \
  --set-env-vars="$ENV_VARS" \
  --project="$PROJECT_ID" \
  --quiet

SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)')
echo ""
echo "=== Deploy complete ==="
echo "Module Hub: $SERVICE_URL"
echo ""
echo "Set MOBIUS_*_URL (and Redis host/port if needed) in Cloud Run env vars so the dashboard links and probes point to your GCP services."
echo "See docs/DEPLOY_MODULE_HUB_GCP.md for env vars and steps."
