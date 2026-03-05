"""
Provider Roster / Credentialing report core logic.
Pure data + report building; no HTTP. Used by CLI and API.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _location_id(org_npi: str, site_address_line_1: str, site_city: str, site_state: str, site_zip: str, site_zip9: str) -> str:
    """Stable location_id from org_npi + address."""
    raw = "|".join(
        str(x) if x is not None else ""
        for x in (org_npi, site_address_line_1, site_city, site_state, site_zip, site_zip9)
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def get_locations(
    bq_client: Any,
    org_name: str,
    project: str,
    marts_dataset: str,
) -> list[dict[str, Any]]:
    """
    Get distinct locations for org name from bh_roster.
    Returns list of dicts: org_npi, org_name, site_address_line_1, site_city, site_state, site_zip, site_zip9, location_id.
    """
    table = f"`{project}.{marts_dataset}.bh_roster`"
    query = f"""
    SELECT DISTINCT
      org_npi,
      org_name,
      site_address_line_1,
      site_city,
      site_state,
      site_zip,
      site_zip9
    FROM {table}
    WHERE LOWER(TRIM(COALESCE(org_name, ''))) LIKE LOWER(@org_pattern)
    ORDER BY org_npi, site_address_line_1, site_city, site_state
    """
    job_config = None
    try:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        job_config = QueryJobConfig(
            query_parameters=[ScalarQueryParameter("org_pattern", "STRING", f"%{org_name.strip()}%")]
        )
    except ImportError:
        pass
    rows = list(bq_client.query(query, job_config=job_config or {}).result())
    out = []
    for r in rows:
        loc_id = _location_id(
            r.get("org_npi") or "",
            r.get("site_address_line_1") or "",
            r.get("site_city") or "",
            r.get("site_state") or "",
            r.get("site_zip") or "",
            r.get("site_zip9") or "",
        )
        out.append({
            "org_npi": str(r.get("org_npi") or ""),
            "org_name": str(r.get("org_name") or ""),
            "site_address_line_1": str(r.get("site_address_line_1") or ""),
            "site_city": str(r.get("site_city") or ""),
            "site_state": str(r.get("site_state") or ""),
            "site_zip": str(r.get("site_zip") or ""),
            "site_zip9": str(r.get("site_zip9") or ""),
            "location_id": loc_id,
        })
    return out


def get_npis_per_location(
    bq_client: Any,
    org_name: str,
    location_ids: list[str] | None,
    project: str,
    marts_dataset: str,
    npi_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    For each location (optionally filtered by location_ids), get NPIs from bh_roster.
    npi_overrides: optional dict location_id -> { "add": [npi, ...], "remove": [npi, ...] }.
    Returns dict: location_id -> [ { servicing_npi, servicing_provider_name, provider_taxonomy_code, source_type, reconciliation } ].
    """
    table = f"`{project}.{marts_dataset}.bh_roster`"
    query = f"""
    SELECT
      org_npi,
      org_name,
      site_address_line_1,
      site_city,
      site_state,
      site_zip,
      servicing_npi,
      servicing_provider_name,
      provider_taxonomy_code,
      source_type
    FROM {table}
    WHERE LOWER(TRIM(COALESCE(org_name, ''))) LIKE LOWER(@org_pattern)
    ORDER BY org_npi, site_address_line_1, site_city, site_state, servicing_npi
    """
    try:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        job_config = QueryJobConfig(
            query_parameters=[ScalarQueryParameter("org_pattern", "STRING", f"%{org_name.strip()}%")]
        )
    except ImportError:
        job_config = None
    rows = list(bq_client.query(query, job_config=job_config or {}).result())
    npi_overrides = npi_overrides or {}

    # Group by location_id
    by_location: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        loc_id = _location_id(
            r.get("org_npi") or "",
            r.get("site_address_line_1") or "",
            r.get("site_city") or "",
            r.get("site_state") or "",
            r.get("site_zip") or "",
            r.get("site_zip9") or "",
        )
        if location_ids is not None and loc_id not in location_ids:
            continue
        if loc_id not in by_location:
            by_location[loc_id] = []
        npi_str = str(r.get("servicing_npi") or "")
        by_location[loc_id].append({
            "servicing_npi": npi_str,
            "servicing_provider_name": str(r.get("servicing_provider_name") or ""),
            "provider_taxonomy_code": str(r.get("provider_taxonomy_code") or ""),
            "source_type": str(r.get("source_type") or ""),
            "reconciliation": "system",
        })

    # Apply overrides: add / remove per location_id
    for loc_id, override in npi_overrides.items():
        if loc_id not in by_location:
            by_location[loc_id] = []
        add_list = [str(x).strip() for x in (override.get("add") or [])] if isinstance(override.get("add"), (list, tuple)) else []
        remove_set = {str(x).strip() for x in (override.get("remove") or [])} if isinstance(override.get("remove"), (list, tuple)) else set()
        for npi in remove_set:
            by_location[loc_id] = [x for x in by_location[loc_id] if x.get("servicing_npi") != npi]
        for npi in add_list:
            if npi and not any(x.get("servicing_npi") == npi for x in by_location[loc_id]):
                by_location[loc_id].append({
                    "servicing_npi": npi,
                    "servicing_provider_name": "",
                    "provider_taxonomy_code": "",
                    "source_type": "",
                    "reconciliation": "user_added",
                })

    return by_location


def get_readiness_and_combos(
    bq_client: Any,
    org_npis: set[str],
    servicing_npis: set[str],
    project: str,
    marts_dataset: str,
) -> list[dict[str, Any]]:
    """
    Get bh_roster_readiness rows filtered by (org_npi in org_npis, servicing_npi in servicing_npis).
    Returns list of readiness rows (check_1..4, readiness_status, etc.).
    """
    if not servicing_npis:
        return []
    table = f"`{project}.{marts_dataset}.bh_roster_readiness`"
    npis_list = ",".join(repr(str(n)) for n in list(servicing_npis)[:5000])
    query = f"""
    SELECT
      org_npi,
      org_name,
      site_address_line_1,
      site_city,
      site_state,
      site_zip,
      servicing_npi,
      servicing_provider_name,
      provider_taxonomy_code,
      servicing_zip9,
      check_1_npi_in_pml_pass,
      check_1_npi_in_pml_explanation,
      check_2_zip9_valid_pass,
      check_2_zip9_valid_explanation,
      check_3_taxonomy_permitted_pass,
      check_3_taxonomy_permitted_explanation,
      check_4_combo_medicaid_id_pass,
      check_4_combo_medicaid_id_explanation,
      readiness_all_pass,
      readiness_status,
      readiness_summary,
      confidence_score,
      total_claims_3yr,
      pml_credentialed_combos,
      suggested_action,
      suggested_taxonomies
    FROM {table}
    WHERE servicing_npi IN ({npis_list})
    ORDER BY org_npi, servicing_npi
    """
    rows = list(bq_client.query(query).result())
    out = []
    for r in rows:
        if org_npis and str(r.get("org_npi") or "").strip() not in org_npis:
            continue
        out.append({k: r[k] for k in r.keys()})
    return out


def get_ghost_billing(
    bq_client: Any,
    org_npis: set[str],
    reportable_servicing_npis: set[str],
    project: str,
    marts_dataset: str,
    months_lookback: int = 12,
) -> list[dict[str, Any]]:
    """
    Ghost billing = servicing NPIs that bill under the org but have weak address/roster match (low confidence).
    Uses ghost_billing_fl (dbt) — rows where confidence_score < 40 and claims in last 12 months.
    """
    if not org_npis:
        return []
    table = f"`{project}.{marts_dataset}.ghost_billing_fl`"
    org_list = ",".join(repr(str(x)) for x in list(org_npis)[:500])
    query = f"""
    SELECT
      billing_npi,
      servicing_npi,
      claim_count,
      total_paid,
      confidence_score
    FROM {table}
    WHERE billing_npi IN ({org_list})
    ORDER BY total_paid DESC
    """
    try:
        rows = list(bq_client.query(query).result())
    except Exception as e:
        logger.warning("get_ghost_billing query failed (check ghost_billing_fl; run dbt for bh_roster): %s", e)
        return []
    return [
        {
            "billing_npi": str(r.get("billing_npi") or ""),
            "servicing_npi": str(r.get("servicing_npi") or "").strip(),
            "claim_count": int(r.get("claim_count") or 0),
            "total_paid": float(r.get("total_paid") or 0),
        }
        for r in rows
    ]


def get_billing_run_rate_by_taxonomy_location(
    bq_client: Any,
    org_npis: set[str],
    project: str,
    marts_dataset: str,
    landing_dataset: str,
    year: int = 2024,
) -> list[dict[str, Any]]:
    """
    DOGE billing run rate per (taxonomy, location): total 2024 paid and physician count
    for each (provider_taxonomy_code, org_npi, site_city, site_state, site_zip) from
    bh_roster_readiness, using stg_doge for the org's billing. Run rate = total_paid_2024 / physician_count.
    """
    if not org_npis:
        return []
    table_readiness = f"`{project}.{marts_dataset}.bh_roster_readiness`"
    table_doge = f"`{project}.{landing_dataset}.stg_doge`"
    org_list = ",".join(repr(str(x)) for x in list(org_npis)[:500])
    year_str = str(year)
    query = f"""
    WITH doge_yr AS (
      SELECT
        billing_npi,
        servicing_npi,
        SUM(COALESCE(total_paid, 0)) AS total_paid
      FROM {table_doge}
      WHERE billing_npi IN ({org_list})
        AND servicing_npi IS NOT NULL AND TRIM(servicing_npi) != ''
        AND SUBSTR(SAFE_CAST(period_month AS STRING), 1, 4) = @year
      GROUP BY billing_npi, servicing_npi
    ),
    roster_cell AS (
      SELECT
        provider_taxonomy_code,
        org_npi,
        site_city,
        site_state,
        site_zip,
        servicing_npi
      FROM {table_readiness}
      WHERE org_npi IN ({org_list})
        AND provider_taxonomy_code IS NOT NULL AND TRIM(CAST(provider_taxonomy_code AS STRING)) != ''
    ),
    cell_npi_paid AS (
      SELECT
        r.provider_taxonomy_code,
        r.org_npi,
        r.site_city,
        r.site_state,
        r.site_zip,
        r.servicing_npi,
        COALESCE(SUM(d.total_paid), 0) AS npi_paid
      FROM roster_cell r
      LEFT JOIN doge_yr d ON r.servicing_npi = d.servicing_npi AND r.org_npi = d.billing_npi
      GROUP BY r.provider_taxonomy_code, r.org_npi, r.site_city, r.site_state, r.site_zip, r.servicing_npi
    )
    SELECT
      provider_taxonomy_code,
      org_npi,
      site_city,
      site_state,
      site_zip,
      SUM(npi_paid) AS total_paid_2024,
      COUNT(DISTINCT servicing_npi) AS physician_count
    FROM cell_npi_paid
    GROUP BY provider_taxonomy_code, org_npi, site_city, site_state, site_zip
    HAVING COUNT(DISTINCT servicing_npi) > 0
    ORDER BY total_paid_2024 DESC
    """
    try:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        job_config = QueryJobConfig(
            query_parameters=[ScalarQueryParameter("year", "STRING", year_str)]
        )
        rows = list(bq_client.query(query, job_config=job_config).result())
    except Exception as e:
        logger.warning("get_billing_run_rate_by_taxonomy_location failed: %s", e)
        return []
    out = []
    for r in rows:
        pc = int(r.get("physician_count") or 0)
        total = float(r.get("total_paid_2024") or 0)
        run_rate = total / pc if pc else 0.0
        out.append({
            "provider_taxonomy_code": str(r.get("provider_taxonomy_code") or ""),
            "org_npi": str(r.get("org_npi") or ""),
            "site_city": str(r.get("site_city") or ""),
            "site_state": str(r.get("site_state") or ""),
            "site_zip": str(r.get("site_zip") or ""),
            "total_paid_2024": total,
            "physician_count": pc,
            "run_rate_per_physician": round(run_rate, 2),
        })
    return out


def build_executive_summary(
    org_name: str,
    locations: list[dict[str, Any]],
    npis_per_location: dict[str, list[dict[str, Any]]],
    readiness_rows: list[dict[str, Any]],
    invalid_combos: list[dict[str, Any]],
    missed_opportunities: list[dict[str, Any]],
    ghost_billing: list[dict[str, Any]],
    run_rate_by_taxonomy_location: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build executive summary dict: org_name, org_npis, counts, readiness_status_breakdown, next_steps, revenue_at_risk_2024."""
    org_npis = {loc["org_npi"] for loc in locations if loc.get("org_npi")}
    all_npis = set()
    for nlist in npis_per_location.values():
        for n in nlist:
            all_npis.add(n.get("servicing_npi") or "")
    all_npis.discard("")
    ready_npis = {r["servicing_npi"] for r in readiness_rows if r.get("readiness_all_pass") is True}
    fail_npis = all_npis - ready_npis
    status_counts: dict[str, int] = {}
    for r in readiness_rows:
        s = r.get("readiness_status") or "Needs review"
        status_counts[s] = status_counts.get(s, 0) + 1
    ghost_claims = sum(g.get("claim_count") or 0 for g in ghost_billing)
    ghost_paid = sum(g.get("total_paid") or 0 for g in ghost_billing)
    locs_no_ready = [
        loc_id for loc_id, nlist in npis_per_location.items()
        if nlist and not any(
            (n.get("servicing_npi") or "") in ready_npis
            for n in nlist
        )
    ]
    next_steps = []
    if locs_no_ready:
        next_steps.append(f"{len(locs_no_ready)} location(s) with no ready NPI.")
    if invalid_combos:
        next_steps.append(f"{len(invalid_combos)} invalid combo(s) need resolution.")
    if ghost_billing:
        next_steps.append(f"{len(ghost_billing)} ghost billing NPI(s) ({ghost_claims} claims, ${ghost_paid:,.0f}).")

    # Revenue at risk: run rate per (taxonomy, location) × distinct NPIs with invalid combo in that cell (2024 basis)
    revenue_at_risk_2024: float = 0.0
    if run_rate_by_taxonomy_location and invalid_combos:
        key_to_run_rate: dict[tuple[str, ...], float] = {}
        for row in run_rate_by_taxonomy_location:
            key = (
                str(row.get("provider_taxonomy_code") or "").strip(),
                str(row.get("org_npi") or "").strip(),
                str(row.get("site_city") or "").strip(),
                str(row.get("site_state") or "").strip(),
                str(row.get("site_zip") or "").strip(),
            )
            key_to_run_rate[key] = float(row.get("run_rate_per_physician") or 0)
        from collections import defaultdict
        cell_to_npis: dict[tuple[str, ...], set[str]] = defaultdict(set)
        for r in invalid_combos:
            key = (
                str(r.get("provider_taxonomy_code") or "").strip(),
                str(r.get("org_npi") or "").strip(),
                str(r.get("site_city") or "").strip(),
                str(r.get("site_state") or "").strip(),
                str(r.get("site_zip") or "").strip(),
            )
            npi = str(r.get("servicing_npi") or "").strip()
            if npi:
                cell_to_npis[key].add(npi)
        for key, npis in cell_to_npis.items():
            run_rate = key_to_run_rate.get(key, 0.0)
            revenue_at_risk_2024 += len(npis) * run_rate

        # Revenue at risk by readiness status (each NPI in a cell counted once, attributed to one status)
        revenue_by_status: dict[str, float] = {}
        # Revenue at risk by confidence (high >=70, medium 40-69, low <40 or missing)
        revenue_by_confidence: dict[str, float] = {"high": 0.0, "medium": 0.0, "low": 0.0}
        seen_key_npi: set[tuple[tuple[str, ...], str]] = set()
        for r in invalid_combos:
            k = (
                str(r.get("provider_taxonomy_code") or "").strip(),
                str(r.get("org_npi") or "").strip(),
                str(r.get("site_city") or "").strip(),
                str(r.get("site_state") or "").strip(),
                str(r.get("site_zip") or "").strip(),
            )
            npi = str(r.get("servicing_npi") or "").strip()
            status = str(r.get("readiness_status") or "Needs review").strip()
            if not npi or (k, npi) in seen_key_npi:
                continue
            seen_key_npi.add((k, npi))
            rate = key_to_run_rate.get(k, 0.0)
            revenue_by_status[status] = revenue_by_status.get(status, 0.0) + rate
            score = r.get("confidence_score")
            if score is not None and score >= 70:
                conf = "high"
            elif score is not None and score >= 40:
                conf = "medium"
            else:
                conf = "low"
            revenue_by_confidence[conf] = revenue_by_confidence.get(conf, 0.0) + rate
        revenue_at_risk_2024_by_status = {s: round(v, 2) for s, v in revenue_by_status.items()}
        revenue_at_risk_2024_by_confidence = {c: round(v, 2) for c, v in revenue_by_confidence.items()}
    else:
        revenue_at_risk_2024_by_status = {}
        revenue_at_risk_2024_by_confidence = {}

    # Confidence breakdown for invalid combos (roster match confidence: high >=70, medium 40-69, low <40 or missing)
    confidence_high = sum(1 for r in invalid_combos if (r.get("confidence_score") or 0) >= 70)
    confidence_medium = sum(1 for r in invalid_combos if 40 <= (r.get("confidence_score") or 0) < 70)
    confidence_low = sum(1 for r in invalid_combos if (r.get("confidence_score") or 0) < 40 or r.get("confidence_score") is None)
    confidence_breakdown = {"high": confidence_high, "medium": confidence_medium, "low": confidence_low}

    # Overall readiness score (0-100): share of combinations that are ready
    total_combos = len(invalid_combos) + len([r for r in readiness_rows if r.get("readiness_all_pass")])
    ready_count = len([r for r in readiness_rows if r.get("readiness_all_pass")])
    readiness_score = round(100.0 * ready_count / total_combos, 0) if total_combos else 0

    # Conservative estimate: if 20% of missed opportunities are activatable at avg run rate of invalid combos
    estimated_missed_opportunities_revenue_20pct: float | None = None
    if revenue_at_risk_2024 and invalid_combos and missed_opportunities:
        avg_per_invalid = revenue_at_risk_2024 / len(invalid_combos)
        estimated_missed_opportunities_revenue_20pct = round(
            avg_per_invalid * 0.2 * len(missed_opportunities), 2
        )

    # Worked example: one NPI/taxonomy/location showing how run rate → annual estimate
    worked_example: dict[str, Any] | None = None
    if run_rate_by_taxonomy_location and invalid_combos:
        key_to_run_rate: dict[tuple[str, ...], float] = {}
        for row in run_rate_by_taxonomy_location:
            key = (
                str(row.get("provider_taxonomy_code") or "").strip(),
                str(row.get("org_npi") or "").strip(),
                str(row.get("site_city") or "").strip(),
                str(row.get("site_state") or "").strip(),
                str(row.get("site_zip") or "").strip(),
            )
            key_to_run_rate[key] = float(row.get("run_rate_per_physician") or 0)
        for r in invalid_combos[:20]:
            k = (
                str(r.get("provider_taxonomy_code") or "").strip(),
                str(r.get("org_npi") or "").strip(),
                str(r.get("site_city") or "").strip(),
                str(r.get("site_state") or "").strip(),
                str(r.get("site_zip") or "").strip(),
            )
            rate = key_to_run_rate.get(k, 0.0)
            if rate > 0:
                worked_example = {
                    "servicing_npi": r.get("servicing_npi"),
                    "servicing_provider_name": r.get("servicing_provider_name") or "(unnamed)",
                    "provider_taxonomy_code": r.get("provider_taxonomy_code"),
                    "site_city": r.get("site_city"),
                    "site_state": r.get("site_state"),
                    "site_zip": r.get("site_zip"),
                    "run_rate_per_physician": round(rate, 2),
                    "annual_estimate": round(rate, 2),
                    "explanation": "Annual Medicaid billing run rate for this (taxonomy × location) cell from 2024 DOGE claims; applied to this provider.",
                }
                break

    result = {
        "org_name": org_name,
        "org_npis": list(org_npis),
        "methodology_overview": "Locations from roster; NPIs per location with reconciliation; four Medicaid NPI checks per NPI and per (NPI, taxonomy, ZIP9) combo; invalid combos, missed opportunities, ghost billing (DOGE).",
        "location_count": len(locations),
        "total_npis": len(all_npis),
        "npis_all_checks_pass": len(ready_npis),
        "npis_at_least_one_fail": len(fail_npis),
        "invalid_combo_count": len(invalid_combos),
        "ghost_billing_claim_count": ghost_claims,
        "ghost_billing_total_paid": ghost_paid,
        "ghost_billing_npi_count": len(ghost_billing),
        "readiness_status_breakdown": status_counts,
        "next_steps": "; ".join(next_steps) if next_steps else "No critical issues.",
        "revenue_at_risk_2024": round(revenue_at_risk_2024, 2),
        "billing_impact_note": "Based on 2024 DOGE billing run rate per physician by taxonomy and location; applies run rate to distinct providers with invalid combos in each taxonomy-location cell." if revenue_at_risk_2024 else None,
        "revenue_at_risk_2024_by_status": revenue_at_risk_2024_by_status if revenue_at_risk_2024 else {},
        "revenue_at_risk_2024_by_confidence": revenue_at_risk_2024_by_confidence if revenue_at_risk_2024 else {},
        "confidence_breakdown": confidence_breakdown,
        "readiness_score": int(readiness_score),
        "estimated_missed_opportunities_revenue_20pct": estimated_missed_opportunities_revenue_20pct,
        "worked_example": worked_example,
    }
    return result


def build_full_report(
    bq_client: Any,
    org_name: str,
    project: str,
    marts_dataset: str,
    landing_dataset: str,
    location_ids: list[str] | None = None,
    npi_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Build full Provider Roster / Credentialing report.
    Returns dict: executive_summary, locations, npis_per_location, per_npi_validation, combos, invalid_combos, missed_opportunities, ghost_billing.
    """
    locations = get_locations(bq_client, org_name, project, marts_dataset)
    if not locations:
        return {
            "executive_summary": {"org_name": org_name, "error": "No locations found for this org name."},
            "locations": [],
            "npis_per_location": {},
            "per_npi_validation": [],
            "combos": [],
            "invalid_combos": [],
            "missed_opportunities": [],
            "ghost_billing": [],
        }
    if location_ids is not None:
        locations = [loc for loc in locations if loc["location_id"] in location_ids]
    npis_per_location = get_npis_per_location(
        bq_client, org_name, location_ids, project, marts_dataset, npi_overrides
    )
    org_npis = {loc["org_npi"] for loc in locations}
    all_servicing = set()
    for nlist in npis_per_location.values():
        for n in nlist:
            all_servicing.add(n.get("servicing_npi") or "")
    all_servicing.discard("")
    readiness_rows = get_readiness_and_combos(bq_client, org_npis, all_servicing, project, marts_dataset)
    run_rate_by_taxonomy_location = get_billing_run_rate_by_taxonomy_location(
        bq_client, org_npis, project, marts_dataset, landing_dataset, year=2024
    )
    ghost_billing = get_ghost_billing(
        bq_client, org_npis, all_servicing, project, marts_dataset
    )
    invalid_combos = [r for r in readiness_rows if not r.get("readiness_all_pass")]
    ready_npis = {r["servicing_npi"] for r in readiness_rows if r.get("readiness_all_pass")}
    missed_opportunities = []
    for loc_id, nlist in npis_per_location.items():
        if nlist and not any((n.get("servicing_npi") or "") in ready_npis for n in nlist):
            missed_opportunities.append({"type": "location_no_ready_npi", "location_id": loc_id})
    for r in readiness_rows:
        if r.get("check_1_npi_in_pml_pass") and not r.get("check_4_combo_medicaid_id_pass"):
            missed_opportunities.append({
                "type": "npi_in_pml_but_combo_fail",
                "servicing_npi": r.get("servicing_npi"),
                "servicing_provider_name": r.get("servicing_provider_name"),
            })
    executive = build_executive_summary(
        org_name, locations, npis_per_location, readiness_rows,
        invalid_combos, missed_opportunities, ghost_billing,
        run_rate_by_taxonomy_location=run_rate_by_taxonomy_location,
    )
    per_npi_validation = []
    seen_npis: set[str] = set()
    for r in readiness_rows:
        npi = r.get("servicing_npi") or ""
        if npi in seen_npis:
            continue
        seen_npis.add(npi)
        per_npi_validation.append({
            "servicing_npi": npi,
            "servicing_provider_name": r.get("servicing_provider_name"),
            "valid_address_pml": bool(r.get("check_1_npi_in_pml_pass") or r.get("check_4_combo_medicaid_id_pass")),
            "valid_zip": bool(r.get("check_2_zip9_valid_pass")),
            "valid_medicaid_id": bool(r.get("check_1_npi_in_pml_pass") and r.get("check_4_combo_medicaid_id_pass")),
            "valid_taxonomy": bool(r.get("check_3_taxonomy_permitted_pass")),
            "readiness_status": r.get("readiness_status"),
            "readiness_summary": r.get("readiness_summary"),
        })
    return {
        "executive_summary": executive,
        "locations": locations,
        "npis_per_location": {k: v for k, v in npis_per_location.items()},
        "per_npi_validation": per_npi_validation,
        "combos": readiness_rows,
        "invalid_combos": invalid_combos,
        "missed_opportunities": missed_opportunities,
        "ghost_billing": ghost_billing,
    }
