#!/usr/bin/env bash
# Create landing tables for CMHC HCRIS in each landing_cmhc_{env}: hcris_rpt, hcris_nmrc, hcris_alpha.
# Run after create_bq_datasets.sh.

set -e
BQ_PROJECT="${BQ_PROJECT:-mobiusos-new}"

echo "Creating CMHC landing tables in project: $BQ_PROJECT"

for env in dev staging prod; do
  LANDING_DATASET="landing_cmhc_${env}"

  echo "  [$env] Creating ${LANDING_DATASET}.hcris_rpt..."
  bq query --project_id="$BQ_PROJECT" --use_legacy_sql=false --nouse_cache "
    CREATE TABLE IF NOT EXISTS \`${BQ_PROJECT}.${LANDING_DATASET}.hcris_rpt\` (
      report_record_key STRING NOT NULL,
      provider_ccn STRING,
      fiscal_year_start DATE,
      fiscal_year_end DATE,
      report_status STRING,
      form_vintage STRING
    )
    OPTIONS(description = 'HCRIS CMHC report index: one row per cost report filing.');
  "

  echo "  [$env] Creating ${LANDING_DATASET}.hcris_nmrc..."
  bq query --project_id="$BQ_PROJECT" --use_legacy_sql=false --nouse_cache "
    CREATE TABLE IF NOT EXISTS \`${BQ_PROJECT}.${LANDING_DATASET}.hcris_nmrc\` (
      report_record_key STRING NOT NULL,
      worksheet STRING,
      line INT64,
      \`column\` INT64,
      value FLOAT64
    )
    OPTIONS(description = 'HCRIS CMHC numeric cells: worksheet/line/column/value per report.');
  "

  echo "  [$env] Creating ${LANDING_DATASET}.hcris_alpha..."
  bq query --project_id="$BQ_PROJECT" --use_legacy_sql=false --nouse_cache "
    CREATE TABLE IF NOT EXISTS \`${BQ_PROJECT}.${LANDING_DATASET}.hcris_alpha\` (
      report_record_key STRING NOT NULL,
      worksheet STRING,
      line INT64,
      \`column\` INT64,
      value STRING
    )
    OPTIONS(description = 'HCRIS CMHC alphanumeric cells: worksheet/line/column/value per report.');
  "
done

echo "Done."
