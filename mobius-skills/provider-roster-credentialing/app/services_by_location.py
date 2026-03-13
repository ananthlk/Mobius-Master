"""
Step 5: Services offered by location.

For each location: distinct taxonomies across providers (NPPES all 15 slots + PML),
deduplicated, with descriptions and Medicaid approval (TML).

Uses landing/source tables directly — no dbt marts.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_NPPES_TAX_COLS = [
    "healthcare_provider_taxonomy_code_1",
    "healthcare_provider_taxonomy_code_2",
    "healthcare_provider_taxonomy_code_3",
    "healthcare_provider_taxonomy_code_4",
    "healthcare_provider_taxonomy_code_5",
    "healthcare_provider_taxonomy_code_6",
    "healthcare_provider_taxonomy_code_7",
    "healthcare_provider_taxonomy_code_8",
    "healthcare_provider_taxonomy_code_9",
    "healthcare_provider_taxonomy_code_10",
    "healthcare_provider_taxonomy_code_11",
    "healthcare_provider_taxonomy_code_12",
    "healthcare_provider_taxonomy_code_13",
    "healthcare_provider_taxonomy_code_14",
    "healthcare_provider_taxonomy_code_15",
]


def _job_config(params: list[tuple[str, str, Any]]) -> Any:
    from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
    return QueryJobConfig(
        query_parameters=[ScalarQueryParameter(name, typ, val) for name, typ, val in params]
    )


def _fetch_nppes_taxonomies(
    client: Any,
    npis: list[str],
    project: str,
) -> dict[str, set[str]]:
    """Fetch all 15 taxonomy codes per NPI from NPPES. Returns npi -> set of taxonomy codes."""
    if not npis:
        return {}
    npis_clean = [str(n).strip().zfill(10) for n in npis if n][:500]
    if not npis_clean:
        return {}

    cols = ", ".join(f"TRIM(CAST({c} AS STRING)) AS {c}" for c in _NPPES_TAX_COLS)
    in_list = ", ".join(f"'{n}'" for n in npis_clean)
    query = f"""
    SELECT
      CAST(npi AS STRING) AS npi,
      {cols}
    FROM `bigquery-public-data.nppes.npi_raw` n
    WHERE TRIM(CAST(npi AS STRING)) IN ({in_list})
    """
    try:
        rows = list(client.query(query).result())
    except Exception as e:
        logger.warning("NPPES taxonomy fetch failed: %s", e)
        return {}

    out: dict[str, set[str]] = {}
    for r in rows:
        npi = str(r.get("npi", "")).strip()
        if not npi:
            continue
        codes: set[str] = set()
        for c in _NPPES_TAX_COLS:
            v = r.get(c)
            if v is not None and str(v).strip():
                codes.add(str(v).strip())
        if codes:
            out.setdefault(npi, set()).update(codes)
    return out


def _fetch_pml_taxonomies(
    client: Any,
    npis: list[str],
    project: str,
    landing_dataset: str,
    state_filter: str = "FL",
) -> dict[str, set[str]]:
    """Fetch taxonomy codes from PML for given NPIs."""
    if not npis or not landing_dataset:
        return {}
    npis_clean = [str(n).strip().zfill(10) for n in npis if n][:500]
    if not npis_clean:
        return {}

    table = f"`{project}.{landing_dataset}.stg_pml`"
    sf = (state_filter or "FL").strip().upper()[:2]
    state_cond = "UPPER(TRIM(COALESCE(program_state, state, ''))) IN ('FL','FLORIDA')" if sf in ("FL", "FLORIDA") else f"UPPER(TRIM(COALESCE(program_state, state, ''))) = '{sf}'"
    in_list = ", ".join(f"'{n}'" for n in npis_clean)
    query = f"""
    SELECT
      TRIM(CAST(npi AS STRING)) AS npi,
      TRIM(CAST(taxonomy_code AS STRING)) AS taxonomy_code
    FROM {table}
    WHERE TRIM(CAST(npi AS STRING)) IN ({in_list})
      AND taxonomy_code IS NOT NULL
      AND TRIM(CAST(taxonomy_code AS STRING)) != ''
      AND ({state_cond})
    """
    try:
        rows = list(client.query(query).result())
    except Exception as e:
        logger.warning("PML taxonomy fetch failed: %s", e)
        return {}

    out: dict[str, set[str]] = {}
    for r in rows:
        npi = str(r.get("npi", "")).strip()
        code = str(r.get("taxonomy_code", "")).strip()
        if npi and code:
            out.setdefault(npi, set()).add(code)
    return out


def _fetch_tml_codes(
    client: Any,
    project: str,
    landing_dataset: str,
    state_filter: str = "FL",
) -> set[str]:
    """Fetch FL Medicaid approved taxonomy codes from TML (landing table)."""
    if not landing_dataset:
        return set()
    table = f"`{project}.{landing_dataset}.stg_tml`"
    try:
        query = f"""
        SELECT DISTINCT TRIM(CAST(taxonomy_code AS STRING)) AS taxonomy_code
        FROM {table}
        WHERE taxonomy_code IS NOT NULL AND TRIM(CAST(taxonomy_code AS STRING)) != ''
        """
        rows = list(client.query(query).result())
        return {str(r.get("taxonomy_code", "")).strip() for r in rows if r.get("taxonomy_code")}
    except Exception as e:
        logger.warning("TML fetch failed (table may not exist): %s", e)
        return set()


def _fetch_nucc_descriptions(
    client: Any,
    codes: list[str],
    project: str,
    landing_dataset: str,
) -> dict[str, str]:
    """Fetch taxonomy code -> description from NUCC. Uses Code/Definition or taxonomy_code/taxonomy_description."""
    if not codes or not landing_dataset:
        return {}
    codes_clean = list(dict.fromkeys(c for c in codes if c))[:500]
    if not codes_clean:
        return {}

    table = f"`{project}.{landing_dataset}.stg_nucc_taxonomy`"
    in_list = ", ".join(f"'{c.replace(chr(39), chr(39)+chr(39))}'" for c in codes_clean)
    try:
        query = f"""
        SELECT TRIM(CAST(taxonomy_code AS STRING)) AS taxonomy_code,
               TRIM(CAST(taxonomy_description AS STRING)) AS taxonomy_description
        FROM {table}
        WHERE taxonomy_code IN ({in_list})
        """
        rows = list(client.query(query).result())
        return {str(r.get("taxonomy_code", "")): str(r.get("taxonomy_description", "")) for r in rows}
    except Exception as e:
        logger.warning("NUCC fetch failed: %s", e)
        return {}


def find_services_by_location(
    bq_client: Any,
    locations: list[dict[str, Any]],
    associated_providers: dict[str, list[dict[str, Any]]],
    *,
    project: str,
    landing_dataset: str | None,
    state_filter: str = "FL",
    taxonomy_labels_fallback: dict[str, str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Step 5: For each location, distinct taxonomies (NPPES all 15 + PML), descriptions, Medicaid approved.

    Args:
        bq_client: BigQuery client
        locations: List of {location_id, site_address_line_1, site_city, site_state, site_zip5, ...}
        associated_providers: location_id -> [{npi, name, entity_type, ...}]
        project: BQ project
        landing_dataset: Landing dataset for PML, TML, NUCC (None = skip PML/TML/NUCC)
        state_filter: State for TML filter (default FL)
        taxonomy_labels_fallback: Code -> description when NUCC unavailable

    Returns:
        location_id -> [{
            taxonomy_code, taxonomy_description, medicaid_approved,
            location_address (summary string)
        }]
    """
    # Collect all NPIs and build location_id -> [npi]
    loc_npis: dict[str, list[str]] = {}
    all_npis: set[str] = set()
    loc_summary: dict[str, str] = {}
    for loc in locations:
        loc_id = loc.get("location_id", "")
        if not loc_id:
            continue
        addr = loc.get("site_address_line_1") or loc.get("site_address", "")
        city = loc.get("site_city", "")
        state = loc.get("site_state", "")
        zip5 = loc.get("site_zip5") or loc.get("site_zip", "")
        loc_summary[loc_id] = f"{addr}, {city}, {state} {zip5}".strip(", ")
        providers = associated_providers.get(loc_id, [])
        npis = []
        for p in providers:
            n = (p.get("npi") or p.get("servicing_npi") or "").strip()
            if n:
                npis.append(n)
                all_npis.add(n)
        if npis:
            loc_npis[loc_id] = npis

    if not loc_npis or not all_npis:
        return {loc_id: [] for loc_id in loc_summary}

    npis_list = list(all_npis)

    # Fetch taxonomies from NPPES and PML
    nppes_tax = _fetch_nppes_taxonomies(bq_client, npis_list, project)
    pml_tax: dict[str, set[str]] = {}
    if landing_dataset:
        pml_tax = _fetch_pml_taxonomies(bq_client, npis_list, project, landing_dataset, state_filter)

    # TML and NUCC
    tml_codes = _fetch_tml_codes(bq_client, project, landing_dataset or "", state_filter) if landing_dataset else set()
    all_codes: set[str] = set()
    for npi, codes in nppes_tax.items():
        all_codes.update(codes)
    for npi, codes in pml_tax.items():
        all_codes.update(codes)
    nucc_desc = _fetch_nucc_descriptions(bq_client, list(all_codes), project, landing_dataset or "") if landing_dataset else {}
    fallback = taxonomy_labels_fallback or {}

    # Build per-location output
    out: dict[str, list[dict[str, Any]]] = {}
    for loc_id, npis in loc_npis.items():
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for npi in npis:
            codes = nppes_tax.get(npi, set()) | pml_tax.get(npi, set())
            for code in codes:
                if not code or code in seen:
                    continue
                seen.add(code)
                desc = nucc_desc.get(code) or fallback.get(code) or code
                approved = code in tml_codes
                rows.append({
                    "taxonomy_code": code,
                    "taxonomy_description": desc,
                    "medicaid_approved": approved,
                })
        rows.sort(key=lambda x: (not x["medicaid_approved"], x["taxonomy_code"]))
        out[loc_id] = [
            {
                **r,
                "location_address": loc_summary.get(loc_id, ""),
            }
            for r in rows
        ]
    # Locations with no providers
    for loc_id in loc_summary:
        if loc_id not in out:
            out[loc_id] = []
    return out
