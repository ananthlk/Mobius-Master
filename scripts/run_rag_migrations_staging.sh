#!/usr/bin/env bash
# Run mobius-rag DB migrations (create tables + all migrations) against staging mobius_rag.
# Required for chunking/embedding workers. Use Cloud SQL Proxy for connectivity.
#
# Usage:
#   # Terminal 1: Start Cloud SQL Proxy
#   cloud-sql-proxy mobius-staging-mobius:us-central1:mobius-platform-staging-db --port 5433 &
#
#   # Terminal 2: Run with password from Secret Manager
#   ./scripts/run_rag_migrations_staging.sh
#
#   # Or with explicit DATABASE_URL:
#   DATABASE_URL="postgresql+asyncpg://mobius_app:PASSWORD@127.0.0.1:5433/mobius_rag" ./scripts/run_rag_migrations_staging.sh
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOBIUS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$MOBIUS_ROOT/mobius-rag" || exit 1

export STAGING_PROJECT_ID="${STAGING_PROJECT_ID:-mobius-staging-mobius}"
export CLOUDSQL_CONN="mobius-staging-mobius:us-central1:mobius-platform-staging-db"

if [[ -z "$DATABASE_URL" ]]; then
  echo "Fetching password from Secret Manager..."
  DB_PASS=$(gcloud secrets versions access latest --secret=db-password-mobius-rag --project="$STAGING_PROJECT_ID" 2>/dev/null || true)
  if [[ -z "$DB_PASS" ]]; then
    echo "Set DATABASE_URL (e.g. postgresql+asyncpg://mobius_app:PASSWORD@127.0.0.1:5433/mobius_rag)"
    echo "Or ensure Cloud SQL Proxy is running and gcloud has access to Secret Manager."
    echo ""
    echo "Start proxy: cloud-sql-proxy $CLOUDSQL_CONN --port 5433 &"
    exit 1
  fi
  export DATABASE_URL="postgresql+asyncpg://mobius_app:${DB_PASS}@127.0.0.1:5433/mobius_rag"
fi

echo "Running RAG migrations against mobius_rag..."
uv run python run_staging_migrations.py
