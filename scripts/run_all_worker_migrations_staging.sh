#!/usr/bin/env bash
# Run both Chat and RAG DB migrations for staging. Required for workers before first deploy.
#
# Prerequisites:
#   - Cloud SQL Proxy running: cloud-sql-proxy mobius-staging-mobius:us-central1:mobius-platform-staging-db --port 5433 &
#   - gcloud configured with access to mobius-staging-mobius and Secret Manager
#
# Usage:
#   ./scripts/run_all_worker_migrations_staging.sh
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOBIUS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export STAGING_PROJECT_ID="${STAGING_PROJECT_ID:-mobius-staging-mobius}"
export CLOUDSQL_CONN="mobius-staging-mobius:us-central1:mobius-platform-staging-db"

echo "=== Worker DB Migrations for Staging ==="
echo "Project: $STAGING_PROJECT_ID"
echo ""
echo "Ensure Cloud SQL Proxy is running first:"
echo "  cloud-sql-proxy $CLOUDSQL_CONN --port 5433 &"
echo "  sleep 3"
echo ""

# Fetch passwords once
echo "Fetching passwords from Secret Manager..."
CHAT_PASS=$(gcloud secrets versions access latest --secret=db-password-mobius-chat --project="$STAGING_PROJECT_ID" 2>/dev/null || true)
RAG_PASS=$(gcloud secrets versions access latest --secret=db-password-mobius-rag --project="$STAGING_PROJECT_ID" 2>/dev/null || true)

if [[ -z "$CHAT_PASS" ]]; then
  echo "ERROR: Could not fetch db-password-mobius-chat. Check gcloud auth and project."
  exit 1
fi
if [[ -z "$RAG_PASS" ]]; then
  echo "ERROR: Could not fetch db-password-mobius-rag. Check gcloud auth and project."
  exit 1
fi

export CHAT_RAG_DATABASE_URL="postgresql://mobius_app:${CHAT_PASS}@127.0.0.1:5433/mobius_chat"
export DATABASE_URL="postgresql+asyncpg://mobius_app:${RAG_PASS}@127.0.0.1:5433/mobius_rag"

echo ""
echo "--- Chat migrations (mobius_chat) ---"
if ! python3 -c "import psycopg2" 2>/dev/null; then
  echo "Installing psycopg2-binary for Chat migrations..."
  pip3 install -q psycopg2-binary 2>/dev/null || pip install -q psycopg2-binary
fi
cd "$MOBIUS_ROOT/mobius-chat" && python3 -m app.db.run_migrations

echo ""
echo "--- RAG migrations (mobius_rag) ---"
cd "$MOBIUS_ROOT/mobius-rag" && uv run python run_staging_migrations.py

echo ""
echo "=== All worker migrations completed ==="
