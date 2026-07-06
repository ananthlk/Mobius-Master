# BigQuery SQL Templates — DOGE Benchmarking

> Replace `{project}.{dataset}.{table}` with the user's actual BQ path.
> Replace `{service_month_filter}` with the appropriate WHERE clause for the selected time window.

---

## Table of Contents
1. Base KPI aggregation (NPI level)
2. Geographic rollups (ZIP, MSA, State, National)
3. Taxonomy-adjusted peer group
4. HCPCS code-level drill
5. Time window variants
6. Benchmark position computation

---

## 1. Base KPI Aggregation — NPI + Taxonomy Level

```sql
SELECT
  service_month,
  servicing_npi,
  taxonomy_code,                          -- join from NPI registry lookup
  SUM(total_beneficiaries)   AS panel_size,
  SAFE_DIVIDE(SUM(total_claims), SUM(total_beneficiaries)) AS claims_per_beneficiary,
  SAFE_DIVIDE(SUM(total_paid), SUM(total_claims))          AS payment_per_claim,
  SUM(total_claims)          AS total_claims,
  SUM(total_paid)            AS total_paid
FROM `{project}.{dataset}.{table}`
{service_month_filter}
GROUP BY 1, 2, 3
```

---

## 2. Geographic Rollups

### ZIP Level
```sql
SELECT
  service_month,
  provider_zip,                           -- must be joined from NPI registry
  taxonomy_code,
  COUNT(DISTINCT servicing_npi)                              AS provider_count,
  SUM(total_beneficiaries)                                   AS total_beneficiaries,
  SAFE_DIVIDE(SUM(total_beneficiaries), COUNT(DISTINCT servicing_npi)) AS avg_panel_size,
  SAFE_DIVIDE(SUM(total_claims), SUM(total_beneficiaries))   AS claims_per_beneficiary,
  SAFE_DIVIDE(SUM(total_paid), SUM(total_claims))            AS payment_per_claim
FROM `{project}.{dataset}.{table}` d
JOIN `{project}.{dataset}.npi_taxonomy_map` t USING (servicing_npi)  -- NPI registry enrichment
{service_month_filter}
GROUP BY 1, 2, 3
```

### MSA Level
```sql
-- Replace provider_zip → msa_code using CBSA crosswalk
-- Standard ZIP-to-CBSA crosswalk available from HUD or HRSA
SELECT
  service_month,
  msa_code,
  msa_name,
  taxonomy_code,
  COUNT(DISTINCT servicing_npi)                              AS provider_count,
  SUM(total_beneficiaries)                                   AS total_beneficiaries,
  SAFE_DIVIDE(SUM(total_beneficiaries), COUNT(DISTINCT servicing_npi)) AS avg_panel_size,
  SAFE_DIVIDE(SUM(total_claims), SUM(total_beneficiaries))   AS claims_per_beneficiary,
  SAFE_DIVIDE(SUM(total_paid), SUM(total_claims))            AS payment_per_claim
FROM `{project}.{dataset}.{table}` d
JOIN `{project}.{dataset}.npi_taxonomy_map` t USING (servicing_npi)
JOIN `{project}.{dataset}.zip_msa_crosswalk` z USING (provider_zip)
{service_month_filter}
GROUP BY 1, 2, 3, 4
```

### State Level
```sql
SELECT
  service_month,
  provider_state,
  taxonomy_code,
  COUNT(DISTINCT servicing_npi)                              AS provider_count,
  SUM(total_beneficiaries)                                   AS total_beneficiaries,
  SAFE_DIVIDE(SUM(total_beneficiaries), COUNT(DISTINCT servicing_npi)) AS avg_panel_size,
  SAFE_DIVIDE(SUM(total_claims), SUM(total_beneficiaries))   AS claims_per_beneficiary,
  SAFE_DIVIDE(SUM(total_paid), SUM(total_claims))            AS payment_per_claim
FROM `{project}.{dataset}.{table}` d
JOIN `{project}.{dataset}.npi_taxonomy_map` t USING (servicing_npi)
{service_month_filter}
GROUP BY 1, 2, 3
```

---

## 3. Taxonomy-Adjusted Peer Group

This is the core query for fair peer comparison. Given a subject NPI's taxonomy mix, weight peer metrics accordingly.

### Step 1: Get subject taxonomy mix
```sql
-- Run this first to get the subject's taxonomy weights
SELECT
  taxonomy_code,
  SAFE_DIVIDE(SUM(total_claims), SUM(SUM(total_claims)) OVER()) AS taxonomy_weight
FROM `{project}.{dataset}.{table}` d
JOIN `{project}.{dataset}.npi_taxonomy_map` t USING (servicing_npi)
WHERE servicing_npi = '{subject_npi}'
  AND {service_month_filter}
GROUP BY 1
```

### Step 2: Compute weighted peer metrics
```sql
-- Apply subject's taxonomy weights to peer group
WITH subject_weights AS (
  SELECT taxonomy_code, {weight_value} AS weight  -- inject from Step 1
  FROM UNNEST([
    STRUCT('{taxonomy_1}' AS taxonomy_code, {w1} AS weight),
    STRUCT('{taxonomy_2}', {w2}),
    ...
  ])
),
peer_metrics AS (
  SELECT
    taxonomy_code,
    peer_geo_level,                        -- zip / msa / state / national
    SAFE_DIVIDE(SUM(total_beneficiaries), COUNT(DISTINCT servicing_npi)) AS avg_panel_size,
    SAFE_DIVIDE(SUM(total_claims), SUM(total_beneficiaries))             AS claims_per_beneficiary,
    SAFE_DIVIDE(SUM(total_paid), SUM(total_claims))                      AS payment_per_claim,
    STDDEV(SAFE_DIVIDE(total_paid, total_claims))                         AS stddev_payment_per_claim,
    COUNT(DISTINCT servicing_npi)                                         AS peer_n
  FROM `{project}.{dataset}.{table}` d
  JOIN `{project}.{dataset}.npi_taxonomy_map` t USING (servicing_npi)
  WHERE servicing_npi != '{subject_npi}'
    AND {geo_filter}
    AND {service_month_filter}
  GROUP BY 1, 2
)
SELECT
  SUM(pm.avg_panel_size * sw.weight)          AS weighted_peer_panel_size,
  SUM(pm.claims_per_beneficiary * sw.weight)  AS weighted_peer_claims_per_bene,
  SUM(pm.payment_per_claim * sw.weight)       AS weighted_peer_payment_per_claim
FROM peer_metrics pm
JOIN subject_weights sw USING (taxonomy_code)
```

---

## 4. HCPCS Code-Level Drill

```sql
SELECT
  service_month,
  servicing_npi,
  hcpcs_code,
  SUM(total_claims)          AS total_claims,
  SUM(total_beneficiaries)   AS total_beneficiaries,
  SUM(total_paid)            AS total_paid,
  SAFE_DIVIDE(SUM(total_paid), SUM(total_claims)) AS payment_per_claim
FROM `{project}.{dataset}.{table}`
WHERE servicing_npi = '{subject_npi}'
  AND {service_month_filter}
GROUP BY 1, 2, 3
ORDER BY total_claims DESC
```

---

## 5. Time Window Variants

### Single month
```sql
WHERE service_month = '{YYYYMM}'
```

### Rolling 3-month
```sql
WHERE service_month BETWEEN '{3_months_ago_YYYYMM}' AND '{current_month_YYYYMM}'
```

### Full year
```sql
WHERE service_month BETWEEN '{year_start_YYYYMM}' AND '{year_end_YYYYMM}'
```

> For trend analysis, remove the GROUP BY on service_month aggregation and keep it as a dimension.

---

## 6. Benchmark Position Computation

### Percentile Rank (run in BQ or Python post-query)
```sql
SELECT
  servicing_npi,
  panel_size,
  PERCENT_RANK() OVER (PARTITION BY taxonomy_code ORDER BY panel_size) AS panel_size_pctile,
  PERCENT_RANK() OVER (PARTITION BY taxonomy_code ORDER BY claims_per_beneficiary) AS cpb_pctile,
  PERCENT_RANK() OVER (PARTITION BY taxonomy_code ORDER BY payment_per_claim) AS ppc_pctile
FROM (
  -- nest the NPI-level KPI query here
)
```

### Z-Score (Python / pandas post-query)
```python
import pandas as pd

def compute_zscores(df, kpi_cols, group_col='taxonomy_code'):
    for col in kpi_cols:
        peer_mean = df.groupby(group_col)[col].transform('mean')
        peer_std  = df.groupby(group_col)[col].transform('std')
        df[f'{col}_zscore'] = (df[col] - peer_mean) / peer_std
    return df
```

### Above/Below Median Flag
```sql
SELECT
  *,
  CASE WHEN panel_size > PERCENTILE_CONT(panel_size, 0.5) OVER (PARTITION BY taxonomy_code)
       THEN 'above' ELSE 'below' END AS panel_size_vs_median
FROM (...)
```
