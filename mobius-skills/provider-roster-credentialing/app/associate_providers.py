"""
Step 3: Find all associated facilities and providers per location.

(a) Historic servicing NPIs from DOGE (billed under org NPIs) - strongest association
(b) Address-match NPIs: union of NPPES + PML by ZIP; normalize; strong match (all elements + zip9 when both have 9 digits), weak match (zip9 same building)
(c) Cross-org penalty: reduce association if NPI billed under a different org
(d) Assemble unique list per location with npi, entity_type (1=individual, 2=facility), association_likelihood

ZIP stored in single field; use len: 5 digits = zip5, 9 digits = zip9 for matching.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.address_normalizer import (
    extract_zip5,
    extract_zip9,
    normalized_address_key,
    normalize_street,
    normalize_city,
    normalize_state,
)

logger = logging.getLogger(__name__)

_MAX_CANDIDATES_PER_ZIP = 5000
_CROSS_ORG_PENALTY = 20
_BASE_HISTORIC = 80
_BASE_ADDRESS_STRONG = 70
_BASE_ADDRESS_WEAK = 45

# Heavy penalties for historic-only / stale association (DOGE is historic, not current)
_PENALTY_NAME_NOT_FOUND = 45
_PENALTY_NOT_IN_NPPES = 50
_PENALTY_NPPES_DEACTIVATED = 45
_PENALTY_PML_INACTIVE = 35
_PENALTY_ORG_NAME_MISMATCH = 40

# Cutoff for "active" roster; only providers above this are used downstream
ACTIVE_ROSTER_CUTOFF = 50


def _get_project() -> str:
    import os
    return os.environ.get("BQ_PROJECT", "mobius-os-dev")


def _get_landing_dataset() -> str | None:
    import os
    return os.environ.get("BQ_LANDING_MEDICAID_DATASET") or None


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
    period_from: str = "202407",
    period_to: str = "202412",
) -> list[str]:
    """Get distinct servicing_npi from DOGE where billing_npi IN org_npis.
    Default 2024-07..2024-12 for more recent (valid) leads."""
    if not org_npis or not landing_dataset:
        return []
    npis = [str(n).strip().lstrip("0") or "0" for n in org_npis]
    npis = [n if len(n) == 10 else n.zfill(10) for n in npis if n and n != "0"][:100]
    if not npis:
        return []
    table = f"`{project}.{landing_dataset}.stg_doge`"
    in_list = ", ".join(f"'{n}'" for n in npis)
    query = f"""
    SELECT DISTINCT TRIM(CAST(servicing_npi AS STRING)) AS servicing_npi
    FROM {table}
    WHERE TRIM(CAST(billing_npi AS STRING)) IN ({in_list})
      AND servicing_npi IS NOT NULL
      AND TRIM(CAST(servicing_npi AS STRING)) != ''
      AND SUBSTR(SAFE_CAST(period_month AS STRING), 1, 6) >= @period_from
      AND SUBSTR(SAFE_CAST(period_month AS STRING), 1, 6) <= @period_to
    """
    try:
        job_config = _job_config([
            ("period_from", "STRING", period_from),
            ("period_to", "STRING", period_to),
        ])
        rows = list(client.query(query, job_config=job_config).result())
        return [str(r.servicing_npi).strip() for r in rows if r.servicing_npi]
    except Exception as e:
        logger.warning("DOGE servicing NPIs failed: %s", e)
        return []


def _billing_orgs_per_npi(
    client: Any,
    servicing_npis: list[str],
    *,
    project: str,
    landing_dataset: str,
) -> dict[str, set[str]]:
    """For each servicing_npi, which billing_npis (orgs) have they ever billed under."""
    if not servicing_npis or not landing_dataset:
        return {}
    npis = [str(n).strip().zfill(10) for n in servicing_npis if n][:500]
    if not npis:
        return {}
    table = f"`{project}.{landing_dataset}.stg_doge`"
    in_list = ", ".join(f"'{n}'" for n in npis)
    query = f"""
    SELECT TRIM(CAST(servicing_npi AS STRING)) AS servicing_npi,
           TRIM(CAST(billing_npi AS STRING)) AS billing_npi
    FROM {table}
    WHERE TRIM(CAST(servicing_npi AS STRING)) IN ({in_list})
      AND billing_npi IS NOT NULL
    """
    try:
        rows = list(client.query(query).result())
        out: dict[str, set[str]] = {}
        for r in rows:
            s = str(r.servicing_npi).strip()
            b = str(r.billing_npi).strip()
            if s and b:
                out.setdefault(s, set()).add(b)
        return out
    except Exception as e:
        logger.warning("DOGE billing orgs query failed: %s", e)
        return {}


def _fetch_nppes_by_zip5_union(
    client: Any,
    zip5: str,
    state: str,
    project: str,
) -> list[dict]:
    """Fetch NPIs from NPPES by zip5; entity_filter=None (both 1 and 2); include zip9."""
    if not zip5 or len(zip5) < 5:
        return []
    state_upper = (state or "FL").strip().upper()[:2]
    if state_upper == "FL":
        state_cond = "UPPER(TRIM(COALESCE(n.provider_business_practice_location_address_state_name,''))) IN ('FL','FLORIDA')"
    else:
        state_cond = f"UPPER(TRIM(COALESCE(n.provider_business_practice_location_address_state_name,''))) = '{state_upper}'"
    zip_raw = "REGEXP_REPLACE(COALESCE(n.provider_business_practice_location_address_postal_code,''), r'[^0-9]', '')"
    zip_cond = f"SUBSTR({zip_raw}, 1, 5) = @zip5"
    name_expr = "CASE WHEN CAST(n.entity_type_code AS STRING) = '2' THEN COALESCE(n.provider_organization_name_legal_business_name,'') ELSE TRIM(CONCAT(COALESCE(n.provider_last_name_legal_name,''), ', ', COALESCE(n.provider_first_name,''))) END"
    entity_expr = "CAST(n.entity_type_code AS STRING)"
    query = f"""
    SELECT
      CAST(n.npi AS STRING) AS npi,
      TRIM({name_expr}) AS name,
      {entity_expr} AS entity_type,
      TRIM(COALESCE(n.provider_first_line_business_practice_location_address,'')) AS address_line_1,
      TRIM(COALESCE(n.provider_business_practice_location_address_city_name,'')) AS city,
      TRIM(COALESCE(n.provider_business_practice_location_address_state_name,'')) AS state,
      SUBSTR({zip_raw}, 1, 5) AS zip5,
      CASE WHEN LENGTH({zip_raw}) >= 9 THEN SUBSTR({zip_raw}, 1, 9) ELSE SUBSTR({zip_raw}, 1, 5) END AS zip9
    FROM `bigquery-public-data.nppes.npi_raw` n
    WHERE ({state_cond}) AND {zip_cond}
    ORDER BY n.entity_type_code, name
    LIMIT @lim
    """
    try:
        job_config = _job_config([("zip5", "STRING", zip5), ("lim", "INT64", _MAX_CANDIDATES_PER_ZIP)])
        rows = list(client.query(query, job_config=job_config).result())
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("NPPES by zip failed: %s", e)
        return []


def _fetch_pml_by_zip5_union(
    client: Any,
    zip5: str,
    state: str,
    project: str,
    landing_dataset: str,
) -> list[dict]:
    """Fetch NPIs from PML by zip5; include zip9. PML entity_type from NPPES lookup or default 1."""
    if not zip5 or not landing_dataset:
        return []
    state_upper = (state or "FL").strip().upper()[:2]
    if state_upper == "FL":
        state_cond = "UPPER(TRIM(COALESCE(program_state, state, ''))) IN ('FL','FLORIDA')"
    else:
        state_cond = f"UPPER(TRIM(COALESCE(program_state, state, ''))) = '{state_upper}'"
    zip_raw = "REGEXP_REPLACE(CONCAT(COALESCE(zip,''), COALESCE(zip_plus_4,'')), r'[^0-9]', '')"
    zip_cond = f"SUBSTR({zip_raw}, 1, 5) = @zip5"
    table = f"`{project}.{landing_dataset}.stg_pml`"
    query = f"""
    SELECT DISTINCT
      CAST(npi AS STRING) AS npi,
      TRIM(COALESCE(provider_name, '')) AS name,
      TRIM(COALESCE(address_line_1, '')) AS address_line_1,
      TRIM(COALESCE(city, '')) AS city,
      TRIM(COALESCE(state, program_state, '')) AS state,
      SUBSTR({zip_raw}, 1, 5) AS zip5,
      CASE WHEN LENGTH({zip_raw}) >= 9 THEN SUBSTR({zip_raw}, 1, 9) ELSE SUBSTR({zip_raw}, 1, 5) END AS zip9
    FROM {table}
    WHERE ({state_cond}) AND {zip_cond}
    ORDER BY provider_name
    LIMIT @lim
    """
    try:
        job_config = _job_config([("zip5", "STRING", zip5), ("lim", "INT64", _MAX_CANDIDATES_PER_ZIP)])
        rows = list(client.query(query, job_config=job_config).result())
        out = []
        for r in rows:
            d = dict(r)
            d["entity_type"] = "1"
            out.append(d)
        return out
    except Exception as e:
        logger.warning("PML by zip failed: %s", e)
        return []


def _fetch_npi_names(client: Any, npis: list[str], project: str) -> dict[str, str]:
    """Fetch NPI -> name from NPPES for given NPIs."""
    if not npis:
        return {}
    npis_clean = [str(n).strip().zfill(10) for n in npis if n][:500]
    if not npis_clean:
        return {}
    in_list = ", ".join(f"'{n}'" for n in npis_clean)
    name_expr = (
        "CASE WHEN CAST(n.entity_type_code AS STRING) = '2' "
        "THEN COALESCE(n.provider_organization_name_legal_business_name,'') "
        "ELSE TRIM(CONCAT(COALESCE(n.provider_last_name_legal_name,''), ', ', COALESCE(n.provider_first_name,''))) END"
    )
    query = f"""
    SELECT CAST(n.npi AS STRING) AS npi, TRIM({name_expr}) AS name
    FROM `bigquery-public-data.nppes.npi_raw` n
    WHERE CAST(n.npi AS STRING) IN ({in_list})
    """
    try:
        rows = list(client.query(query).result())
        return {str(r.npi).strip(): str(r.name or "").strip() for r in rows if r.npi}
    except Exception as e:
        logger.warning("NPPES name lookup failed: %s", e)
        return {}


def _normalize_org_name(s: str) -> str:
    """Lowercase, strip, remove common suffixes and punctuation for comparison."""
    t = (s or "").lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    for suffix in ("inc", "llc", "lpa", "corp", "ltd", "pa", "pc", "pllc", "dba"):
        t = re.sub(rf"\b{suffix}\b", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _org_name_mismatch(org_name_solve: str, nppes_org_name: str) -> bool:
    """True if nppes_org_name exists and is clearly different from org_name_solve."""
    solve_n = _normalize_org_name(org_name_solve)
    nppes_n = _normalize_org_name(nppes_org_name)
    if not solve_n or not nppes_n:
        return False
    if solve_n in nppes_n or nppes_n in solve_n:
        return False
    solve_tokens = {w for w in solve_n.split() if len(w) > 2}
    nppes_tokens = {w for w in nppes_n.split() if len(w) > 2}
    overlap = solve_tokens & nppes_tokens
    if len(overlap) >= 2:
        return False
    return True


def _fetch_nppes_status(
    client: Any, npis: list[str], project: str
) -> dict[str, dict[str, Any]]:
    """Return npi -> {in_nppes, active, org_name}. org_name = provider_organization_name_legal_business_name."""
    if not npis:
        return {}
    npis_clean = list(dict.fromkeys(str(n).strip().zfill(10) for n in npis if n))[:500]
    in_list = ", ".join(f"'{n}'" for n in npis_clean)
    query = """
    SELECT TRIM(CAST(npi AS STRING)) AS npi, npi_deactivation_date,
           TRIM(COALESCE(provider_organization_name_legal_business_name,'')) AS org_name
    FROM `bigquery-public-data.nppes.npi_raw`
    WHERE TRIM(CAST(npi AS STRING)) IN ({})
    """.format(in_list)
    out: dict[str, dict[str, Any]] = {
        n: {"in_nppes": False, "active": False, "org_name": ""} for n in npis_clean
    }
    try:
        rows = list(client.query(query).result())
    except Exception as e:
        try:
            query_fb = f"""
            SELECT TRIM(CAST(npi AS STRING)) AS npi,
                   TRIM(COALESCE(provider_organization_name_legal_business_name,'')) AS org_name
            FROM `bigquery-public-data.nppes.npi_raw`
            WHERE TRIM(CAST(npi AS STRING)) IN ({in_list})
            """
            rows = list(client.query(query_fb).result())
        except Exception as e2:
            logger.warning("NPPES status fetch failed: %s", e2)
            return out
    for r in rows:
        npi = str(getattr(r, "npi", "")).strip()
        if not npi:
            continue
        deact = getattr(r, "npi_deactivation_date", None)
        active = deact is None
        org_name = str(getattr(r, "org_name", "") or "").strip()
        out[npi] = {"in_nppes": True, "active": active, "org_name": org_name}
    return out


def _fetch_pml_status(
    client: Any, npis: list[str], project: str, landing_dataset: str
) -> dict[str, dict[str, Any]]:
    """Return npi -> {in_pml, active}. Active = has any PML row with active status/contract."""
    if not npis or not landing_dataset:
        return {}
    npis_clean = list(dict.fromkeys(str(n).strip().zfill(10) for n in npis if n))[:500]
    in_list = ", ".join(f"'{n}'" for n in npis_clean)
    table = f"`{project}.{landing_dataset}.stg_pml`"
    query = f"""
    SELECT TRIM(CAST(npi AS STRING)) AS npi, status, contract_end_date
    FROM {table}
    WHERE TRIM(CAST(npi AS STRING)) IN ({in_list})
    """
    out: dict[str, dict[str, Any]] = {n: {"in_pml": False, "active": False} for n in npis_clean}
    try:
        rows = list(client.query(query).result())
    except Exception as e:
        logger.warning("PML status fetch failed: %s", e)
        return out
    for r in rows:
        npi = str(getattr(r, "npi", "")).strip()
        if not npi:
            continue
        status = (str(getattr(r, "status", "") or "")).lower()
        end = getattr(r, "contract_end_date", None)
        inactive = "inactive" in status or "terminated" in status or "revoked" in status
        if end is not None:
            try:
                from datetime import date
                d = end if isinstance(end, date) else __import__("datetime").datetime.strptime(str(end)[:10], "%Y-%m-%d").date()
                if d < date.today():
                    inactive = True
            except Exception:
                pass
        out[npi]["in_pml"] = True
        if not inactive:
            out[npi]["active"] = True
    return out


def _fetch_pml_names(
    client: Any, npis: list[str], project: str, landing_dataset: str
) -> dict[str, str]:
    """Fetch NPI -> name from PML for given NPIs. Fallback when NPPES has no name (e.g. deactivated)."""
    if not npis or not landing_dataset:
        return {}
    npis_clean = [str(n).strip().zfill(10) for n in npis if n][:500]
    if not npis_clean:
        return {}
    in_list = ", ".join(f"'{n}'" for n in npis_clean)
    table = f"`{project}.{landing_dataset}.stg_pml`"
    query = f"""
    SELECT TRIM(CAST(npi AS STRING)) AS npi,
           TRIM(COALESCE(provider_name, '')) AS name
    FROM {table}
    WHERE TRIM(CAST(npi AS STRING)) IN ({in_list})
      AND TRIM(COALESCE(provider_name, '')) != ''
    """
    try:
        rows = list(client.query(query).result())
        return {str(r.npi).strip(): str(r.name or "").strip() for r in rows if r.npi and (r.name or "").strip()}
    except Exception as e:
        logger.warning("PML name lookup failed: %s", e)
        return {}


def _address_match_strength(
    loc_addr: str,
    loc_city: str,
    loc_state: str,
    loc_zip: str,
    npi_addr: str,
    npi_city: str,
    npi_state: str,
    npi_zip: str,
) -> str | None:
    """
    Returns "strong" | "weak" | None.
    Strong: full normalized address match + zip9 match when both have 9 digits.
    Weak: zip9 match when both have 9 digits (same building).
    Use len: zip5 = first 5 digits, zip9 = first 9 when len>=9.
    """
    loc_zip5 = extract_zip5(loc_zip)
    loc_zip9 = extract_zip9(loc_zip)
    npi_zip5 = extract_zip5(npi_zip)
    npi_zip9 = extract_zip9(npi_zip)
    if loc_zip5 != npi_zip5:
        return None
    loc_key = normalized_address_key(loc_addr, loc_city, loc_state, loc_zip)
    npi_key = normalized_address_key(npi_addr, npi_city, npi_state, npi_zip)
    if loc_key == npi_key:
        if len(loc_zip9) >= 9 and len(npi_zip9) >= 9 and loc_zip9 == npi_zip9:
            return "strong"
        return "strong"
    if len(loc_zip9) >= 9 and len(npi_zip9) >= 9 and loc_zip9 == npi_zip9:
        return "weak"
    return None


def find_associated_providers(
    bq_client: Any,
    locations: list[dict[str, Any]],
    org_npis: list[str],
    *,
    project: str | None = None,
    landing_dataset: str | None = None,
    state_filter: str = "FL",
    active_roster_cutoff: int = ACTIVE_ROSTER_CUTOFF,
    org_name: str = "",
) -> dict[str, Any]:
    """
    Find all associated facilities and providers per location.

    Returns: {
      "associated_providers": { location_id: [ { npi, name, entity_type, association_likelihood, match_type, roster_status }, ... ] },
      "active_roster": { location_id: [ providers with roster_status="active" ] },
      "active_roster_cutoff": int,
    }
    roster_status: "active" if score >= cutoff (used downstream); "historic" otherwise.
    Heavy penalties applied for: no name, not in NPPES, NPPES deactivated, PML inactive.
    """
    proj = project or _get_project()
    land_ds = landing_dataset or _get_landing_dataset()
    org_set = {str(n).strip().zfill(10) for n in org_npis if n}

    historic = _servicing_npis_from_doge(
        bq_client, org_npis, project=proj, landing_dataset=land_ds or ""
    )
    billing_orgs = _billing_orgs_per_npi(
        bq_client, list(set(historic)), project=proj, landing_dataset=land_ds or ""
    ) if land_ds else {}
    # Pre-fetch names for historic NPIs (DOGE has no names): NPPES first, PML fallback
    historic_npis = list(set(historic))
    historic_names = _fetch_npi_names(bq_client, historic_npis, proj)
    missing = [n for n in historic_npis if not (historic_names.get(str(n).strip().zfill(10), "") or "").strip()]
    if missing and land_ds:
        pml_names = _fetch_pml_names(bq_client, missing, proj, land_ds)
        for npi, name in pml_names.items():
            if name:
                historic_names[npi] = name

    result: dict[str, list[dict[str, Any]]] = {}
    for loc in locations:
        loc_id = loc.get("location_id") or ""
        addr = str(loc.get("site_address_line_1") or "").strip()
        city = str(loc.get("site_city") or "").strip()
        state = str(loc.get("site_state") or state_filter).strip()
        zip_val = str(loc.get("site_zip5") or loc.get("site_zip") or "").strip()
        zip5 = extract_zip5(zip_val)
        zip9 = extract_zip9(zip_val)
        if not zip5:
            result[loc_id] = []
            continue

        seen_npis: dict[str, dict[str, Any]] = {}

        for npi in historic:
            npi = str(npi).strip().zfill(10)
            if not npi:
                continue
            score = _BASE_HISTORIC
            if npi in billing_orgs:
                other_orgs = billing_orgs[npi] - org_set
                if other_orgs:
                    score = max(0, score - _CROSS_ORG_PENALTY)
            name = historic_names.get(npi, "").strip()
            seen_npis[npi] = {
                "npi": npi,
                "name": name,
                "entity_type": "1",
                "association_likelihood": min(100, score),
                "match_type": "historic_billing",
                "name_status": "not_found_in_nppes" if not name else None,
            }

        nppes_rows = _fetch_nppes_by_zip5_union(bq_client, zip5, state, proj)
        pml_rows = _fetch_pml_by_zip5_union(bq_client, zip5, state, proj, land_ds or "")
        all_rows = nppes_rows[:]
        seen_pml = {r["npi"] for r in pml_rows}
        for r in pml_rows:
            if r["npi"] not in {x["npi"] for x in nppes_rows}:
                all_rows.append(r)

        for r in all_rows:
            npi = str(r.get("npi", "")).strip().zfill(10)
            if not npi:
                continue
            npi_addr = str(r.get("address_line_1") or "").strip()
            npi_city = str(r.get("city") or "").strip()
            npi_state = str(r.get("state") or "").strip()
            npi_zip = str(r.get("zip5") or r.get("zip9") or "").strip()
            strength = _address_match_strength(
                addr, city, state, zip_val, npi_addr, npi_city, npi_state, npi_zip
            )
            if strength is None:
                continue
            score = _BASE_ADDRESS_STRONG if strength == "strong" else _BASE_ADDRESS_WEAK
            if npi in billing_orgs and (billing_orgs[npi] - org_set):
                score = max(0, score - _CROSS_ORG_PENALTY)
            entity = str(r.get("entity_type", "1")).strip()
            if entity not in ("1", "2"):
                entity = "1"
            if npi in seen_npis:
                existing = seen_npis[npi]
                if score > existing.get("association_likelihood", 0):
                    existing["association_likelihood"] = min(100, score)
                    existing["match_type"] = f"address_{strength}"
                # Enrich name from address match if historic had no name
                if not existing.get("name") and r.get("name"):
                    existing["name"] = str(r.get("name", "")).strip()
                    existing.pop("name_status", None)
            else:
                name_val = str(r.get("name", "")).strip()
                seen_npis[npi] = {
                    "npi": npi,
                    "name": name_val,
                    "entity_type": entity,
                    "association_likelihood": min(100, score),
                    "match_type": f"address_{strength}",
                    "name_status": "not_found_in_nppes" if not name_val else None,
                }

        result[loc_id] = sorted(
            seen_npis.values(),
            key=lambda x: (-(x.get("association_likelihood") or 0), x.get("npi", "")),
        )

    # Pass 2: NPPES/PML status, penalties, roster_status
    all_npis = list(set(p["npi"] for provs in result.values() for p in provs if p.get("npi")))
    nppes_status = _fetch_nppes_status(bq_client, all_npis, proj)
    pml_status = _fetch_pml_status(bq_client, all_npis, proj, land_ds or "") if land_ds else {}

    active_roster: dict[str, list[dict[str, Any]]] = {}
    for loc_id, provs in result.items():
        penalized: list[dict[str, Any]] = []
        active_list: list[dict[str, Any]] = []
        for p in provs:
            p = dict(p)
            npi = str(p.get("npi", "")).strip().zfill(10)
            score = int(p.get("association_likelihood") or 0)

            ns = nppes_status.get(npi, {"in_nppes": False, "active": False})
            ps = pml_status.get(npi, {"in_pml": False, "active": False})

            if not (p.get("name") or "").strip():
                score = max(0, score - _PENALTY_NAME_NOT_FOUND)
            if not ns["in_nppes"]:
                score = max(0, score - _PENALTY_NOT_IN_NPPES)
            elif not ns["active"]:
                score = max(0, score - _PENALTY_NPPES_DEACTIVATED)
            if ps.get("in_pml") and not ps.get("active"):
                score = max(0, score - _PENALTY_PML_INACTIVE)
            if org_name and _org_name_mismatch(org_name, ns.get("org_name") or ""):
                score = max(0, score - _PENALTY_ORG_NAME_MISMATCH)

            p["association_likelihood"] = min(100, score)
            p["roster_status"] = "active" if score >= active_roster_cutoff else "historic"
            penalized.append(p)
            if p["roster_status"] == "active":
                active_list.append(p)

        result[loc_id] = sorted(penalized, key=lambda x: (-(x.get("association_likelihood") or 0), x.get("npi", "")))
        active_roster[loc_id] = active_list

    return {
        "associated_providers": result,
        "active_roster": active_roster,
        "active_roster_cutoff": active_roster_cutoff,
    }
