#!/usr/bin/env bash
# One-off Cloud Run Job: embed the shipped corpus/chunks into pgvector
# (product_awareness.cli ingest-from-chunks). Runs in-cloud so it has the SA's
# Vertex + Cloud SQL access — no local proxy or ADC needed.
set -euo pipefail

ENV_LABEL="${1:-}"
[[ -n "${ENV_LABEL}" ]] || { echo "usage: $0 <env>" >&2; exit 64; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${SERVICE_DIR}/deploy/${ENV_LABEL}.env"
[[ -f "${ENV_FILE}" ]] || { echo "${ENV_FILE} not found" >&2; exit 66; }
set -a; source "${ENV_FILE}"; set +a

JOB_NAME="${SERVICE_NAME}-ingest"
IMAGE="${IMAGE_BASE}:latest"

ENV_CSV="^##^PRODUCT_DOCS_STORE=${PRODUCT_DOCS_STORE}##PRODUCT_DOCS_EMBEDDER=${PRODUCT_DOCS_EMBEDDER}##VERTEX_PROJECT_ID=${VERTEX_PROJECT_ID}##VERTEX_LOCATION=${VERTEX_LOCATION}##PRODUCT_DOCS_DATABASE_URL=${PRODUCT_DOCS_DATABASE_URL}##PRODUCT_DOCS_DB_NAME=${PRODUCT_DOCS_DB_NAME}##PRODUCT_DOCS_DB_USER=${PRODUCT_DOCS_DB_USER}##PRODUCT_DOCS_DB_HOST=${PRODUCT_DOCS_DB_HOST}"

gcloud run jobs deploy "${JOB_NAME}" \
    --project="${GCP_PROJECT}" --region="${GCP_REGION}" \
    --image="${IMAGE}" \
    --service-account="${SERVICE_ACCOUNT}" \
    --set-cloudsql-instances="${CLOUDSQL_INSTANCE}" \
    --set-env-vars="${ENV_CSV}" \
    --set-secrets="PRODUCT_DOCS_DB_PASSWORD=${DB_PASSWORD_SECRET}:latest" \
    --command=python \
    --args="-m,product_awareness.cli,ingest-from-chunks" \
    --max-retries=1 --task-timeout=600 --memory=1Gi --cpu=1

gcloud run jobs execute "${JOB_NAME}" \
    --project="${GCP_PROJECT}" --region="${GCP_REGION}" --wait
