#!/usr/bin/env bash
# Cloud Run deploy for mobius-feedback. Same shape as mobius-skills/vibe.
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

GIT_SHA="$(git -C "${SERVICE_DIR}" rev-parse --short=10 HEAD 2>/dev/null \
            || git -C "${SERVICE_DIR}/.." rev-parse --short=10 HEAD 2>/dev/null \
            || echo nogit)"
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
        --timeout=15m
else
    IMAGE_TAG="$(gcloud artifacts docker images list "${IMAGE_BASE}" \
        --project="${GCP_PROJECT}" --include-tags --format='value(IMAGE,TAGS)' \
        --sort-by="~UPDATE_TIME" --limit=1 | awk '{print $1":"$2}' | awk -F, '{print $1}')"
    [[ -n "${IMAGE_TAG}" ]] || { echo "no prior image"; exit 71; }
fi

SET_ENV_VARS=(
    "FEEDBACK_LLM_STAGE=${FEEDBACK_LLM_STAGE}"
    "FEEDBACK_MAX_TOKENS=${FEEDBACK_MAX_TOKENS}"
    "FEEDBACK_LLM_ROUTER_URL=${FEEDBACK_LLM_ROUTER_URL}"
    "FEEDBACK_USE_CHAT_LLM_ROUTER=1"
)

SET_SECRETS=(
    "MOBIUS_SKILL_LLM_INTERNAL_KEY=mobius-skill-llm-internal-key:latest"
)

run gcloud run deploy "${SERVICE_NAME}" \
    --project="${GCP_PROJECT}" --region="${GCP_REGION}" \
    --image="${IMAGE_TAG}" \
    --service-account="${SERVICE_ACCOUNT}" \
    --platform=managed --allow-unauthenticated \
    --memory="${RUN_MEMORY}" --cpu="${RUN_CPU}" \
    --concurrency="${RUN_CONCURRENCY}" --timeout="${RUN_TIMEOUT}" \
    --min-instances="${RUN_MIN_INSTANCES}" --max-instances="${RUN_MAX_INSTANCES}" \
    --port=8080 \
    --set-env-vars="$(csv_env "${SET_ENV_VARS[@]}")" \
    --set-secrets="$(csv_env "${SET_SECRETS[@]}")" \
    --cpu-boost --execution-environment=gen2

if [[ "${DRY_RUN}" -eq 0 ]]; then
    URL="$(gcloud run services describe "${SERVICE_NAME}" \
        --project="${GCP_PROJECT}" --region="${GCP_REGION}" \
        --format='value(status.url)')"
    echo; echo "✓ ${URL}"
    echo "Wire into chat: CHAT_SKILLS_FEEDBACK_URL=${URL}/classify"
fi
