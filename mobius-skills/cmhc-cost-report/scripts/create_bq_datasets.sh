#!/usr/bin/env bash
# Create BigQuery datasets for CMHC HCRIS: landing_cmhc_{env}, mobius_cmhc_{env}.
# Requires: bq CLI and auth (gcloud auth application-default login).
# After this, run scripts/create_env_tables.sh to create the tables.

set -e
BQ_PROJECT="${BQ_PROJECT:-mobiusos-new}"
BQ_LOCATION="${BQ_LOCATION:-US}"

echo "Creating CMHC datasets in project: $BQ_PROJECT (location: $BQ_LOCATION)"

for env in dev staging prod; do
  echo "  Creating landing_cmhc_${env}..."
  bq mk --project_id="$BQ_PROJECT" --dataset --location="$BQ_LOCATION" "${BQ_PROJECT}:landing_cmhc_${env}" 2>/dev/null || true
  echo "  Creating mobius_cmhc_${env}..."
  bq mk --project_id="$BQ_PROJECT" --dataset --location="$BQ_LOCATION" "${BQ_PROJECT}:mobius_cmhc_${env}" 2>/dev/null || true
done

echo "Done. Next: ./scripts/create_env_tables.sh"
