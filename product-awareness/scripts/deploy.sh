#!/usr/bin/env bash
# Cloud Run deploy for mobius-product-awareness (the retrieval service).
# Same shape as mobius-feedback, plus Cloud SQL (pgvector) + Vertex env.
set -euo pipefail

ENV_LABEL="${1:-}"
[[ -n "${ENV_LABEL}" ]] || { echo "usage: $0 <env> [--dry-run] [--skip-build]" >&2; exit 64; }

DRY_RUN=0; SKIP_BUILD=0
shift || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --skip-build) SKIP_BUILD=1; shift ;;
        *) echo "unknown: $1" >&2; exit 64 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${SERVICE_DIR}/deploy/${ENV_LABEL}.env"
[[ -f "${ENV_FILE}" ]] || { echo "${ENV_FILE} not found" >&2; exit 66; }
set -a; source "${ENV_FILE}"; set +a

GIT_SHA="$(git -C "${SERVICE_DIR}/.." rev-parse --short=10 HEAD 2>/dev/null || echo nogit)"
BUILD_TS="$(date -u +%Y%m%d-%H%M%S)"
IMAGE_TAG="${IMAGE_BASE}:${BUILD_TS}-${GIT_SHA}"

run() { echo "+ $*"; [[ "${DRY_RUN}" -eq 1 ]] || "$@"; }
csv_env() { printf '%s\n' "$@" | paste -sd, -; }

if ! gcloud artifacts repositories describe "${AR_REPO}" \
        --project="${GCP_PROJECT}" --location="${GCP_REGION}" >/dev/null 2>&1; then
    run gcloud artifacts repositories create "${AR_REPO}" \
        --project="${GCP_PROJECT}" --location="${GCP_REGION}" \
        --repository-format=docker
fi

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
    run gcloud builds submit "${SERVICE_DIR}" \
        --project="${GCP_PROJECT}" --region="${GCP_REGION}" \
        --config="${SERVICE_DIR}/deploy/cloudbuild.yaml" \
        --ignore-file="${SERVICE_DIR}/deploy/.gcloudignore" \
        --substitutions="_IMAGE=${IMAGE_TAG},_IMAGE_BASE=${IMAGE_BASE},_DOCKERFILE=Dockerfile" \
        --timeout=20m
else
    IMAGE_TAG="${IMAGE_BASE}:latest"
fi

SET_ENV_VARS=(
    "PRODUCT_DOCS_STORE=${PRODUCT_DOCS_STORE}"
    "PRODUCT_DOCS_EMBEDDER=${PRODUCT_DOCS_EMBEDDER}"
    "VERTEX_PROJECT_ID=${VERTEX_PROJECT_ID}"
    "VERTEX_LOCATION=${VERTEX_LOCATION}"
    "PRODUCT_DOCS_DATABASE_URL=${PRODUCT_DOCS_DATABASE_URL}"
    "PRODUCT_DOCS_DB_NAME=${PRODUCT_DOCS_DB_NAME}"
    "PRODUCT_DOCS_DB_USER=${PRODUCT_DOCS_DB_USER}"
    "PRODUCT_DOCS_DB_HOST=${PRODUCT_DOCS_DB_HOST}"
    "PRODUCT_HELP_TAU_GAP=${PRODUCT_HELP_TAU_GAP}"
)

run gcloud run deploy "${SERVICE_NAME}" \
    --project="${GCP_PROJECT}" --region="${GCP_REGION}" \
    --image="${IMAGE_TAG}" \
    --service-account="${SERVICE_ACCOUNT}" \
    --platform=managed --allow-unauthenticated \
    --add-cloudsql-instances="${CLOUDSQL_INSTANCE}" \
    --memory="${RUN_MEMORY}" --cpu="${RUN_CPU}" \
    --concurrency="${RUN_CONCURRENCY}" --timeout="${RUN_TIMEOUT}" \
    --min-instances="${RUN_MIN_INSTANCES}" --max-instances="${RUN_MAX_INSTANCES}" \
    --port=8080 \
    --set-env-vars="^##^$(printf '%s##' "${SET_ENV_VARS[@]}" | sed 's/##$//')" \
    --set-secrets="PRODUCT_DOCS_DB_PASSWORD=${DB_PASSWORD_SECRET}:latest" \
    --cpu-boost --execution-environment=gen2

if [[ "${DRY_RUN}" -eq 0 ]]; then
    URL="$(gcloud run services describe "${SERVICE_NAME}" \
        --project="${GCP_PROJECT}" --region="${GCP_REGION}" \
        --format='value(status.url)')"
    echo; echo "✓ ${URL}"
    echo "Wire into chat: CHAT_SKILLS_PRODUCT_HELP_SEARCH_URL=${URL}/search"
    echo "Now populate pgvector:  bash scripts/reindex.sh ${ENV_LABEL}"
fi
