"""
Step 2: Identify all practice locations for an organization.

Given org NPIs (from Step 1 find-org), returns:
(a) Sites identified when identifying the org (initial_sites)
(b) Distinct locations from DOGE: where billing_npi IN org_npis → servicing_npis → addresses from NPPES/PML

All in Python (no dbt). Direct BigQuery to landing stg_doge, NPPES, PML.
Ready for MCP exposure.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _get_project() -> str:
    import os
    return os.environ.get("BQ_PROJECT", "mobius-os-dev")


def _get_landing_dataset() -> str | None:
    import os
    return os.environ.get("BQ_LANDING_MEDICAID_DATASET") or None


def _location_id(site_address_line_1: str, site_city: str, site_state: str, site_zip: str) -> str:
    raw = "|".join(
        str(x) if x is not None else ""
        for x in (site_address_line_1, site_city, site_state, site_zip)
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _job_config(params: list[tuple[str, str, Any]]) -> Any:
    from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
    return QueryJobConfig(
        query_parameters=[ScalarQueryParameter(name, typ, val) for name, typ, val in params]
    )


def _servicing_npis_from_doge(
    client: Any,
    org_npis: list[str],
    *,
    project: str,
    landing_dataset: str,
    period_from: str = "202202",
) -> list[str]:
    """Get distinct servicing_npi from DOGE where billing_npi IN org_npis."""
    if not org_npis or not landing_dataset:
        return []
    # Normalize NPIs (10 digits, strip)
    npis = [str(n).strip().lstrip("0") or "0" for n in org_npis]
    npis = [n if len(n) == 10 else n.zfill(10) for n in npis if n and n != "0"]
    if not npis:
        return []

    table = f"`{project}.{landing_dataset}.stg_doge`"
    # DOGE may have billing_npi/servicing_npi or alternate columns
    in_list = ", ".join(f"'{n}'" for n in npis[:100])  # cap
    query = f"""
    SELECT DISTINCT TRIM(CAST(servicing_npi AS STRING)) AS servicing_npi
    FROM {table}
    WHERE TRIM(CAST(billing_npi AS STRING)) IN ({in_list})
      AND servicing_npi IS NOT NULL
      AND TRIM(CAST(servicing_npi AS STRING)) != ''
      AND SUBSTR(SAFE_CAST(period_month AS STRING), 1, 6) >= @period_from
    """
    try:
        job_config = _job_config([("period_from", "STRING", period_from)])
        rows = list(client.query(query, job_config=job_config).result())
        return [str(r.servicing_npi).strip() for r in rows if r.servicing_npi]
    except Exception as e:
        logger.warning("DOGE servicing NPIs query failed (billing_npi/servicing_npi columns?): %s", e)
        return []


def _addresses_from_nppes(client: Any, npis: list[str], project: str) -> list[dict]:
    """Get practice addresses from NPPES for given NPIs. Entity type 2 = org, 1 = individual."""
    if not npis:
        return []
    npis_clean = [str(n).strip() for n in npis if n][:500]
    if not npis_clean:
        return []

    placeholders = ", ".join(f"'{n}'" for n in npis_clean)
    name_expr = "CASE WHEN CAST(n.entity_type_code AS STRING) = '2' THEN COALESCE(n.provider_organization_name_legal_business_name,'') ELSE TRIM(CONCAT(COALESCE(n.provider_last_name_legal_name,''), ', ', COALESCE(n.provider_first_name,''))) END"
    entity_expr = "CASE WHEN CAST(n.entity_type_code AS STRING) = '2' THEN 'organization' ELSE 'individual' END"

    query = f"""
    SELECT
      CAST(n.npi AS STRING) AS npi,
      TRIM({name_expr}) AS name,
      {entity_expr} AS entity_type,
      TRIM(COALESCE(n.provider_first_line_business_practice_location_address,'')) AS address_line_1,
      TRIM(COALESCE(n.provider_business_practice_location_address_city_name,'')) AS city,
      TRIM(COALESCE(n.provider_business_practice_location_address_state_name,'')) AS state,
      SUBSTR(REGEXP_REPLACE(COALESCE(n.provider_business_practice_location_address_postal_code,''), r'[^0-9]', ''), 1, 5) AS zip5,
      SUBSTR(REGEXP_REPLACE(COALESCE(n.provider_business_practice_location_address_postal_code,''), r'[^0-9]', ''), 1, 9) AS zip9
    FROM `bigquery-public-data.nppes.npi_raw` n
    WHERE CAST(n.npi AS STRING) IN ({placeholders})
      AND (TRIM(COALESCE(n.provider_first_line_business_practice_location_address,'')) != ''
           OR TRIM(COALESCE(n.provider_business_practice_location_address_city_name,'')) != '')
    """
    try:
        rows = list(client.query(query).result())
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("NPPES addresses query failed: %s", e)
        return []


def _addresses_from_pml(
    client: Any,
    npis: list[str],
    project: str,
    landing_dataset: str,
) -> list[dict]:
    """Get addresses from PML for given NPIs."""
    if not npis or not landing_dataset:
        return []
    npis_clean = [str(n).strip() for n in npis if n][:500]
    if not npis_clean:
        return []

    placeholders = ", ".join(f"'{n}'" for n in npis_clean)
    table = f"`{project}.{landing_dataset}.stg_pml`"

    query = f"""
    SELECT DISTINCT
      CAST(npi AS STRING) AS npi,
      TRIM(COALESCE(provider_name, '')) AS name,
      TRIM(COALESCE(address_line_1, '')) AS address_line_1,
      TRIM(COALESCE(city, '')) AS city,
      TRIM(COALESCE(state, program_state, '')) AS state,
      SUBSTR(REGEXP_REPLACE(CONCAT(COALESCE(zip,''), COALESCE(zip_plus_4,'')), r'[^0-9]', ''), 1, 5) AS zip5,
      SUBSTR(REGEXP_REPLACE(CONCAT(COALESCE(zip,''), COALESCE(zip_plus_4,'')), r'[^0-9]', ''), 1, 9) AS zip9
    FROM {table}
    WHERE CAST(npi AS STRING) IN ({placeholders})
      AND (TRIM(COALESCE(address_line_1,'')) != '' OR TRIM(COALESCE(city,'')) != '')
    """
    try:
        rows = list(client.query(query).result())
        out = []
        for r in rows:
            d = dict(r)
            d["entity_type"] = "unknown"
            out.append(d)
        return out
    except Exception as e:
        logger.warning("PML addresses query failed: %s", e)
        return []


def _normalized_key(addr: str, city: str, state: str, zip5: str) -> str:
    """Normalized key for dedup (from address_normalizer)."""
    from app.address_normalizer import normalized_address_key
    return normalized_address_key(addr, city, state, zip5)


def find_locations_for_org(
    bq_client: Any,
    org_npis: list[str],
    *,
    initial_sites: list[dict[str, Any]] | None = None,
    state_filter: str = "FL",
    project: str | None = None,
    landing_dataset: str | None = None,
) -> list[dict[str, Any]]:
    """
    Identify all practice locations for an organization.

    Args:
        bq_client: BigQuery client.
        org_npis: NPIs identified for the org (from Step 1 find-org).
        initial_sites: Optional list of {address_line_1, city, state, zip5} from org identification.
        state_filter: State filter for addresses (default FL).
        project: BQ project (default from env).
        landing_dataset: Landing dataset for stg_doge, stg_pml (default from env).

    Returns:
        List of locations, each:
        {
          "location_id": str,
          "site_address_line_1": str,
          "site_city": str,
          "site_state": str,
          "site_zip5": str,
          "site_source": "initial" | "org_nppes" | "org_pml" | "servicing_nppes" | "servicing_pml",
          "npi": str (when from NPPES/PML),
          "name": str (when available),
        }
    """
    proj = project or _get_project()
    land_ds = landing_dataset or _get_landing_dataset()

    seen_keys: set[str] = set()
    locations: list[dict[str, Any]] = []

    state_upper = (state_filter or "FL").strip().upper()[:2]
    if state_upper == "FL":
        state_ok = lambda s: (s or "").upper() in ("FL", "FLORIDA", "")
    else:
        state_ok = lambda s: (s or "").upper()[:2] == state_upper

    def _add(addr: str, city: str, state: str, zip5: str, source: str, npi: str = "", name: str = "") -> None:
        if not (addr or city or zip5):
            return
        if not state_ok(state) and state:
            return
        key = _normalized_key(addr, city, state or state_filter, zip5)
        if key in seen_keys:
            return
        seen_keys.add(key)
        locations.append({
            "location_id": _location_id(addr, city, state, zip5),
            "site_address_line_1": addr,
            "site_city": city,
            "site_state": state or state_filter,
            "site_zip5": zip5,
            "site_source": source,
            "npi": npi,
            "name": name,
        })

    # (a) Initial sites from org identification
    for s in (initial_sites or []):
        addr = (s.get("address_line_1") or s.get("site_address_line_1") or "").strip()
        city = (s.get("city") or s.get("site_city") or "").strip()
        state = (s.get("state") or s.get("site_state") or state_filter).strip()
        zip5 = (s.get("zip5") or s.get("site_zip5") or s.get("postal_code") or "").strip()[:5]
        if zip5 or addr or city:
            _add(addr, city, state, zip5, "initial")

    # (b) Org NPI addresses from NPPES (entity 2 = facilities) and PML
    org_addrs_nppes = _addresses_from_nppes(bq_client, org_npis, proj)
    for r in org_addrs_nppes:
        _add(
            (r.get("address_line_1") or "").strip(),
            (r.get("city") or "").strip(),
            (r.get("state") or "").strip(),
            (r.get("zip5") or "").strip()[:5],
            "org_nppes",
            npi=r.get("npi", ""),
            name=r.get("name", ""),
        )

    if land_ds:
        org_addrs_pml = _addresses_from_pml(bq_client, org_npis, proj, land_ds)
        for r in org_addrs_pml:
            _add(
                (r.get("address_line_1") or "").strip(),
                (r.get("city") or "").strip(),
                (r.get("state") or "").strip(),
                (r.get("zip5") or "").strip()[:5],
                "org_pml",
                npi=r.get("npi", ""),
                name=r.get("name", ""),
            )

    # (c) Servicing NPIs from DOGE
    servicing_npis = _servicing_npis_from_doge(bq_client, org_npis, project=proj, landing_dataset=land_ds)
    all_npis = list(dict.fromkeys(org_npis + servicing_npis))

    serv_nppes = _addresses_from_nppes(bq_client, servicing_npis, proj)
    for r in serv_nppes:
        _add(
            (r.get("address_line_1") or "").strip(),
            (r.get("city") or "").strip(),
            (r.get("state") or "").strip(),
            (r.get("zip5") or "").strip()[:5],
            "servicing_nppes",
            npi=r.get("npi", ""),
            name=r.get("name", ""),
        )

    if land_ds and servicing_npis:
        serv_pml = _addresses_from_pml(bq_client, servicing_npis, proj, land_ds)
        for r in serv_pml:
            _add(
                (r.get("address_line_1") or "").strip(),
                (r.get("city") or "").strip(),
                (r.get("state") or "").strip(),
                (r.get("zip5") or "").strip()[:5],
                "servicing_pml",
                npi=r.get("npi", ""),
                name=r.get("name", ""),
            )

    return locations
