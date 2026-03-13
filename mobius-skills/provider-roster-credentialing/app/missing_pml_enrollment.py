"""
Step 7: Missing PML enrollment — active roster providers not in PML.

For each active roster NPI with no PML rows:
- Suggested taxonomy: TML-approved from NPPES (primary/first match)
- Suggested location: from roster association (address, city, state, zip for enrollment)
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.core import TAXONOMY_CODE_LABELS

logger = logging.getLogger(__name__)


def _normalize_zip9(zip_val: str | None, zip_plus_4: str | None) -> str:
    digits = re.sub(r"[^0-9]", "", str(zip_val or "") + str(zip_plus_4 or ""))
    if len(digits) < 5:
        return ""
    if len(digits) >= 9:
        return digits[:9]
    return digits.ljust(9, "0")


def find_missing_pml_enrollment(
    bq_client: Any,
    active_roster: dict[str, list[dict[str, Any]]],
    locations: list[dict[str, Any]],
    *,
    project: str,
    landing_dataset: str,
    taxonomy_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Find active roster NPIs not in PML. For each: suggest taxonomy + location for enrollment.

    Returns:
      {
        "missing": [
          {
            "npi": str,
            "name": str,
            "entity_type": str,
            "location_id": str,
            "site_address_line_1": str,
            "site_city": str,
            "site_state": str,
            "site_zip5": str,
            "site_zip9": str,
            "suggested_taxonomy_code": str,
            "suggested_taxonomy_description": str,
            "nppes_taxonomies": list[str],
            "tml_approved": bool,
          },
          ...
        ],
        "summary": {"total": int},
      }
    """
    from app.pml_validation import (
        _extract_pml_rows,
        _nppes_npi_status,
        _tml_codes,
    )

    labels = taxonomy_labels or TAXONOMY_CODE_LABELS
    loc_by_id = {loc.get("location_id") or "": loc for loc in (locations or []) if loc.get("location_id")}

    # Collect active roster NPIs with (location_id, name, entity_type)
    roster_entries: list[tuple[str, str, str, str]] = []  # (npi, location_id, name, entity_type)
    for loc_id, provs in (active_roster or {}).items():
        for p in provs or []:
            npi = (p.get("npi") or p.get("servicing_npi") or "").strip().zfill(10)
            if not npi:
                continue
            name = (p.get("name") or p.get("provider_name") or "").strip()
            entity = str(p.get("entity_type") or "1").strip()
            roster_entries.append((npi, loc_id, name, entity))

    roster_npis = list(dict.fromkeys(n for n, _, _, _ in roster_entries))
    if not roster_npis or not landing_dataset:
        return {"missing": [], "summary": {"total": 0}}

    pml_rows = _extract_pml_rows(
        bq_client, roster_npis, project=project, landing_dataset=landing_dataset,
        program_state="FL", product="medicaid",
    )
    pml_npis = {str(r.get("npi", "")).strip().zfill(10) for r in pml_rows if r.get("npi")}
    nppes_status = _nppes_npi_status(bq_client, roster_npis, project)
    tml_codes = _tml_codes(bq_client, project, landing_dataset)

    missing_npis = {n for n, _, _, _ in roster_entries if n not in pml_npis}
    if not missing_npis:
        return {"missing": [], "summary": {"total": 0}}

    missing: list[dict[str, Any]] = []
    for npi, loc_id, name, entity in roster_entries:
        if npi not in missing_npis:
            continue

        loc = loc_by_id.get(loc_id) or {}
        addr = str(loc.get("site_address_line_1") or loc.get("site_address") or "").strip()
        city = str(loc.get("site_city") or "").strip()
        state = str(loc.get("site_state") or loc.get("state") or "FL").strip()
        zip5 = re.sub(r"[^0-9]", "", str(loc.get("site_zip5") or loc.get("site_zip") or ""))[:5]
        zip_plus = re.sub(r"[^0-9]", "", str(loc.get("site_zip9") or loc.get("zip_plus_4") or ""))[:4]
        zip9 = (zip5 + zip_plus) if len(zip5) == 5 and len(zip_plus) == 4 else (zip5 + "0000" if len(zip5) == 5 else "")

        ns = nppes_status.get(npi, {"nppes_taxonomies": set()})
        nppes_tax = ns.get("nppes_taxonomies") or set()
        approved = [t for t in nppes_tax if t in tml_codes]
        suggested_code = approved[0] if approved else (list(nppes_tax)[0] if nppes_tax else "")
        suggested_desc = labels.get(suggested_code, "") if suggested_code else ""
        tml_approved = bool(approved)

        missing.append({
            "npi": npi,
            "name": name,
            "entity_type": entity,
            "location_id": loc_id,
            "site_address_line_1": addr,
            "site_city": city,
            "site_state": state,
            "site_zip5": zip5,
            "site_zip9": zip9,
            "suggested_taxonomy_code": suggested_code,
            "suggested_taxonomy_description": suggested_desc,
            "nppes_taxonomies": ";".join(sorted(nppes_tax)) if nppes_tax else "",
            "tml_approved": tml_approved,
        })

    return {
        "missing": missing,
        "summary": {"total": len(missing)},
    }
