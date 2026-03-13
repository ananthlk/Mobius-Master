#!/usr/bin/env bash
# One environment setup for all of Mobius.
# Run from repo root: ./scripts/setup_one_env.sh
#
# 1. Python: .venv + root requirements.txt + Mobius-user editable install
# 2. Env: copy mobius-config/.env.example → mobius-config/.env (if missing)
# 3. Optional: copy key vars into service .env files so dbt/scripts see BQ_* and Medicaid vars
# 4. BigQuery: create dev datasets (landing_rag, mobius_rag, landing_medicaid_npi_dev, mobius_medicaid_npi_dev)
# 5. GCP: remind user to run gcloud auth application-default login
# 6. Optional: dbt seed + run for Medicaid NPI (B0–B6)
#
# After this: ./mstart to run all services. For dbt: source mobius-config/.env (or ensure BQ_* set), then cd mobius-dbt && dbt run.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MOBIUS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$MOBIUS_ROOT"

echo "=============================================="
echo "  Mobius — one environment setup"
echo "=============================================="
echo ""

# --- 1. Python venv ---
if [[ ! -d ".venv" ]]; then
  echo "Creating .venv ..."
  python3.11 -m venv .venv || python3 -m venv .venv
fi
echo "Activating .venv ..."
# shellcheck source=/dev/null
source .venv/bin/activate

echo "Installing dependencies (requirements.txt) ..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
if [[ -d "Mobius-user" ]]; then
  pip install -q -e ./Mobius-user
fi
echo "  Done."
echo ""

# --- 2. Single .env from mobius-config ---
CONFIG_ENV="$MOBIUS_ROOT/mobius-config/.env"
if [[ ! -f "$CONFIG_ENV" ]]; then
  if [[ -f "$MOBIUS_ROOT/mobius-config/.env.example" ]]; then
    cp "$MOBIUS_ROOT/mobius-config/.env.example" "$CONFIG_ENV"
    echo "Created mobius-config/.env from .env.example (single source of env for all of Mobius)."
  else
    echo "No mobius-config/.env.example found. Create mobius-config/.env manually."
  fi
else
  echo "mobius-config/.env already exists."
fi
echo ""

# --- 3. Ensure service .env exist (so mstart and manual dbt see vars); symlink or copy from config ---
# mstart loads mobius-config/.env for some services. For dbt we need BQ_* when running from mobius-dbt.
# Option: source mobius-config/.env before dbt. Here we just ensure mobius-dbt/.env has a pointer or copy.
if [[ -f "$CONFIG_ENV" ]] && [[ -d "$MOBIUS_ROOT/mobius-dbt" ]]; then
  if [[ ! -f "$MOBIUS_ROOT/mobius-dbt/.env" ]]; then
    cp "$CONFIG_ENV" "$MOBIUS_ROOT/mobius-dbt/.env" 2>/dev/null || true
    echo "Created mobius-dbt/.env from mobius-config/.env (for dbt and B6 report scripts)."
  fi
fi
echo ""

# --- 4. BigQuery datasets ---
echo "Creating BigQuery datasets (if missing) ..."
export BQ_PROJECT="${BQ_PROJECT:-mobius-os-dev}"
export BQ_LOCATION="${BQ_LOCATION:-US}"
if [[ -f "$CONFIG_ENV" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$CONFIG_ENV"
  set +a
fi
BQ_PROJECT="${BQ_PROJECT:-mobius-os-dev}"
BQ_LANDING_MEDICAID="${BQ_LANDING_MEDICAID_DATASET:-landing_medicaid_npi_dev}"
BQ_MARTS_MEDICAID="${BQ_MARTS_MEDICAID_DATASET:-mobius_medicaid_npi_dev}"

if command -v bq >/dev/null 2>&1; then
  for ds in landing_rag mobius_rag "$BQ_LANDING_MEDICAID" "$BQ_MARTS_MEDICAID"; do
    bq mk --project_id="$BQ_PROJECT" --dataset --location="${BQ_LOCATION:-US}" "${BQ_PROJECT}:${ds}" 2>/dev/null || true
  done
  echo "  Datasets: landing_rag, mobius_rag, $BQ_LANDING_MEDICAID, $BQ_MARTS_MEDICAID"
else
  echo "  bq CLI not found; skip dataset creation. Run: gcloud auth application-default login && ./mobius-dbt/scripts/create_bq_datasets.sh"
fi
echo ""

# --- 5. GCP auth ---
echo "Ensure GCP auth: gcloud auth application-default login"
echo ""

# --- 6. Optional: dbt seed + Medicaid B6 ---
if [[ -t 0 ]]; then
  read -r -p "Run dbt seed and Medicaid NPI models (B0–B6)? [y/N] " reply
  if [[ "$reply" =~ ^[yY] ]]; then
    export BQ_PROJECT BQ_MARTS_MEDICAID_DATASET BQ_LANDING_MEDICAID_DATASET
    BQ_MARTS_MEDICAID_DATASET="${BQ_MARTS_MEDICAID_DATASET:-mobius_medicaid_npi_dev}"
    BQ_LANDING_MEDICAID_DATASET="${BQ_LANDING_MEDICAID_DATASET:-landing_medicaid_npi_dev}"
    cd "$MOBIUS_ROOT/mobius-dbt"
    dbt seed
    dbt run --select +b6_integrated_report_fl
    cd "$MOBIUS_ROOT"
    echo "  dbt seed and B6 run done."
  fi
else
  echo "To build Medicaid NPI (B0–B6): source mobius-config/.env && cd mobius-dbt && dbt seed && dbt run --select +b6_integrated_report_fl"
fi
echo ""

echo "=============================================="
echo "  One environment ready"
echo "=============================================="
echo "  Venv:    $MOBIUS_ROOT/.venv  (activate: source .venv/bin/activate)"
echo "  Env:     mobius-config/.env  (single source for BQ, Postgres, Vertex, Medicaid NPI)"
echo "  Start:   ./mstart"
echo "  Stop:    ./mstop"
echo ""
echo "  DBT:     source mobius-config/.env && cd mobius-dbt && dbt run"
echo "  B6 report: source mobius-config/.env && python mobius-dbt/scripts/generate_b6_report.py --name \"Aspire Behavioral Health\""
echo ""
echo "  If DB migrations fail (Cloud SQL unreachable):"
echo "    docker compose -f mobius-chat/docker-compose.yml up -d"
echo "    Then set CHAT_RAG_DATABASE_URL=postgresql://mobius:mobius@localhost:5433/mobius_chat_rag in mobius-chat/.env"
echo ""
