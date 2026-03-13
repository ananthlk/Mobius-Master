"""
Utilization trend benchmarks: claims/member, revenue/member, revenue/claim by taxonomy and geography.

- Pre-populated table: taxonomy_utilization_benchmarks (ZIP, state, national).
- Org benchmark: utilization metrics for active NPIs tied to this org (computed on-the-fly from DOGE).
Used by Step 10 to estimate potential revenue for missed/errored NPIs.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Key for org-level benchmark in the benchmarks dict
ORG_BENCHMARK_KEY = "org"


def populate_benchmarks_table(
    bq_client: Any,
    *,
    project: str,
    landing_dataset: str,
    marts_dataset: str,
    period: str = "2024",
    state_filter: str = "FL",
) -> dict[str, Any]:
    """
    Populate taxonomy_utilization_benchmarks table (Step 9).
    Run as part of the flow to ensure revenue metrics are in place before Step 10.

    Returns: {"status": "ok", "table": "project.dataset.taxonomy_utilization_benchmarks"} or {"status": "error", "error": str}
    """
    table_doge = f"`{project}.{landing_dataset}.stg_doge`"
    table_out = f"`{project}.{marts_dataset}.taxonomy_utilization_benchmarks`"
    nppes = "bigquery-public-data.nppes.npi_raw"
    query = f"""
    CREATE OR REPLACE TABLE {table_out} AS
    WITH doge_base AS (
      SELECT
        TRIM(CAST(servicing_npi AS STRING)) AS servicing_npi,
        TRIM(CAST(COALESCE(state, 'FL') AS STRING)) AS state,
        SUM(COALESCE(claim_count, 0)) AS claim_count,
        SUM(COALESCE(total_paid, 0)) AS total_paid,
        SUM(COALESCE(beneficiary_count, 0)) AS beneficiary_count
      FROM {table_doge}
      WHERE servicing_npi IS NOT NULL
        AND TRIM(CAST(servicing_npi AS STRING)) != ''
        AND SUBSTR(SAFE_CAST(period_month AS STRING), 1, 4) = @period
        AND (state IS NULL OR UPPER(TRIM(CAST(state AS STRING))) = @state_filter)
      GROUP BY 1, 2
    ),
    npi_geo AS (
      SELECT
        TRIM(CAST(n.npi AS STRING)) AS npi,
        SUBSTR(REGEXP_REPLACE(COALESCE(n.provider_business_practice_location_address_postal_code, ''), r'[^0-9]', ''), 1, 5) AS zip5,
        UPPER(TRIM(COALESCE(n.provider_business_practice_location_address_state_name, ''))) AS nppes_state,
        TRIM(CAST(n.healthcare_provider_taxonomy_code_1 AS STRING)) AS taxonomy_code
      FROM `{nppes}` n
      WHERE n.healthcare_provider_taxonomy_code_1 IS NOT NULL
        AND TRIM(CAST(n.healthcare_provider_taxonomy_code_1 AS STRING)) != ''
    ),
    joined AS (
      SELECT d.servicing_npi, d.state, g.zip5, g.taxonomy_code, d.claim_count, d.total_paid, d.beneficiary_count
      FROM doge_base d
      INNER JOIN npi_geo g ON g.npi = d.servicing_npi
      WHERE d.beneficiary_count > 0
    ),
    by_zip AS (
      SELECT taxonomy_code, 'zip5' AS geography_type, zip5 AS geography_value, @period AS period,
        SUM(claim_count) AS claim_count, SUM(total_paid) AS total_revenue, SUM(beneficiary_count) AS member_count,
        SAFE_DIVIDE(SUM(claim_count), SUM(beneficiary_count)) AS claims_per_member,
        SAFE_DIVIDE(SUM(total_paid), SUM(beneficiary_count)) AS revenue_per_member,
        SAFE_DIVIDE(SUM(total_paid), NULLIF(SUM(claim_count), 0)) AS revenue_per_claim
      FROM joined WHERE LENGTH(zip5) = 5
      GROUP BY 1, 2, 3 HAVING SUM(beneficiary_count) >= 5
    ),
    by_state AS (
      SELECT taxonomy_code, 'state' AS geography_type, state AS geography_value, @period AS period,
        SUM(claim_count) AS claim_count, SUM(total_paid) AS total_revenue, SUM(beneficiary_count) AS member_count,
        SAFE_DIVIDE(SUM(claim_count), SUM(beneficiary_count)) AS claims_per_member,
        SAFE_DIVIDE(SUM(total_paid), SUM(beneficiary_count)) AS revenue_per_member,
        SAFE_DIVIDE(SUM(total_paid), NULLIF(SUM(claim_count), 0)) AS revenue_per_claim
      FROM joined WHERE state IS NOT NULL AND TRIM(state) != ''
      GROUP BY 1, 2, 3 HAVING SUM(beneficiary_count) >= 10
    ),
    by_national AS (
      SELECT taxonomy_code, 'national' AS geography_type, 'US' AS geography_value, @period AS period,
        SUM(claim_count) AS claim_count, SUM(total_paid) AS total_revenue, SUM(beneficiary_count) AS member_count,
        SAFE_DIVIDE(SUM(claim_count), SUM(beneficiary_count)) AS claims_per_member,
        SAFE_DIVIDE(SUM(total_paid), SUM(beneficiary_count)) AS revenue_per_member,
        SAFE_DIVIDE(SUM(total_paid), NULLIF(SUM(claim_count), 0)) AS revenue_per_claim
      FROM joined GROUP BY 1, 2, 3 HAVING SUM(beneficiary_count) >= 20
    )
    SELECT * FROM by_zip UNION ALL SELECT * FROM by_state UNION ALL SELECT * FROM by_national
    ORDER BY geography_type, geography_value, taxonomy_code
    """
    try:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        job_config = QueryJobConfig(query_parameters=[
            ScalarQueryParameter("period", "STRING", period),
            ScalarQueryParameter("state_filter", "STRING", state_filter),
        ])
        bq_client.query(query, job_config=job_config).result()
        return {"status": "ok", "table": table_out}
    except Exception as e:
        logger.warning("Populate benchmarks failed: %s", e)
        return {"status": "error", "error": str(e)}


def compute_org_benchmark(
    bq_client: Any,
    active_roster_npis: list[str],
    *,
    project: str,
    landing_dataset: str,
    period: str = "2024",
) -> dict[str, Any]:
    """
    Compute utilization metrics for active roster NPIs tied to this org.
    Queries DOGE for those servicing NPIs and aggregates.

    Returns:
        {
          "claims_per_member": float,
          "revenue_per_member": float,
          "revenue_per_claim": float,
          "claim_count": int,
          "total_paid": float,
          "member_count": int,
          "npi_count": int,
        }
        Or empty dict if no DOGE data.
    """
    if not active_roster_npis or not landing_dataset:
        return {}

    npis = list(dict.fromkeys(str(n).strip().zfill(10) for n in active_roster_npis if n))[:500]
    if not npis:
        return {}

    table = f"`{project}.{landing_dataset}.stg_doge`"
    in_list = ", ".join(f"'{n}'" for n in npis)
    query = f"""
    SELECT
      SUM(COALESCE(claim_count, 0)) AS claim_count,
      SUM(COALESCE(total_paid, 0)) AS total_paid,
      SUM(COALESCE(beneficiary_count, 0)) AS member_count
    FROM {table}
    WHERE TRIM(CAST(servicing_npi AS STRING)) IN ({in_list})
      AND SUBSTR(SAFE_CAST(period_month AS STRING), 1, 4) = @period
    """
    try:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        job_config = QueryJobConfig(query_parameters=[
            ScalarQueryParameter("period", "STRING", period),
        ])
        rows = list(bq_client.query(query, job_config=job_config).result())
    except Exception as e:
        logger.warning("Org benchmark query failed: %s", e)
        return {}

    if not rows:
        return {}

    r = rows[0]
    claim_count = int(r.get("claim_count") or 0)
    total_paid = float(r.get("total_paid") or 0)
    member_count = int(r.get("member_count") or 0)

    if member_count <= 0:
        return {
            "claims_per_member": 0.0,
            "revenue_per_member": 0.0,
            "revenue_per_claim": 0.0,
            "claim_count": claim_count,
            "total_paid": total_paid,
            "member_count": member_count,
            "npi_count": len(npis),
        }

    claims_per_member = claim_count / member_count
    revenue_per_member = total_paid / member_count
    revenue_per_claim = total_paid / claim_count if claim_count else 0.0

    return {
        "claims_per_member": round(claims_per_member, 2),
        "revenue_per_member": round(revenue_per_member, 2),
        "revenue_per_claim": round(revenue_per_claim, 2),
        "claim_count": claim_count,
        "total_paid": round(total_paid, 2),
        "member_count": member_count,
        "npi_count": len(npis),
    }


def fetch_benchmarks(
    bq_client: Any,
    taxonomy_codes: list[str],
    *,
    project: str,
    marts_dataset: str,
    period: str = "2024",
) -> dict[str, dict[str, Any]]:
    """
    Fetch benchmarks for given taxonomy codes from pre-populated table.

    Returns: {
      "zip5:{zip}": { "taxonomy_code" -> { claims_per_member, revenue_per_member, revenue_per_claim, ... } },
      "state:{state}": { ... },
      "national": { ... },
    }
    Or flat: keyed by (geography_type, geography_value, taxonomy_code).
    """
    if not taxonomy_codes or not marts_dataset:
        return {}

    table = f"`{project}.{marts_dataset}.taxonomy_utilization_benchmarks`"
    in_list = ", ".join(f"'{t}'" for t in taxonomy_codes[:100])
    query = f"""
    SELECT
      taxonomy_code,
      geography_type,
      geography_value,
      claims_per_member,
      revenue_per_member,
      revenue_per_claim,
      member_count,
      claim_count,
      total_revenue
    FROM {table}
    WHERE taxonomy_code IN ({in_list})
      AND (period = @period OR period IS NULL)
    """
    try:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        job_config = QueryJobConfig(query_parameters=[
            ScalarQueryParameter("period", "STRING", period),
        ])
        rows = list(bq_client.query(query, job_config=job_config).result())
    except Exception as e:
        logger.warning("Benchmarks fetch failed (table may not exist): %s", e)
        return {}

    out: dict[str, dict[str, dict[str, Any]]] = {}
    for r in rows:
        tax = str(r.get("taxonomy_code") or "").strip()
        geo_type = str(r.get("geography_type") or "").strip()
        geo_val = str(r.get("geography_value") or "").strip()
        key = f"{geo_type}:{geo_val}" if geo_val else geo_type
        if key not in out:
            out[key] = {}
        out[key][tax] = {
            "claims_per_member": float(r.get("claims_per_member") or 0),
            "revenue_per_member": float(r.get("revenue_per_member") or 0),
            "revenue_per_claim": float(r.get("revenue_per_claim") or 0),
            "member_count": int(r.get("member_count") or 0),
            "claim_count": int(r.get("claim_count") or 0),
            "total_revenue": float(r.get("total_revenue") or 0),
        }
    return out


def export_benchmarks_rows(
    bq_client: Any,
    *,
    project: str,
    marts_dataset: str,
    period: str = "2024",
    taxonomy_codes: list[str] | None = None,
    zip5_list: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Export taxonomy_utilization_benchmarks as flat rows for CSV.
    Optional filters: only taxonomies and ZIPs relevant to the client.
    - taxonomy_codes: restrict to these taxonomy codes (empty = all).
    - zip5_list: for zip5 geography, only include these ZIPs; state and national always included.
    """
    if not marts_dataset:
        return []
    table = f"`{project}.{marts_dataset}.taxonomy_utilization_benchmarks`"
    conditions = ["(period = @period OR period IS NULL)"]
    params: list[tuple[str, str, Any]] = [("period", "STRING", period)]

    if taxonomy_codes and len(taxonomy_codes) > 0:
        # BigQuery IN list: up to 100 taxonomies
        tax_clean = [str(t).strip() for t in taxonomy_codes[:100] if t]
        if tax_clean:
            placeholders = ", ".join(f"'{t}'" for t in tax_clean)
            conditions.append(f"taxonomy_code IN ({placeholders})")

    if zip5_list and len(zip5_list) > 0:
        zip_clean = [str(z).strip()[:5] for z in zip5_list if z and len(str(z).strip()[:5]) == 5][:500]
        if zip_clean:
            # Include: (geography_type = 'state' OR 'national') OR (geography_type = 'zip5' AND geography_value IN zips)
            zip_placeholders = ", ".join(f"'{z}'" for z in zip_clean)
            conditions.append(
                f"(geography_type IN ('state', 'national') OR (geography_type = 'zip5' AND geography_value IN ({zip_placeholders})))"
            )

    where_clause = " AND ".join(conditions)
    query = f"""
    SELECT
      taxonomy_code,
      geography_type,
      geography_value,
      period,
      claim_count,
      total_revenue,
      member_count,
      claims_per_member,
      revenue_per_member,
      revenue_per_claim
    FROM {table}
    WHERE {where_clause}
    ORDER BY geography_type, geography_value, taxonomy_code
    """
    try:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        job_config = QueryJobConfig(
            query_parameters=[ScalarQueryParameter(name, typ, val) for name, typ, val in params]
        )
        rows = list(bq_client.query(query, job_config=job_config).result())
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("Benchmarks export failed: %s", e)
        return []


def ensure_hcpcs_state_benchmarks_table(
    bq_client: Any,
    *,
    project: str,
    landing_dataset: str,
    marts_dataset: str,
    period: str = "2024",
    state_filter: str = "FL",
) -> dict[str, Any]:
    """
    Create hcpcs_state_benchmarks_fl in Python from stg_doge if it does not exist.
    Uses CREATE TABLE IF NOT EXISTS: first run creates and populates; subsequent runs skip creation.

    Returns: {"status": "ok", "table": "project.dataset.hcpcs_state_benchmarks_fl"} or {"status": "error", "error": str}
    """
    table_doge = f"`{project}.{landing_dataset}.stg_doge`"
    table_out = f"`{project}.{marts_dataset}.hcpcs_state_benchmarks_fl`"
    query = f"""
    CREATE TABLE IF NOT EXISTS {table_out} AS
    SELECT
      TRIM(CAST(hcpcs_code AS STRING)) AS hcpcs_code,
      SUM(COALESCE(claim_count, 0)) AS claim_count,
      SUM(COALESCE(total_paid, 0)) AS total_paid
    FROM {table_doge}
    WHERE hcpcs_code IS NOT NULL
      AND TRIM(CAST(hcpcs_code AS STRING)) != ''
      AND SUBSTR(SAFE_CAST(period_month AS STRING), 1, 4) = @period
      AND (state IS NULL OR UPPER(TRIM(CAST(state AS STRING))) = @state_filter)
    GROUP BY 1
    HAVING SUM(COALESCE(claim_count, 0)) >= 10
    ORDER BY 2 DESC
    """
    try:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        job_config = QueryJobConfig(query_parameters=[
            ScalarQueryParameter("period", "STRING", period),
            ScalarQueryParameter("state_filter", "STRING", state_filter),
        ])
        bq_client.query(query, job_config=job_config).result()
        return {"status": "ok", "table": f"{project}.{marts_dataset}.hcpcs_state_benchmarks_fl"}
    except Exception as e:
        logger.warning("Ensure HCPCS state benchmarks table failed: %s", e)
        return {"status": "error", "error": str(e)}


def fetch_hcpcs_state_benchmarks(
    bq_client: Any,
    *,
    project: str,
    landing_dataset: str,
    marts_dataset: str | None = None,
    period: str = "2024",
    state_filter: str = "FL",
) -> list[dict[str, Any]]:
    """
    Fetch HCPCS-level revenue_per_claim for FL/national comparison.
    Uses Python-created hcpcs_state_benchmarks_fl (built from stg_doge).
    Creates table if not exists on first run; subsequent runs only query.
    Returns rows: {hcpcs_code, claim_count, total_paid, revenue_per_claim}.
    """
    marts = marts_dataset or os.environ.get("BQ_MARTS_MEDICAID_DATASET", "mobius_medicaid_npi_dev")
    landing = landing_dataset or os.environ.get("BQ_LANDING_MEDICAID_DATASET", "landing_medicaid_npi_dev")
    # Ensure table exists (no-op if already created)
    ensure_hcpcs_state_benchmarks_table(
        bq_client,
        project=project,
        landing_dataset=landing,
        marts_dataset=marts,
        period=period,
        state_filter=state_filter,
    )
    table = f"`{project}.{marts}.hcpcs_state_benchmarks_fl`"
    query = f"""
    SELECT hcpcs_code, claim_count, total_paid
    FROM {table}
    ORDER BY claim_count DESC
    """
    try:
        rows = list(bq_client.query(query).result())
        out = []
        for r in rows:
            code = str(r.get("hcpcs_code") or "").strip()
            if not code:
                continue
            cc = int(r.get("claim_count") or 0)
            tp = float(r.get("total_paid") or 0)
            rpc = tp / cc if cc else 0.0
            out.append({
                "hcpcs_code": code,
                "claim_count": cc,
                "total_paid": round(tp, 2),
                "revenue_per_claim": round(rpc, 2),
            })
        return out
    except Exception as e:
        logger.warning("HCPCS state benchmarks query failed: %s", e)
        return []


def get_benchmark_for_npi(
    benchmarks: dict[str, dict[str, dict[str, Any]]],
    taxonomy_code: str,
    zip5: str = "",
    state: str = "FL",
    org_benchmark: dict[str, Any] | None = None,
) -> tuple[dict[str, float], str]:
    """
    Lookup benchmark for (taxonomy, location).
    Fallback order: org (this org's active roster) -> zip5 -> state -> national:US.

    org_benchmark: Optional dict from compute_org_benchmark (claims_per_member, revenue_per_member, revenue_per_claim).
    """
    state_clean = (state or "FL").strip().upper() or "FL"
    zip5_clean = (zip5 or "").strip()[:5]
    empty = {"claims_per_member": 0, "revenue_per_member": 0, "revenue_per_claim": 0}

    # 1. Org benchmark first (utilization for this org's active NPIs)
    if org_benchmark and (float(org_benchmark.get("revenue_per_member") or 0) > 0 or float(org_benchmark.get("revenue_per_claim") or 0) > 0):
        return (
            {
                "claims_per_member": float(org_benchmark.get("claims_per_member") or 0),
                "revenue_per_member": float(org_benchmark.get("revenue_per_member") or 0),
                "revenue_per_claim": float(org_benchmark.get("revenue_per_claim") or 0),
            },
            ORG_BENCHMARK_KEY,
        )

    # 2. Taxonomy benchmarks by geography
    for key in [
        f"zip5:{zip5_clean}" if zip5_clean else None,
        f"state:{state_clean}",
        "national:US",
    ]:
        if not key:
            continue
        if key in benchmarks and taxonomy_code in benchmarks[key]:
            b = benchmarks[key][taxonomy_code]
            return (
                {
                    "claims_per_member": b.get("claims_per_member", 0),
                    "revenue_per_member": b.get("revenue_per_member", 0),
                    "revenue_per_claim": b.get("revenue_per_claim", 0),
                },
                key,
            )
    return (empty, "none")
