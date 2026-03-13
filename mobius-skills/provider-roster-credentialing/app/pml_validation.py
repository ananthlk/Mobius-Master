"""
Step 6: PML (Provider Master List) validation.

For each PML row for our NPIs:
a) Valid NPI: NPI in NPPES and active in both PML and NPPES
b) Valid taxonomy: PML taxonomy is Medicaid-approved (TML) and associated with NPPES
c) Valid ZIP: 9-digit ZIP matching a known location
d) If a,b,c pass: valid Medicaid ID

Flags failures with specific recommendations.
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


def _normalize_zip9(zip_val: str | None, zip_plus_4: str | None) -> str:
    """Extract 9-digit ZIP from zip and zip_plus_4. Pads zip5 with 0000 when no +4."""
    import re
    digits = re.sub(r"[^0-9]", "", str(zip_val or "") + str(zip_plus_4 or ""))
    if len(digits) < 5:
        return ""
    if len(digits) >= 9:
        return digits[:9]
    return digits.ljust(9, "0")


def _extract_pml_rows(
    client: Any,
    npis: list[str],
    *,
    project: str,
    landing_dataset: str,
    program_state: str = "FL",
    product: str = "medicaid",
) -> list[dict[str, Any]]:
    """Extract all PML rows for the given NPIs."""
    if not npis or not landing_dataset:
        return []
    npis_clean = [str(n).strip().zfill(10) for n in npis if n][:500]
    if not npis_clean:
        return []
    in_list = ", ".join(f"'{n}'" for n in npis_clean)
    table = f"`{project}.{landing_dataset}.stg_pml`"
    query = f"""
    SELECT
      TRIM(CAST(npi AS STRING)) AS npi,
      TRIM(COALESCE(provider_name, '')) AS provider_name,
      TRIM(CAST(taxonomy_code AS STRING)) AS taxonomy_code,
      TRIM(COALESCE(address_line_1, '')) AS address_line_1,
      TRIM(COALESCE(city, '')) AS city,
      TRIM(COALESCE(state, '')) AS state,
      TRIM(CAST(zip AS STRING)) AS zip,
      TRIM(CAST(zip_plus_4 AS STRING)) AS zip_plus_4,
      TRIM(CAST(medicaid_provider_id AS STRING)) AS medicaid_provider_id,
      status,
      contract_effective_date,
      contract_end_date
    FROM {table}
    WHERE TRIM(CAST(npi AS STRING)) IN ({in_list})
    """
    try:
        rows = list(client.query(query).result())
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("PML extract failed: %s", e)
        return []


def _nppes_npi_status(
    client: Any,
    npis: list[str],
    project: str,
) -> dict[str, dict[str, Any]]:
    """Return npi -> {in_nppes, active, nppes_taxonomies, entity_type_code}.

    entity_type_code: "1" = individual, "2" = organization.
    """
    if not npis:
        return {}
    npis_clean = list(dict.fromkeys(str(n).strip().zfill(10) for n in npis if n))[:500]
    in_list = ", ".join(f"'{n}'" for n in npis_clean)
    cols = ", ".join(f"TRIM(CAST({c} AS STRING)) AS {c}" for c in _NPPES_TAX_COLS)
    # npi_deactivation_date: NULL = active. entity_type_code: 1=individual, 2=organization.
    query = f"""
    SELECT
      TRIM(CAST(npi AS STRING)) AS npi,
      npi_deactivation_date,
      CAST(entity_type_code AS STRING) AS entity_type_code,
      {cols}
    FROM `bigquery-public-data.nppes.npi_raw`
    WHERE TRIM(CAST(npi AS STRING)) IN ({in_list})
    """
    try:
        rows = list(client.query(query).result())
    except Exception as e:
        # Fallback: skip deactivation check if column missing
        try:
            query_fb = f"""
            SELECT TRIM(CAST(npi AS STRING)) AS npi, CAST(entity_type_code AS STRING) AS entity_type_code, {cols}
            FROM `bigquery-public-data.nppes.npi_raw`
            WHERE TRIM(CAST(npi AS STRING)) IN ({in_list})
            """
            rows = list(client.query(query_fb).result())
        except Exception as e2:
            logger.warning("NPPES status fetch failed: %s", e2)
            return {}
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        npi = str(r.get("npi", "")).strip()
        if not npi:
            continue
        deact = getattr(r, "npi_deactivation_date", None)
        active = deact is None
        taxes: set[str] = set()
        for c in _NPPES_TAX_COLS:
            v = r.get(c)
            if v is not None and str(v).strip():
                taxes.add(str(v).strip())
        entity_type = str(r.get("entity_type_code") or "1").strip()
        out[npi] = {"in_nppes": True, "active": active, "nppes_taxonomies": taxes, "entity_type_code": entity_type}
    for n in npis_clean:
        if n not in out:
            out[n] = {"in_nppes": False, "active": False, "nppes_taxonomies": set(), "entity_type_code": "1"}
    return out


def _tml_codes(client: Any, project: str, landing_dataset: str) -> set[str]:
    """Medicaid-approved taxonomy codes from TML."""
    if not landing_dataset:
        return set()
    table = f"`{project}.{landing_dataset}.stg_tml`"
    try:
        rows = list(client.query(f"SELECT DISTINCT TRIM(CAST(taxonomy_code AS STRING)) AS taxonomy_code FROM {table} WHERE taxonomy_code IS NOT NULL AND TRIM(CAST(taxonomy_code AS STRING)) != ''").result())
        return {str(r.taxonomy_code).strip() for r in rows if r.taxonomy_code}
    except Exception as e:
        logger.warning("TML fetch failed: %s", e)
        return set()


def _location_zip9_set(locations: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """Return (zip5_set, zip9_set). Locations often only have zip5; zip9 only when site_zip9/zip_plus_4 present."""
    import re
    zip5_set: set[str] = set()
    zip9_set: set[str] = set()
    for loc in locations or []:
        zip5 = re.sub(r"[^0-9]", "", str(loc.get("site_zip5") or loc.get("site_zip") or ""))[:5]
        zip_plus = re.sub(r"[^0-9]", "", str(loc.get("site_zip9") or loc.get("zip_plus_4") or ""))[:4]
        if len(zip5) == 5:
            zip5_set.add(zip5)
            if zip_plus and len(zip_plus) == 4:
                zip9_set.add(zip5 + zip_plus)
            else:
                zip9_set.add(zip5 + "0000")  # padded for exact match to PML zip5+0000
    return (zip5_set, zip9_set)


def _is_pml_row_active(row: dict[str, Any]) -> bool:
    """PML row considered active: status or contract not ended."""
    status = (row.get("status") or "").lower()
    if "inactive" in status or "terminated" in status or "revoked" in status:
        return False
    end = row.get("contract_end_date")
    if end is not None:
        from datetime import date
        try:
            d = end if isinstance(end, date) else __import__("datetime").datetime.strptime(str(end)[:10], "%Y-%m-%d").date()
            if d < __import__("datetime").date.today():
                return False
        except Exception:
            pass
    return True


def validate_pml_rows(
    bq_client: Any,
    npis: list[str],
    locations: list[dict[str, Any]],
    *,
    project: str,
    landing_dataset: str,
    program_state: str = "FL",
    product: str = "medicaid",
    provider_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Step 6: PML validation.

    Extracts PML rows for NPIs, validates each:
    a) NPI in NPPES and active in PML and NPPES
    b) Taxonomy in TML and in NPPES
    c) ZIP is 9-digit and matches a location
    d) Medicaid ID present (if a,b,c pass)

    Returns:
      {
        "pml_rows": [...],
        "validated": [...],
        "flagged": [...],
        "summary": {"total": int, "valid": int, "flagged": int},
      }
    """
    pml_rows = _extract_pml_rows(
        bq_client, npis, project=project, landing_dataset=landing_dataset,
        program_state=program_state, product=product,
    )
    if not pml_rows:
        return {
            "pml_rows": [],
            "validated": [],
            "flagged": [],
            "summary": {"total": 0, "valid": 0, "flagged": 0},
        }
    nppes_status = _nppes_npi_status(bq_client, npis, project)
    tml_codes = _tml_codes(bq_client, project, landing_dataset)
    location_zip5_set, location_zip9_set = _location_zip9_set(locations)

    validated: list[dict[str, Any]] = []
    flagged: list[dict[str, Any]] = []

    name_fallback = provider_names or {}

    for row in pml_rows:
        npi = str(row.get("npi", "")).strip().zfill(10)
        provider_name = (row.get("provider_name") or "").strip()
        if not provider_name:
            provider_name = (name_fallback.get(npi) or "").strip()
        taxonomy = (row.get("taxonomy_code") or "").strip()
        zip9 = _normalize_zip9(row.get("zip"), row.get("zip_plus_4"))
        medicaid_id = (row.get("medicaid_provider_id") or "").strip()

        issues: list[str] = []
        recommendations: list[str] = []
        ns = nppes_status.get(npi, {"in_nppes": False, "active": False, "nppes_taxonomies": set()})

        # a) Valid NPI
        if not ns["in_nppes"]:
            issues.append("npi_not_in_nppes")
            recommendations.append(f"Provider {npi} ({provider_name or 'N/A'}) is not in NPPES. Please update.")
        elif not ns["active"]:
            issues.append("npi_deactivated_nppes")
            recommendations.append(f"Provider {npi} ({provider_name or 'N/A'}) is not active in NPPES. Please update.")
        elif not _is_pml_row_active(row):
            issues.append("npi_inactive_pml")
            recommendations.append(f"Provider {npi} ({provider_name or 'N/A'}) PML contract/status is inactive. Please update.")

        # b) Valid taxonomy (only if NPI checks passed)
        if not any(x.startswith("npi_") for x in issues):
            if not taxonomy:
                issues.append("taxonomy_missing")
                recommendations.append(f"Provider {npi}: No taxonomy on PML. Please add a taxonomy.")
            elif taxonomy not in tml_codes:
                issues.append("taxonomy_not_medicaid_approved")
                nppes_tax = ns.get("nppes_taxonomies") or set()
                approved_from_nppes = [t for t in nppes_tax if t in tml_codes]
                if approved_from_nppes:
                    rec = f"Provider {npi} taxonomy in PML is not Medicaid approved. Please consider using one of these (from NPPES): {', '.join(approved_from_nppes[:5])}."
                else:
                    rec = f"Provider {npi} taxonomy in PML ({taxonomy}) is not Medicaid approved. Please use a TML-approved taxonomy."
                recommendations.append(rec)
            elif taxonomy not in (ns.get("nppes_taxonomies") or set()):
                issues.append("taxonomy_not_in_nppes")
                recommendations.append(f"Provider {npi}: PML taxonomy {taxonomy} is not associated with NPPES. Please update NPPES or PML.")

        # c) Valid ZIP: PML must have 9 digits. Match = zip9 exact OR zip5 match (locations often only have zip5)
        if len(zip9) != 9:
            issues.append("zip_not_9_digits")
            if location_zip5_set or location_zip9_set:
                suggestions = list(location_zip5_set)[:3] or list(location_zip9_set)[:3]
                recommendations.append(f"Provider {npi} ZIP should be 9 digits. Please consider one of these location ZIPs: {', '.join(suggestions)}.")
            else:
                recommendations.append(f"Provider {npi} ZIP should be 9 digits.")
        elif location_zip5_set or location_zip9_set:
            zip5_match = zip9[:5] in location_zip5_set
            zip9_match = zip9 in location_zip9_set
            if not zip5_match and not zip9_match:
                issues.append("zip_mismatch_location")
                suggestions = list(location_zip5_set)[:3] or [z[:5] for z in list(location_zip9_set)[:3]]
                recommendations.append(f"Provider {npi} ZIP ({zip9}) does not match known locations (zip5). Please consider: {', '.join(suggestions)}.")

        # d) Medicaid ID (if a,b,c pass)
        if not issues and not medicaid_id:
            issues.append("medicaid_id_missing")
            recommendations.append(f"Provider {npi} has no Medicaid provider ID on file.")

        rec_text = " ".join(recommendations) if recommendations else ""
        out_row = {
            "npi": npi,
            "provider_name": provider_name,
            "taxonomy_code": taxonomy,
            "address_line_1": (row.get("address_line_1") or "")[:80],
            "city": row.get("city", ""),
            "state": row.get("state", ""),
            "zip": row.get("zip", ""),
            "zip_plus_4": row.get("zip_plus_4", ""),
            "zip9": zip9,
            "medicaid_provider_id": medicaid_id,
            "issues": issues,
            "recommendation": rec_text,
            "valid": len(issues) == 0,
        }
        if out_row["valid"]:
            validated.append(out_row)
        else:
            flagged.append(out_row)

    return {
        "pml_rows": pml_rows,
        "validated": validated,
        "flagged": flagged,
        "summary": {
            "total": len(pml_rows),
            "valid": len(validated),
            "flagged": len(flagged),
        },
    }
