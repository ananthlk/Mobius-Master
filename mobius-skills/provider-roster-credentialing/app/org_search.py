"""
Step 1: Organization name search and address search for disambiguation.

Given a user-provided org/provider name OR address, search NPPES and PML
and return candidate matches with NPI. Used for interactive chat flow.

Uses direct BigQuery (no dbt trigger) for low latency and scaling.
Address normalization: Google Address Validation when available, else local.
Env: BQ_PROJECT, BQ_LANDING_MEDICAID_DATASET (optional, for PML).
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Max search words for LIKE AND logic
_MAX_WORDS = 5

# Max street words for address search (legacy LIKE matching)
_MAX_STREET_WORDS = 4

# Max rows to fetch per ZIP for normalized-address matching (avoids huge pulls)
_MAX_CANDIDATES_PER_ZIP = 5000

# Default limit of matches per source
_DEFAULT_LIMIT = 20


def search_org_names(
    bq_client: Any,
    name: str,
    *,
    state_filter: str = "FL",
    limit: int = _DEFAULT_LIMIT,
    project: str | None = None,
    landing_dataset: str | None = None,
    include_pml: bool = True,
    entity_type_filter: str | None = "2",
) -> list[dict[str, Any]]:
    """
    Search NPPES and optionally PML for org/provider names matching the given string.

    Uses word-based AND matching: each word must appear in the name (case-insensitive).
    E.g. "David Lawrence" matches "David Lawrence Center" and "Lawrence, David MD".

    Returns list of { npi, name, source, entity_type }.
    - source: "nppes" | "pml"
    - entity_type: "organization" | "individual" (NPPES only); "unknown" for PML
    """
    name = (name or "").strip()
    if not name:
        return []

    words = [w.strip().lower() for w in name.split() if w.strip()][:_MAX_WORDS]
    if not words:
        return []

    proj = project or _get_project()
    land_ds = landing_dataset or _get_landing_dataset()
    out: list[dict[str, Any]] = []

    # 1. NPPES search (always; public dataset)
    nppes_rows = _search_nppes(bq_client, words, state_filter, limit, proj, entity_type_filter=entity_type_filter)
    for r in nppes_rows:
        tax = str(r.get("taxonomy_code", "")).strip()
        out.append({
            "npi": str(r.get("npi", "")),
            "name": str(r.get("name", "")),
            "source": "nppes",
            "entity_type": str(r.get("entity_type", "unknown")),
            "taxonomy_code": tax if tax else None,
        })

    # 2. PML search (optional; requires landing dataset)
    if include_pml and land_ds:
        try:
            pml_rows = _search_pml(bq_client, words, state_filter, limit, proj, land_ds)
            seen_npis = {x["npi"] for x in out}
            for r in pml_rows:
                npi = str(r.get("npi", ""))
                if npi and npi not in seen_npis:
                    seen_npis.add(npi)
                    out.append({
                        "npi": npi,
                        "name": str(r.get("name", "")),
                        "source": "pml",
                        "entity_type": "unknown",
                        "taxonomy_code": None,
                    })
        except Exception as e:
            logger.warning("PML org search skipped: %s", e)

    return out


def normalize_address(
    address_line_1: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    *,
    address_raw: str | None = None,
    use_google: bool = True,
) -> dict[str, str] | None:
    """
    Normalize address for search. Use Google when available, else local normalizer.

    Pass either (address_line_1, city, state, postal_code) or address_raw (free-form string).
    Returns { address_line_1, city, state, zip5, zip_plus_4 } or None if invalid.
    """
    if address_raw and not any([address_line_1, city, state, postal_code]):
        parsed = _parse_address_string(address_raw)
        if not parsed:
            return None
        address_line_1 = parsed.get("address_line_1") or ""
        city = parsed.get("city") or ""
        state = parsed.get("state") or ""
        postal_code = parsed.get("postal_code") or ""

    if not (address_line_1 or city or state or postal_code):
        return None

    norm = _normalize_via_google_or_local(
        address_line_1 or "",
        city or "",
        state or "",
        postal_code or "",
        use_google=use_google,
    )
    if not norm or not norm.get("zip5"):
        return None
    return norm


def _parse_address_string(s: str) -> dict[str, str] | None:
    """Parse free-form US address like '123 Main St, Miami, FL 33101' or 'Miami FL 33101'."""
    s = (s or "").strip()
    if not s:
        return None
    # Match ZIP at end (5 or 9 digits)
    zip_m = re.search(r"(\d{5})(?:-\d{4})?\s*$", s)
    zip5 = zip_m.group(1) if zip_m else ""
    rest = s[: zip_m.start()].strip() if zip_m else s

    # Match state (2 letters or FLORIDA) before zip
    state_m = re.search(r",?\s+([A-Za-z]{2}|Florida)\s*,?\s*$", rest, re.IGNORECASE)
    state = (state_m.group(1) or "").strip().upper() if state_m else ""
    if state == "FLORIDA":
        state = "FL"
    elif len(state) > 2:
        state = state[:2]
    rest = rest[: state_m.start()].strip() if state_m else rest

    # Remainder: "123 Main St, Miami" or "Miami"
    parts = [p.strip() for p in rest.split(",") if p.strip()]
    if len(parts) >= 2:
        address_line_1 = ", ".join(parts[:-1])
        city = parts[-1]
    elif len(parts) == 1:
        # Single part: could be "123 Main St Miami" or just "Miami"
        if re.match(r"^[\d\w\s\.\#\-]+$", parts[0]) and any(c.isdigit() for c in parts[0]):
            address_line_1 = parts[0]
            city = ""
        else:
            address_line_1 = ""
            city = parts[0]
    else:
        address_line_1 = ""
        city = ""

    if not zip5 and not city and not address_line_1:
        return None
    return {
        "address_line_1": address_line_1,
        "city": city,
        "state": state or "FL",
        "postal_code": zip5,
    }


def _normalize_via_google_or_local(
    address_line_1: str,
    city: str,
    state: str,
    postal_code: str,
    *,
    use_google: bool = True,
) -> dict[str, str] | None:
    """Normalize using Google when use_google=True and available, else local."""
    from app.address_normalizer import extract_zip5, normalize_state

    fallback_zip5 = extract_zip5(postal_code)
    if not fallback_zip5:
        return None

    norm = None
    if use_google:
        try:
            from app.google_address_client import normalize_via_google, normalized_from_local

            norm = normalize_via_google(address_line_1, city, state, postal_code)
            if norm is None:
                norm = normalized_from_local(address_line_1, city, state, postal_code)
        except Exception as e:
            logger.warning("Google address normalization failed, using local: %s", e)
    if norm is None:
        from app.google_address_client import normalized_from_local

        norm = normalized_from_local(address_line_1, city, state, postal_code)
    zip5 = norm.zip5 or fallback_zip5
    return {
        "address_line_1": norm.address_line_1 or address_line_1,
        "city": norm.city or city,
        "state": norm.state or state,
        "zip5": zip5,
        "zip_plus_4": norm.zip_plus_4 or "",
    }


def search_org_by_address(
    bq_client: Any,
    *,
    address_line_1: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    address_raw: str | None = None,
    limit: int = _DEFAULT_LIMIT,
    project: str | None = None,
    landing_dataset: str | None = None,
    include_pml: bool = True,
    use_google: bool = True,
    entity_type_filter: str | None = "2",
) -> tuple[dict[str, str] | None, list[dict[str, Any]]]:
    """
    Search NPPES and PML by address. Normalizes the address first.

    Pass address_line_1, city, state, postal_code OR address_raw (free-form string).
    Returns (normalized_address, results).
    - entity_type_filter: "2" = orgs only (default), "1" = individuals, None = all
    """
    norm = normalize_address(
        address_line_1=address_line_1,
        city=city,
        state=state,
        postal_code=postal_code,
        address_raw=address_raw,
        use_google=use_google,
    )
    if not norm or not norm.get("zip5"):
        return None, []

    proj = project or _get_project()
    land_ds = landing_dataset or _get_landing_dataset()
    out: list[dict[str, Any]] = []

    # User's normalized key for matching (handles W vs West, Blvd vs Boulevard, etc.)
    from app.address_normalizer import normalized_address_key

    user_key = normalized_address_key(
        norm.get("address_line_1"),
        norm.get("city"),
        norm.get("state"),
        norm.get("zip5"),
    )

    # 1. NPPES: fetch all by zip5, normalize each, match
    nppes_rows = _fetch_nppes_by_zip5(
        bq_client, norm["zip5"], norm["state"], proj, entity_type_filter=entity_type_filter
    )
    for r in nppes_rows:
        row_key = normalized_address_key(
            r.get("address_line_1"),
            r.get("city"),
            r.get("state"),
            r.get("zip5"),
        )
        if row_key == user_key:
            out.append({
                "npi": str(r.get("npi", "")),
                "name": str(r.get("name", "")),
                "source": "nppes",
                "entity_type": str(r.get("entity_type", "unknown")),
                "address_line_1": str(r.get("address_line_1", "")),
                "city": str(r.get("city", "")),
                "state": str(r.get("state", "")),
                "zip5": str(r.get("zip5", "")),
            })
            if len(out) >= limit:
                break

    # 2. PML: same approach
    if include_pml and land_ds and len(out) < limit:
        try:
            pml_rows = _fetch_pml_by_zip5(
                bq_client, norm["zip5"], norm["state"], proj, land_ds
            )
            seen_npis = {x["npi"] for x in out}
            for r in pml_rows:
                if len(out) >= limit:
                    break
                row_key = normalized_address_key(
                    r.get("address_line_1"),
                    r.get("city"),
                    r.get("state"),
                    r.get("zip5"),
                )
                if row_key == user_key:
                    npi = str(r.get("npi", ""))
                    if npi and npi not in seen_npis:
                        seen_npis.add(npi)
                        out.append({
                            "npi": npi,
                            "name": str(r.get("name", "")),
                            "source": "pml",
                            "entity_type": "unknown",
                            "address_line_1": str(r.get("address_line_1", "")),
                            "city": str(r.get("city", "")),
                            "state": str(r.get("state", "")),
                            "zip5": str(r.get("zip5", "")),
                        })
        except Exception as e:
            logger.warning("PML address search skipped: %s", e)

    return norm, out[:limit]


def _fetch_nppes_by_zip5(
    client: Any,
    zip5: str,
    state: str,
    project: str,
    *,
    entity_type_filter: str | None = "2",
) -> list[dict]:
    """Fetch all NPPES rows for zip5+state; normalized matching done in Python."""
    state_upper = (state or "FL").strip().upper()[:2]
    if state_upper == "FL":
        state_cond = "UPPER(TRIM(COALESCE(n.provider_business_practice_location_address_state_name,''))) IN ('FL','FLORIDA')"
    else:
        state_cond = f"UPPER(TRIM(COALESCE(n.provider_business_practice_location_address_state_name,''))) = '{state_upper}'"

    zip_cond = "SUBSTR(REGEXP_REPLACE(COALESCE(n.provider_business_practice_location_address_postal_code,''), r'[^0-9]', ''), 1, 5) = @zip5"
    entity_cond = ""
    if entity_type_filter is not None:
        entity_cond = f" AND CAST(n.entity_type_code AS STRING) = '{entity_type_filter}'"
    name_expr = "CASE WHEN CAST(n.entity_type_code AS STRING) = '2' THEN COALESCE(n.provider_organization_name_legal_business_name,'') ELSE TRIM(CONCAT(COALESCE(n.provider_last_name_legal_name,''), ', ', COALESCE(n.provider_first_name,''))) END"
    entity_expr = "CASE WHEN CAST(n.entity_type_code AS STRING) = '2' THEN 'organization' ELSE 'individual' END"
    addr_expr = "COALESCE(n.provider_first_line_business_practice_location_address,'')"
    city_expr = "COALESCE(n.provider_business_practice_location_address_city_name,'')"
    state_expr = "COALESCE(n.provider_business_practice_location_address_state_name,'')"
    zip_expr = "SUBSTR(REGEXP_REPLACE(COALESCE(n.provider_business_practice_location_address_postal_code,''), r'[^0-9]', ''), 1, 5)"

    query = f"""
    SELECT
      CAST(n.npi AS STRING) AS npi,
      TRIM({name_expr}) AS name,
      {entity_expr} AS entity_type,
      TRIM({addr_expr}) AS address_line_1,
      TRIM({city_expr}) AS city,
      TRIM({state_expr}) AS state,
      {zip_expr} AS zip5
    FROM `bigquery-public-data.nppes.npi_raw` n
    WHERE ({state_cond})
      AND {zip_cond}
      {entity_cond}
    ORDER BY n.entity_type_code, name
    LIMIT @lim
    """
    job_config = _job_config([("zip5", "STRING", zip5), ("lim", "INT64", _MAX_CANDIDATES_PER_ZIP)])
    rows = list(client.query(query, job_config=job_config).result())
    return [dict(r) for r in rows]


def _fetch_pml_by_zip5(
    client: Any,
    zip5: str,
    state: str,
    project: str,
    landing_dataset: str,
) -> list[dict]:
    """Fetch all PML rows for zip5+state; normalized matching done in Python."""
    state_upper = (state or "FL").strip().upper()[:2]
    if state_upper == "FL":
        state_cond = "UPPER(TRIM(COALESCE(program_state, state, ''))) IN ('FL','FLORIDA')"
    else:
        state_cond = f"UPPER(TRIM(COALESCE(program_state, state, ''))) = '{state_upper}'"

    zip_cond = "SUBSTR(REGEXP_REPLACE(CONCAT(COALESCE(zip,''), COALESCE(zip_plus_4,'')), r'[^0-9]', ''), 1, 5) = @zip5"
    table = f"`{project}.{landing_dataset}.stg_pml`"

    query = f"""
    SELECT DISTINCT
      CAST(npi AS STRING) AS npi,
      TRIM(COALESCE(provider_name, '')) AS name,
      TRIM(COALESCE(address_line_1, '')) AS address_line_1,
      TRIM(COALESCE(city, '')) AS city,
      TRIM(COALESCE(state, program_state, '')) AS state,
      SUBSTR(REGEXP_REPLACE(CONCAT(COALESCE(zip,''), COALESCE(zip_plus_4,'')), r'[^0-9]', ''), 1, 5) AS zip5
    FROM {table}
    WHERE ({state_cond})
      AND {zip_cond}
    ORDER BY provider_name
    LIMIT @lim
    """
    job_config = _job_config([("zip5", "STRING", zip5), ("lim", "INT64", _MAX_CANDIDATES_PER_ZIP)])
    rows = list(client.query(query, job_config=job_config).result())
    return [dict(r) for r in rows]


def _get_project() -> str:
    import os
    return os.environ.get("BQ_PROJECT", "mobius-os-dev")


def _get_landing_dataset() -> str | None:
    import os
    return os.environ.get("BQ_LANDING_MEDICAID_DATASET") or None


def _search_nppes(
    client: Any,
    words: list[str],
    state_filter: str,
    limit: int,
    project: str,
    *,
    entity_type_filter: str | None = "2",
) -> list[dict]:
    # NPPES: org name or individual name; filter by state
    state_upper = state_filter.strip().upper()[:2]
    if state_upper == "FL":
        state_cond = "UPPER(TRIM(COALESCE(n.provider_business_practice_location_address_state_name,''))) IN ('FL','FLORIDA')"
    else:
        state_cond = f"UPPER(TRIM(COALESCE(n.provider_business_practice_location_address_state_name,''))) = '{state_upper}'"

    entity_cond = ""
    if entity_type_filter is not None:
        entity_cond = f" AND CAST(n.entity_type_code AS STRING) = '{entity_type_filter}'"

    # entity_type_code can be INT64 in npi_raw; cast for comparison
    name_expr = "CASE WHEN CAST(n.entity_type_code AS STRING) = '2' THEN COALESCE(n.provider_organization_name_legal_business_name,'') ELSE TRIM(CONCAT(COALESCE(n.provider_last_name_legal_name,''), ', ', COALESCE(n.provider_first_name,''))) END"
    entity_expr = "CASE WHEN CAST(n.entity_type_code AS STRING) = '2' THEN 'organization' ELSE 'individual' END"

    like_parts = []
    params_list: list[tuple[str, str, Any]] = []
    for i, w in enumerate(words):
        param = f"w{i}"
        like_parts.append(f"LOWER(base.name_raw) LIKE CONCAT('%', LOWER(@{param}), '%')")
        params_list.append((param, "STRING", w))

    like_clause = " AND ".join(like_parts)

    tax_expr = "TRIM(CAST(COALESCE(n.healthcare_provider_taxonomy_code_1,'') AS STRING))"
    query = f"""
    WITH base AS (
      SELECT
        CAST(n.npi AS STRING) AS npi,
        TRIM({name_expr}) AS name_raw,
        {entity_expr} AS entity_type,
        {tax_expr} AS taxonomy_code
      FROM `bigquery-public-data.nppes.npi_raw` n
      WHERE ({state_cond}){entity_cond}
    )
    SELECT base.npi, base.name_raw AS name, base.entity_type, base.taxonomy_code
    FROM base
    WHERE ({like_clause})
    ORDER BY base.entity_type, base.name_raw
    LIMIT @lim
    """
    job_config = _job_config(params_list + [("lim", "INT64", limit)])
    rows = list(client.query(query, job_config=job_config).result())
    return [dict(r) for r in rows]


def _search_pml(
    client: Any,
    words: list[str],
    state_filter: str,
    limit: int,
    project: str,
    landing_dataset: str,
) -> list[dict]:
    # PML: provider_name; filter by program_state or state
    state_upper = state_filter.strip().upper()[:2]
    if state_upper == "FL":
        state_cond = "UPPER(TRIM(COALESCE(program_state, state, ''))) IN ('FL','FLORIDA')"
    else:
        state_cond = f"UPPER(TRIM(COALESCE(program_state, state, ''))) = '{state_upper}'"

    like_parts = []
    params_list: list[tuple[str, str, str]] = []
    for i, w in enumerate(words):
        param = f"w{i}"
        like_parts.append(f"LOWER(COALESCE(provider_name,'')) LIKE CONCAT('%', LOWER(@{param}), '%')")
        params_list.append((param, "STRING", w))

    like_clause = " AND ".join(like_parts)
    table = f"`{project}.{landing_dataset}.stg_pml`"

    query = f"""
    SELECT DISTINCT
      CAST(npi AS STRING) AS npi,
      TRIM(COALESCE(provider_name, '')) AS name
    FROM {table}
    WHERE ({state_cond})
      AND ({like_clause})
    ORDER BY name
    LIMIT @lim
    """
    job_config = _job_config(params_list + [("lim", "INT64", limit)])
    rows = list(client.query(query, job_config=job_config).result())
    return [dict(r) for r in rows]


def _job_config(params: list[tuple[str, str, Any]]) -> Any:
    from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
    return QueryJobConfig(
        query_parameters=[ScalarQueryParameter(name, typ, val) for name, typ, val in params]
    )
