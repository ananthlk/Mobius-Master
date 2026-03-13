#!/usr/bin/env bash
# Clear PostgreSQL connection slots so mstart migrations can run.
# Use when you see: "remaining connection slots are reserved for non-replication superuser connections"
#
# Usage:
#   ./scripts/clear_db_slots.sh          # Restart proxy + terminate idle connections
#   ./scripts/clear_db_slots.sh --restart # Restart Cloud SQL instance (nuclear option)
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOBIUS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$MOBIUS_ROOT"

VENV="${MOBIUS_ROOT}/.venv"
PROXY_PORT=5433
CLOUDSQL_CONN="${CLOUDSQL_CONNECTION_NAME:-mobius-os-dev:us-central1:mobius-platform-dev-db}"
CLOUDSQL_INST="${CLOUDSQL_INSTANCE:-mobius-platform-dev-db}"
CLOUDSQL_PROJ="${GCP_PROJECT:-mobius-os-dev}"

if [[ "$1" == "--restart" ]]; then
  echo "[clear_db_slots] Restarting Cloud SQL instance (clears all connections) ..."
  if ! command -v gcloud >/dev/null 2>&1; then
    echo "[clear_db_slots] ERROR: gcloud not found"
    exit 1
  fi
  gcloud sql instances restart "$CLOUDSQL_INST" --project="$CLOUDSQL_PROJ" --quiet
  echo "[clear_db_slots] Waiting 90s for instance to come back ..."
  sleep 90
  echo "[clear_db_slots] Killing proxy, starting fresh..."
  pid=$(lsof -ti :"$PROXY_PORT" 2>/dev/null) || true
  [[ -n "$pid" ]] && echo "$pid" | xargs kill -9 2>/dev/null || true
  sleep 3
  PROXY_BIN=""
  for p in cloud-sql-proxy "$HOME/google-cloud-sdk/bin/cloud-sql-proxy" /opt/homebrew/bin/cloud-sql-proxy; do
    command -v "$p" >/dev/null 2>&1 || [[ -x "$p" ]] 2>/dev/null && PROXY_BIN="$p" && break
  done
  if [[ -n "$PROXY_BIN" ]]; then
    "$PROXY_BIN" "$CLOUDSQL_CONN" --port "$PROXY_PORT" >> "${MOBIUS_ROOT}/.mobius_logs/cloud-sql-proxy.log" 2>&1 &
    for i in {1..20}; do nc -z 127.0.0.1 $PROXY_PORT 2>/dev/null && break; sleep 1; done
    sleep 2
  fi
  echo "[clear_db_slots] Snapshot of connections (check for unknown IPs):"
  echo "---"
  if [[ -x "$VENV/bin/python3" ]] && [[ -f "$MOBIUS_ROOT/scripts/show_db_connections.py" ]]; then
    "$VENV/bin/python3" "$MOBIUS_ROOT/scripts/show_db_connections.py" 2>&1 || echo "(could not query - run manually after mstart)"
  fi
  echo "---"
  echo "[clear_db_slots] Done. Run: mstart"
  exit 0
fi

# 1. Restart cloud-sql-proxy (drops our connections)
echo "[clear_db_slots] Restarting Cloud SQL Proxy ..."
pid=$(lsof -ti :"$PROXY_PORT" 2>/dev/null) || true
if [[ -n "$pid" ]]; then
  echo "$pid" | xargs kill -9 2>/dev/null || true
  echo "[clear_db_slots] Killed proxy"
fi
sleep 5

# 2. Start fresh proxy
PROXY_BIN=""
for p in cloud-sql-proxy "$HOME/google-cloud-sdk/bin/cloud-sql-proxy" /opt/homebrew/bin/cloud-sql-proxy; do
  if command -v "$p" >/dev/null 2>&1 || [[ -x "$p" ]] 2>/dev/null; then
    PROXY_BIN="$p"
    break
  fi
done
if [[ -z "$PROXY_BIN" ]]; then
  echo "[clear_db_slots] ERROR: cloud-sql-proxy not found"
  exit 1
fi

echo "[clear_db_slots] Starting proxy on port $PROXY_PORT ..."
"$PROXY_BIN" "$CLOUDSQL_CONN" --port "$PROXY_PORT" >> "${MOBIUS_ROOT}/.mobius_logs/cloud-sql-proxy.log" 2>&1 &
for i in {1..15}; do
  if nc -z 127.0.0.1 $PROXY_PORT 2>/dev/null; then
    echo "[clear_db_slots] Proxy ready"
    break
  fi
  sleep 1
done

sleep 3
echo "[clear_db_slots] Terminating idle DB connections ..."
if [[ -x "$VENV/bin/python3" ]] && [[ -f "$MOBIUS_ROOT/scripts/cleanup_db_connections.py" ]]; then
  if "$VENV/bin/python3" "$MOBIUS_ROOT/scripts/cleanup_db_connections.py" 2>&1; then
    echo "[clear_db_slots] Done. Run: mstart"
  else
    echo "[clear_db_slots] Cleanup failed (slots may still be full). Try: ./scripts/clear_db_slots.sh --restart"
    exit 1
  fi
else
  echo "[clear_db_slots] Run migrations to test: cd mobius-chat && python -m app.db.run_migrations"
fi
