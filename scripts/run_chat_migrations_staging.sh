#!/usr/bin/env bash
# Run mobius-chat DB migrations against staging mobius_chat database.
# Requires: Cloud SQL Proxy running (tcp:5433), or direct connectivity to the instance.
#
# Usage:
#   # Option A: Auto-fetch password from Secret Manager (recommended)
#   cloud-sql-proxy mobius-staging-mobius:us-central1:mobius-platform-staging-db --port 5433 &
#   sleep 3
#   ./scripts/run_chat_migrations_staging.sh
#
#   # Option B: With explicit URL
#   CHAT_RAG_DATABASE_URL="postgresql://mobius_app:PASSWORD@127.0.0.1:5433/mobius_chat" ./scripts/run_chat_migrations_staging.sh
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOBIUS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$MOBIUS_ROOT/mobius-chat" || exit 1

export STAGING_PROJECT_ID="${STAGING_PROJECT_ID:-mobius-staging-mobius}"

if [[ -z "$CHAT_RAG_DATABASE_URL" ]]; then
  echo "Fetching password from Secret Manager..."
  DB_PASS=$(gcloud secrets versions access latest --secret=db-password-mobius-chat --project="$STAGING_PROJECT_ID" 2>/dev/null || true)
  if [[ -z "$DB_PASS" ]]; then
    echo "Set CHAT_RAG_DATABASE_URL (e.g. postgresql://mobius_app:PASSWORD@127.0.0.1:5433/mobius_chat)"
    echo "Or ensure Cloud SQL Proxy is running and gcloud has access to Secret Manager."
    echo ""
    echo "Start proxy: cloud-sql-proxy mobius-staging-mobius:us-central1:mobius-platform-staging-db --port 5433 &"
    exit 1
  fi
  export CHAT_RAG_DATABASE_URL="postgresql://mobius_app:${DB_PASS}@127.0.0.1:5433/mobius_chat"
fi

# Ensure psycopg2 is available (required for Chat migrations)
if ! python3 -c "import psycopg2" 2>/dev/null; then
  echo "Installing psycopg2-binary..."
  pip3 install -q psycopg2-binary || pip install -q psycopg2-binary
fi
python3 -m app.db.run_migrations
