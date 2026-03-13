"""
Provider Roster / Credentialing report core logic.
Pure data + report building; no HTTP. Used by CLI and API.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Short labels for common taxonomy codes (NUCC). Fallback when nucc_taxonomy not in BQ.
# See: https://www.nucc.org, HL7 nuccProviderCodes. Run load_nucc_to_landing.py for full set.
TAXONOMY_CODE_LABELS: dict[str, str] = {
    "101Y00000X": "Counselor",
    "101YA0400X": "Addiction (Substance Use Disorder) Counselor",
    "101YM0800X": "Clinical Social Worker",
    "101YP1600X": "Pastoral Counselor",
    "101YP2500X": "Professional Counselor",
    "103G00000X": "Neuropsychologist",
    "103K00000X": "Behavioral Analyst",
    "103T00000X": "Psychologist",
    "103TA0400X": "Addiction (Substance Use Disorder) Psychologist",
    "103TB0200X": "Cognitive & Behavioral Psychologist",
    "103TC0700X": "Clinical Psychologist",
    "103TC1900X": "Counseling Psychologist",
    "103TC2200X": "Clinical Child & Adolescent Psychologist",
    "103TF0200X": "Family Psychologist",
    "103TH0004X": "Health Psychologist",
    "103TM1800X": "Intellectual & Developmental Disabilities Psychologist",
    "103TR0400X": "Rehabilitation Psychologist",
    "103TS0200X": "School Psychologist",
    "104100000X": "Social Worker",
    "1041C0700X": "Clinical Neuropsychologist",
    "106E00000X": "Assisted Living Facility",
    "106H00000X": "Hospice and Palliative Care",
    "106S00000X": "Marriage & Family Therapist",
    "111N00000X": "Chiropractor",
    "111NR0400X": "Rehabilitation Chiropractor",
    "111NS0005X": "Sports Physician Chiropractor",
    "111NX0800X": "Orthopedic Chiropractor",
    "122300000X": "Dental Hygienist",
    "1223D0001X": "Dental Public Health",
    "1223E0200X": "Pediatric Dental Hygienist",
    "1223G0001X": "Dental Hygienist (General Practice)",
    "1223P0106X": "Periodontics",
    "1223P0221X": "Pediatric Dentistry",
    "1223P0300X": "Periodontics",
    "1223P0700X": "Prosthodontics",
    "1223S0112X": "Oral and Maxillofacial Surgery",
    "1223X0400X": "Dental Hygienist (Endodontics)",
    "124Q00000X": "Dental Therapist",
    "126800000X": "Physical Therapy Assistant",
    "126900000X": "Rehabilitation Counselor",
    "133N00000X": "Nutritionist",
    "133V00000X": "Dietitian",
    "133VN1004X": "Nutrition, Pediatric",
    "133VN1005X": "Nutrition, Renal",
    "133VN1201X": "Nutrition, Metabolic",
    "146D00000X": "Personal Care Attendant",
    "146N00000X": "Emergency Medical Technician, Paramedic",
    "152W00000X": "Optometrist",
    "152WC0802X": "Corneal and Contact Management",
    "156FX1800X": "Ophthalmology",
    "163W00000X": "Registered Nurse",
    "163WC0200X": "Critical Care Medicine",
    "163WC0400X": "Case Management",
    "163WC1500X": "Community Health",
    "163WE0003X": "Emergency",
    "163WG0000X": "General Practice",
    "163WH0200X": "Home Health",
    "163WL0100X": "Lactation Consultant",
    "163WN0800X": "Neonatal, Critical Care",
    "163WP0808X": "Psych/Mental Health",
    "163WP0809X": "Psych/Mental Health, Adult",
    "163WP2201X": "Psych/Mental Health, Child & Family",
    "163WR0400X": "Rehabilitation",
    "163WS0200X": "School",
    "163WX0003X": "Obstetric, High-Risk",
    "163WX0200X": "Oncology",
    "164W00000X": "Licensed Practical Nurse",
    "164X00000X": "Licensed Vocational Nurse",
    "170300000X": "Legal Medicine",
    "171100000X": "Acupuncturist",
    "171400000X": "Health & Wellness Coach",
    "171M00000X": "Case Manager/Care Coordinator",
    "171W00000X": "Contractor",
    "172A00000X": "Driver",
    "172V00000X": "Driver",
    "174400000X": "Specialist",
    "1744P3200X": "Prosthetics Case Management",
    "174H00000X": "Health Educator",
    "174M00000X": "Veterinarian",
    "207P00000X": "Emergency Medicine",
    "207Q00000X": "Family Medicine",
    "207R00000X": "Internal Medicine",
    "207V00000X": "Obstetrics & Gynecology",
    "208000000X": "Pediatrics",
    "208D00000X": "General Practice",
    "222Q00000X": "Physical Therapist",
    "225X00000X": "Occupational Therapist",
    "235Z00000X": "Speech-Language Pathologist",
    "2355S0801X": "Speech-Language Pathologist, School",
    "251S00000X": "Community/Behavioral Health Agency",
    "390200000X": "Student in an Organized Health Care Program",
    "363A00000X": "Physician Assistant",
    "363L00000X": "Nurse Practitioner",
    "363LF0000X": "Family Nurse Practitioner",
}

# Canonical recommendation per problem type (readiness_status). Report is structured around these.
PROBLEM_TYPE_RECOMMENDATIONS: dict[str, str] = {
    "Invalid address": "Update service address to a valid 9-digit ZIP+4 so location matches state requirements.",
    "Taxonomy not permitted": "Recredential under an approved (TML) taxonomy; current code is not on the state-approved list.",
    "Combo mismatch": "Align NPI, taxonomy, and service location with state enrollment so the combination has a valid Medicaid ID.",
    "Not enrolled": "Complete Medicaid enrollment for these providers (NPI in PML with valid Medicaid ID).",
    "Needs review": "Review and resolve so combinations pass Medicaid NPI checks.",
}

# Four-tier confidence (Perfect / Good / Medium / Low) per business rules.
CONFIDENCE_DEFINITIONS: dict[str, str] = {
    "perfect": "Same address + ZIP9 + historic billing. Highest certainty; prioritize for action.",
    "good": "Historic billing + (ZIP9 OR address). Billing corroborates link; needs PML/combo work.",
    "medium": "Same address + ZIP9, no billing. Likely new joiners post-2024; verify onboarding.",
    "low": "Partial address only (ZIP5/street/city+state). Verify before acting.",
}


def _location_id(org_npi: str, site_address_line_1: str, site_city: str, site_state: str, site_zip: str, site_zip9: str) -> str:
    """Stable location_id from org_npi + address."""
    raw = "|".join(
        str(x) if x is not None else ""
        for x in (org_npi, site_address_line_1, site_city, site_state, site_zip, site_zip9)
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _normalize_addr(s: str) -> str:
    """Normalize address for matching: lowercase, collapse spaces."""
    if not s:
        return ""
    return " ".join(str(s).lower().split())


def _norm_key_for_match(addr: str, city: str, state: str, zip_val: str) -> str:
    """Produce match key using Google when available, else local normalizer."""
    from app.google_address_client import normalize_via_google, normalized_from_local
    norm = normalize_via_google(addr, city, state, zip_val)
    if norm is None:
        norm = normalized_from_local(addr, city, state, zip_val)
    return norm.street_zip_key()


def _locations_from_user_override(
    locations_override: list[dict[str, Any]],
    org_name: str,
    org_npi: str = "",
    l1_locations: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Convert user-validated locations (L2) into canonical location records with location_id.
    Each override item should have: site_address_line_1, site_city, site_state, site_zip; optional site_zip9.
    When l1_locations is provided, we match L2 to L1 using normalized addresses (Google when available, else local)
    so the L1 location_id is preserved. Uses street+zip key for matching.
    Adds match_source (l1_matched | l2_new), l1_address, l2_address for diagnostics.
    """
    from app.address_normalizer import extract_zip5

    out = []
    seen_ids: set[str] = set()
    l1_normalized: list[tuple[dict, str]] = []
    if l1_locations:
        for l1 in l1_locations:
            key = _norm_key_for_match(
                str(l1.get("site_address_line_1") or ""),
                str(l1.get("site_city") or ""),
                str(l1.get("site_state") or "FL"),
                str(l1.get("site_zip") or l1.get("site_zip9") or ""),
            )
            l1_normalized.append((l1, key))
    for loc in locations_override:
        addr = str(loc.get("site_address_line_1") or "").strip()
        city = str(loc.get("site_city") or "").strip()
        state = str(loc.get("site_state") or "FL").strip()
        zip5 = extract_zip5(loc.get("site_zip") or loc.get("site_zip9") or "")
        zip9 = str(loc.get("site_zip9") or "").strip()
        if not city or not state or not zip5:
            continue
        l2_key = _norm_key_for_match(addr, city, state, loc.get("site_zip") or zip5)
        l2_address = f"{addr}, {city}, {state} {zip5}".strip(", ")
        loc_id = _location_id(org_npi, addr, city, state, zip5, zip9)
        match_source = "l2_new"
        l1_address = ""
        matched_l1 = None
        for l1, l1_key in l1_normalized:
            if l1_key == l2_key:
                loc_id = l1["location_id"]
                addr = l1.get("site_address_line_1") or addr
                zip9 = l1.get("site_zip9") or zip9
                match_source = "l1_matched"
                matched_l1 = l1
                l1_addr = str(l1.get("site_address_line_1") or "").strip()
                l1_address = f"{l1_addr}, {l1.get('site_city')}, {l1.get('site_state')} {l1.get('site_zip')}".strip(", ")
                break
        if loc_id in seen_ids:
            continue
        seen_ids.add(loc_id)
        rec = {
            "org_npi": org_npi,
            "org_name": org_name,
            "site_address_line_1": addr,
            "site_city": city,
            "site_state": state,
            "site_zip": zip5,
            "site_zip9": zip9,
            "location_id": loc_id,
            "match_source": match_source,
            "l1_address": l1_address,
            "l2_address": l2_address,
            "site_source": matched_l1.get("site_source", "") if matched_l1 else "",
            "site_reason": matched_l1.get("site_reason", "") if matched_l1 else "",
        }
        out.append(rec)
    return out


def merge_locations_l1_l2(
    l1_locations: list[dict[str, Any]],
    locations_override: list[dict[str, Any]] | None,
    org_name: str,
) -> list[dict[str, Any]]:
    """
    Layer 3 = Universal truth: merge L1 (system-imputed) + L2 (user-validated).
    When locations_override is provided, it REPLACES L1 as the authoritative location list.
    L1 is used to infer org_npi and to match addresses so L1 location_ids (and thus NPIs) are preserved.
    L1-only locations get match_source='l1', l1_address set, l2_address=''.
    """
    if not locations_override:
        for loc in l1_locations:
            addr = str(loc.get("site_address_line_1") or "").strip()
            loc["match_source"] = "l1"
            loc["l1_address"] = f"{addr}, {loc.get('site_city')}, {loc.get('site_state')} {loc.get('site_zip')}".strip(", ")
            loc["l2_address"] = ""
        return l1_locations
    org_npi = (l1_locations[0].get("org_npi") or "") if l1_locations else ""
    return _locations_from_user_override(locations_override, org_name, org_npi, l1_locations)


def get_locations(
    bq_client: Any,
    org_name: str,
    project: str,
    marts_dataset: str,
    *,
    state_filter: str | None = "FL",
) -> list[dict[str, Any]]:
    """
    Get distinct locations for org name from bh_roster_sites.
    When state_filter is set (default FL), restrict to locations in that state to avoid name collision
    (e.g. Henderson FL vs Henderson NV). Returns list of dicts: org_npi, org_name, site_address_line_1,
    site_city, site_state, site_zip, site_zip9, location_id, site_source, site_reason.
    """
    table = f"`{project}.{marts_dataset}.bh_roster_sites`"
    state_clause = ""
    if state_filter:
        state_upper = state_filter.strip().upper()
        if state_upper == "FL":
            state_clause = " AND (UPPER(TRIM(COALESCE(site_state, ''))) IN ('FL', 'FLORIDA'))"
        else:
            state_clause = f" AND UPPER(TRIM(COALESCE(site_state, ''))) = '{state_upper}'"
    query = f"""
    SELECT
      org_npi,
      org_name,
      site_address_line_1,
      site_city,
      site_state,
      site_zip,
      site_zip9,
      site_source,
      site_reason
    FROM {table}
    WHERE LOWER(TRIM(COALESCE(org_name, ''))) LIKE LOWER(@org_pattern){state_clause}
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
            "site_source": str(r.get("site_source") or ""),
            "site_reason": str(r.get("site_reason") or ""),
        })
    return out


def get_npis_per_location(
    bq_client: Any,
    org_name: str,
    location_ids: list[str] | None,
    project: str,
    marts_dataset: str,
    npi_overrides: dict[str, dict[str, Any]] | None = None,
    *,
    state_filter: str | None = "FL",
) -> dict[str, list[dict[str, Any]]]:
    """
    For each location (optionally filtered by location_ids), get NPIs from bh_roster.
    npi_overrides: optional dict location_id -> { "add": [npi, ...], "remove": [npi, ...] }.
    Returns dict: location_id -> [ { servicing_npi, servicing_provider_name, provider_taxonomy_code, source_type, reconciliation } ].
    """
    table = f"`{project}.{marts_dataset}.bh_roster`"
    state_clause = ""
    if state_filter:
        state_upper = state_filter.strip().upper()
        if state_upper == "FL":
            state_clause = " AND (UPPER(TRIM(COALESCE(site_state, ''))) IN ('FL', 'FLORIDA'))"
        else:
            state_clause = f" AND UPPER(TRIM(COALESCE(site_state, ''))) = '{state_upper}'"
    query = f"""
    SELECT
      org_npi,
      org_name,
      site_address_line_1,
      site_city,
      site_state,
      site_zip,
      site_zip9,
      servicing_npi,
      servicing_provider_name,
      provider_taxonomy_code,
      source_type,
      confidence_score
    FROM {table}
    WHERE LOWER(TRIM(COALESCE(org_name, ''))) LIKE LOWER(@org_pattern){state_clause}
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
            "roster_org_npi": str(r.get("org_npi") or ""),
            "roster_org_name": str(r.get("org_name") or ""),
            "confidence_score": r.get("confidence_score"),
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


def get_npis_by_address(
    bq_client: Any,
    l2_locations: list[dict[str, Any]],
    project: str,
    marts_dataset: str,
    *,
    state_filter: str | None = "FL",
) -> dict[str, list[dict[str, Any]]]:
    """
    For L2 (user-validated) locations: find NPIs at those addresses in bh_roster by address match only (no org filter).
    User said these addresses belong to the org, so we use address as gospel.
    Matching: state required; then street+zip (strong) or zip only (partial). Uses Google Address Validation
    when available for normalization; falls back to local normalizer.
    Returns dict: location_id -> [ { servicing_npi, ... } ], sorted by match type (strong first).
    """
    from app.address_normalizer import extract_zip5
    from app.google_address_client import normalize_via_google, normalized_from_local, NormalizedAddress

    if not l2_locations:
        return {}
    table = f"`{project}.{marts_dataset}.bh_roster`"
    state_clause = ""
    if state_filter:
        state_upper = state_filter.strip().upper()
        if state_upper == "FL":
            state_clause = " AND (UPPER(TRIM(COALESCE(site_state, ''))) IN ('FL', 'FLORIDA'))"
        else:
            state_clause = f" AND UPPER(TRIM(COALESCE(site_state, ''))) = '{state_upper}'"
    city_zip_pairs = set()
    for loc in l2_locations:
        city = str(loc.get("site_city") or "").strip()
        zip5 = extract_zip5(loc.get("site_zip") or loc.get("site_zip9") or "")
        if city and zip5:
            city_zip_pairs.add((city.upper(), zip5))
    if not city_zip_pairs:
        return {}
    city_zip_conditions = " OR ".join(
        f"(LOWER(TRIM(COALESCE(site_city,''))) = LOWER(@c{i}) AND SUBSTR(REGEXP_REPLACE(COALESCE(site_zip, site_zip9, ''), r'[^0-9]', ''), 1, 5) = @z{i})"
        for i, (c, z) in enumerate(city_zip_pairs)
    )
    params = []
    for i, (c, z) in enumerate(city_zip_pairs):
        params.append(("c" + str(i), c))
        params.append(("z" + str(i), z))
    query = f"""
    SELECT
      org_npi,
      org_name,
      site_address_line_1,
      site_city,
      site_state,
      site_zip,
      site_zip9,
      servicing_npi,
      servicing_provider_name,
      provider_taxonomy_code,
      source_type,
      confidence_score
    FROM {table}
    WHERE ({city_zip_conditions}){state_clause}
    ORDER BY site_city, site_state, site_zip, servicing_npi
    """
    try:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        job_config = QueryJobConfig(
            query_parameters=[ScalarQueryParameter(k, "STRING", v) for k, v in params]
        )
    except ImportError:
        job_config = None
    rows = list(bq_client.query(query, job_config=job_config or {}).result())

    def _roster_rec(r: Any) -> dict[str, Any]:
        return {
            "servicing_npi": str(r.get("servicing_npi") or ""),
            "servicing_provider_name": str(r.get("servicing_provider_name") or ""),
            "provider_taxonomy_code": str(r.get("provider_taxonomy_code") or ""),
            "source_type": str(r.get("source_type") or ""),
            "reconciliation": "address_match",
            "roster_org_npi": str(r.get("org_npi") or ""),
            "roster_org_name": str(r.get("org_name") or ""),
            "confidence_score": r.get("confidence_score"),
        }

    # Group roster rows by (addr1, city, state, zip) to avoid duplicate Google calls
    roster_by_addr: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for r in rows:
        a1 = str(r.get("site_address_line_1") or "").strip()
        c = str(r.get("site_city") or "").strip()
        s = str(r.get("site_state") or "").strip()
        z = str(r.get("site_zip") or r.get("site_zip9") or "").strip()
        key = (a1, c, s, z)
        if key not in roster_by_addr:
            roster_by_addr[key] = []
        roster_by_addr[key].append(_roster_rec(r))

    # Normalize each L2 location (Google or local)
    l2_normalized: dict[str, NormalizedAddress] = {}
    for loc in l2_locations:
        lid = loc.get("location_id") or ""
        if not lid:
            continue
        addr = str(loc.get("site_address_line_1") or "").strip()
        city = str(loc.get("site_city") or "").strip()
        state = str(loc.get("site_state") or "FL").strip()
        zip_val = loc.get("site_zip") or loc.get("site_zip9") or ""
        if not city or not state or not extract_zip5(zip_val):
            continue
        norm = normalize_via_google(addr, city, state, str(zip_val))
        if norm is None:
            norm = normalized_from_local(addr, city, state, str(zip_val))
        l2_normalized[lid] = norm

    # Normalize each distinct roster address (Google or local); cache
    roster_norm_cache: dict[tuple[str, str, str, str], NormalizedAddress] = {}
    for (a1, c, s, z) in roster_by_addr:
        norm = normalize_via_google(a1, c, s, z)
        if norm is None:
            norm = normalized_from_local(a1, c, s, z)
        roster_norm_cache[(a1, c, s, z)] = norm

    # Match: state required; street+zip = strong, zip only = partial
    out: dict[str, list[dict[str, Any]]] = {}
    for lid, l2_norm in l2_normalized.items():
        strong: list[dict[str, Any]] = []
        partial: list[dict[str, Any]] = []
        seen_npis: set[str] = set()
        for (a1, c, s, z), recs in roster_by_addr.items():
            if not recs:
                continue
            r_norm = roster_norm_cache.get((a1, c, s, z))
            if not r_norm:
                continue
            def _state_key(s: str) -> str:
                u = (s or "").strip().upper()
                return "FL" if u in ("FL", "FLORIDA") else (u[:2] or "")

            if _state_key(r_norm.state) != _state_key(l2_norm.state):
                continue
            street_match = r_norm.street_zip_key() == l2_norm.street_zip_key()
            zip_match = r_norm.zip5 == l2_norm.zip5
            if street_match:
                for rec in recs:
                    npi = rec.get("servicing_npi") or ""
                    if npi and npi not in seen_npis:
                        seen_npis.add(npi)
                        strong.append(rec)
            elif zip_match:
                for rec in recs:
                    npi = rec.get("servicing_npi") or ""
                    if npi and npi not in seen_npis:
                        seen_npis.add(npi)
                        partial.append(rec)
        npis_list = strong + partial
        if npis_list:
            out[lid] = npis_list
    return out


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


def get_readiness_and_revenue_impact(
    bq_client: Any,
    org_npis: set[str],
    servicing_npis: set[str],
    project: str,
    marts_dataset: str,
) -> list[dict[str, Any]] | None:
    """
    Get bh_roster_revenue_impact rows (readiness + est_revenue_low/mid/high).
    Returns list of dicts with all readiness columns plus est_revenue_low, est_revenue_mid,
    est_revenue_high, revenue_source, is_deprecated_taxonomy.
    Returns None if the table does not exist (dbt not run yet).
    """
    if not servicing_npis:
        return []
    table = f"`{project}.{marts_dataset}.bh_roster_revenue_impact`"
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
      suggested_taxonomies,
      est_revenue_low,
      est_revenue_mid,
      est_revenue_high,
      revenue_source,
      is_deprecated_taxonomy,
      assumed_beneficiaries_per_provider
    FROM {table}
    WHERE servicing_npi IN ({npis_list})
    ORDER BY org_npi, servicing_npi
    """
    try:
        rows = list(bq_client.query(query).result())
    except Exception as e:
        logger.debug("get_readiness_and_revenue_impact failed (run dbt: bh_roster_revenue_impact): %s", e)
        return None
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


def _compute_org_run_rates_by_taxonomy(
    run_rate_by_taxonomy_location: list[dict[str, Any]],
) -> dict[tuple[str, str], tuple[float, float]]:
    """
    From cell-level run rates, compute per (taxonomy, org_npi): (avg, high).
    avg = mean run rate across locations; high = 75th percentile.
    """
    from collections import defaultdict
    import math
    cell_rates: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in run_rate_by_taxonomy_location:
        tax = str(row.get("provider_taxonomy_code") or "").strip()
        org = str(row.get("org_npi") or "").strip()
        rate = float(row.get("run_rate_per_physician") or 0)
        if tax and org:
            cell_rates[(tax, org)].append(rate)
    out: dict[tuple[str, str], tuple[float, float]] = {}
    for (tax, org), rates in cell_rates.items():
        if not rates:
            continue
        avg = sum(rates) / len(rates)
        sorted_rates = sorted(rates)
        idx = max(0, int(math.ceil(0.75 * len(sorted_rates))) - 1)
        high = sorted_rates[idx] if sorted_rates else 0.0
        out[(tax, org)] = (round(avg, 2), round(high, 2))
    return out


def get_run_rate_by_taxonomy_state(
    bq_client: Any,
    project: str,
    marts_dataset: str,
    landing_dataset: str,
    state: str = "FL",
    year: int = 2024,
) -> dict[str, float]:
    """
    State-wide avg run rate per physician by taxonomy (no location).
    Used as fallback when org has no billing for a taxonomy.
    """
    table_readiness = f"`{project}.{marts_dataset}.bh_roster_readiness`"
    table_doge = f"`{project}.{landing_dataset}.stg_doge`"
    state_upper = state.strip().upper()
    state_cond = "UPPER(TRIM(COALESCE(site_state, ''))) IN ('FL', 'FLORIDA')" if state_upper == "FL" else f"UPPER(TRIM(COALESCE(site_state, ''))) = '{state_upper}'"
    year_str = str(year)
    query = f"""
    WITH doge_yr AS (
      SELECT
        billing_npi,
        servicing_npi,
        SUM(COALESCE(total_paid, 0)) AS total_paid
      FROM {table_doge}
      WHERE servicing_npi IS NOT NULL AND TRIM(servicing_npi) != ''
        AND SUBSTR(SAFE_CAST(period_month AS STRING), 1, 4) = @year
      GROUP BY billing_npi, servicing_npi
    ),
    roster_cell AS (
      SELECT
        provider_taxonomy_code,
        org_npi,
        servicing_npi
      FROM {table_readiness}
      WHERE {state_cond}
        AND provider_taxonomy_code IS NOT NULL AND TRIM(CAST(provider_taxonomy_code AS STRING)) != ''
    ),
    cell_npi_paid AS (
      SELECT
        r.provider_taxonomy_code,
        r.org_npi,
        r.servicing_npi,
        COALESCE(SUM(d.total_paid), 0) AS npi_paid
      FROM roster_cell r
      LEFT JOIN doge_yr d ON r.servicing_npi = d.servicing_npi AND r.org_npi = d.billing_npi
      GROUP BY r.provider_taxonomy_code, r.org_npi, r.servicing_npi
    ),
    by_taxonomy AS (
      SELECT
        provider_taxonomy_code,
        SUM(npi_paid) AS total_paid_2024,
        COUNT(DISTINCT servicing_npi) AS physician_count
      FROM cell_npi_paid
      GROUP BY provider_taxonomy_code
      HAVING COUNT(DISTINCT servicing_npi) > 0
    )
    SELECT
      provider_taxonomy_code,
      total_paid_2024 / physician_count AS run_rate_avg
    FROM by_taxonomy
    """
    try:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        job_config = QueryJobConfig(
            query_parameters=[ScalarQueryParameter("year", "STRING", year_str)]
        )
        rows = list(bq_client.query(query, job_config=job_config).result())
    except Exception as e:
        logger.warning("get_run_rate_by_taxonomy_state failed: %s", e)
        return {}
    return {
        str(r.get("provider_taxonomy_code") or "").strip(): round(float(r.get("run_rate_avg") or 0), 2)
        for r in rows
        if (r.get("provider_taxonomy_code") or "").strip()
    }


def _build_top_recommendations_by_code(
    revenue_by_taxonomy: list[dict[str, Any]],
    invalid_combos: list[dict[str, Any]],
    top_n: int = 3,
) -> list[dict[str, Any]]:
    """
    Build top N taxonomy-level recommendations for the summary section.
    Each item: provider_taxonomy_code, taxonomy_description (label), recommendation, revenue_at_risk_2024, invalid_combo_count.
    Recommendation is synthesized from dominant readiness_status, is_deprecated_taxonomy, and suggested_action.
    """
    from collections import Counter, defaultdict

    if not revenue_by_taxonomy or not invalid_combos:
        return []
    # Top taxonomies by revenue (already sorted)
    top_tax_codes = [t["provider_taxonomy_code"] for t in revenue_by_taxonomy[:top_n]]
    rev_by_tax = {t["provider_taxonomy_code"]: t["revenue_at_risk_2024"] for t in revenue_by_taxonomy}

    # Group invalid combos by taxonomy
    by_tax: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in invalid_combos:
        tax = str(r.get("provider_taxonomy_code") or "").strip()
        if tax:
            by_tax[tax].append(r)

    out: list[dict[str, Any]] = []
    for tax in top_tax_codes:
        rows = by_tax.get(tax, [])
        if not rows:
            continue
        status_counts = Counter(str(r.get("readiness_status") or "Needs review").strip() for r in rows)
        dominant_status = status_counts.most_common(1)[0][0] if status_counts else "Needs review"
        deprecated_any = any(r.get("is_deprecated_taxonomy") for r in rows)
        suggested_actions = [r.get("suggested_action") for r in rows if r.get("suggested_action")]
        first_suggested = (suggested_actions[0] or "").strip() if suggested_actions else ""

        # Synthesize recommendation
        if deprecated_any:
            rec = "Recredential under an approved (TML) taxonomy; this code is not on the state-approved list."
        elif first_suggested and len(first_suggested) < 200:
            rec = first_suggested
        elif dominant_status == "Combo mismatch":
            rec = "Align NPI, taxonomy, and service location with state enrollment so the combination has a valid Medicaid ID."
        elif dominant_status == "Not enrolled":
            rec = "Complete Medicaid enrollment for these providers (NPI in PML with valid Medicaid ID)."
        elif dominant_status == "Invalid address":
            rec = "Update service address to a valid 9-digit ZIP+4 so location matches state requirements."
        else:
            rec = f"Resolve {dominant_status} so combinations pass Medicaid NPI checks."

        out.append({
            "provider_taxonomy_code": tax,
            "taxonomy_description": TAXONOMY_CODE_LABELS.get(tax) or tax,
            "recommendation": rec,
            "revenue_at_risk_2024": round(rev_by_tax.get(tax, 0), 2),
            "invalid_combo_count": len(rows),
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
    run_rate_by_taxonomy_state: dict[str, float] | None = None,
    state_filter: str = "FL",
    *,
    primary_org_npis: set[str] | None = None,
) -> dict[str, Any]:
    """Build executive summary dict: org_name, org_npis, counts, readiness_status_breakdown, next_steps, revenue_at_risk_2024."""
    org_npis = {loc["org_npi"] for loc in locations if loc.get("org_npi")}
    primary = primary_org_npis or org_npis
    all_npis = set()
    for nlist in npis_per_location.values():
        for n in nlist:
            all_npis.add(n.get("servicing_npi") or "")
    all_npis.discard("")
    npis_with_readiness = {r["servicing_npi"] for r in readiness_rows}
    npis_no_readiness = all_npis - npis_with_readiness
    npis_org_misaligned: set[str] = set()
    for r in readiness_rows:
        row_org = str(r.get("org_npi") or "").strip()
        if row_org and row_org not in primary:
            npis_org_misaligned.add(r.get("servicing_npi") or "")
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

    # Revenue at risk: prefer dbt bh_roster_revenue_impact (est_revenue_low/mid/high per row).
    # Fallback: taxonomy-level run rate (org avg/high, fallback to state avg) × NPIs.
    revenue_at_risk_2024: float = 0.0
    revenue_at_risk_2024_low: float = 0.0
    revenue_at_risk_2024_high: float = 0.0
    deprecated_taxonomy_revenue: float = 0.0
    if invalid_combos and invalid_combos[0].get("est_revenue_mid") is not None:
        # From dbt bh_roster_revenue_impact
        for r in invalid_combos:
            revenue_at_risk_2024 += float(r.get("est_revenue_mid") or 0)
            revenue_at_risk_2024_low += float(r.get("est_revenue_low") or 0)
            revenue_at_risk_2024_high += float(r.get("est_revenue_high") or 0)
            if r.get("is_deprecated_taxonomy"):
                deprecated_taxonomy_revenue += float(r.get("est_revenue_mid") or 0)
        revenue_by_status: dict[str, float] = {}
        revenue_by_confidence: dict[str, float] = {"perfect": 0.0, "good": 0.0, "medium": 0.0, "low": 0.0}
        for r in invalid_combos:
            status = str(r.get("readiness_status") or "Needs review").strip()
            revenue_by_status[status] = revenue_by_status.get(status, 0.0) + float(r.get("est_revenue_mid") or 0)
            score = r.get("confidence_score")
            conf = (
                "perfect" if score is not None and score >= 90
                else "good" if score is not None and score >= 70
                else "medium" if score is not None and score >= 50
                else "low"
            )
            revenue_by_confidence[conf] = revenue_by_confidence.get(conf, 0.0) + float(r.get("est_revenue_mid") or 0)
        revenue_at_risk_2024_by_status = {s: round(v, 2) for s, v in revenue_by_status.items()}
        revenue_at_risk_2024_by_confidence = {c: round(v, 2) for c, v in revenue_by_confidence.items()}
    elif invalid_combos:
        from collections import defaultdict
        org_rates = _compute_org_run_rates_by_taxonomy(run_rate_by_taxonomy_location or [])
        state_rates = run_rate_by_taxonomy_state or {}
        # Dedupe by (taxonomy, org_npi, servicing_npi)
        cell_to_npis: dict[tuple[str, str], set[str]] = defaultdict(set)
        for r in invalid_combos:
            tax = str(r.get("provider_taxonomy_code") or "").strip()
            org = str(r.get("org_npi") or "").strip()
            npi = str(r.get("servicing_npi") or "").strip()
            if tax and org and npi:
                cell_to_npis[(tax, org)].add(npi)
        for (tax, org), npis in cell_to_npis.items():
            rate_avg = 0.0
            rate_high = 0.0
            if (tax, org) in org_rates:
                o_avg, o_high = org_rates[(tax, org)]
                if o_avg > 0 or o_high > 0:
                    rate_avg, rate_high = o_avg, o_high
            if rate_avg == 0 and rate_high == 0 and tax in state_rates:
                rate_avg = rate_high = state_rates[tax]
            revenue_at_risk_2024 += len(npis) * rate_avg
            revenue_at_risk_2024_high += len(npis) * rate_high
        revenue_at_risk_2024_low = revenue_at_risk_2024  # run-rate path: single point estimate used as low

        # Revenue at risk by readiness status and confidence (per NPI, taxonomy+org cell)
        revenue_by_status: dict[str, float] = {}
        revenue_by_confidence: dict[str, float] = {"perfect": 0.0, "good": 0.0, "medium": 0.0, "low": 0.0}
        seen: set[tuple[str, str, str]] = set()
        for r in invalid_combos:
            tax = str(r.get("provider_taxonomy_code") or "").strip()
            org = str(r.get("org_npi") or "").strip()
            npi = str(r.get("servicing_npi") or "").strip()
            if not npi or (tax, org, npi) in seen:
                continue
            seen.add((tax, org, npi))
            rate_avg = 0.0
            if (tax, org) in org_rates and org_rates[(tax, org)][0] > 0:
                rate_avg = org_rates[(tax, org)][0]
            elif tax in state_rates:
                rate_avg = state_rates[tax]
            status = str(r.get("readiness_status") or "Needs review").strip()
            revenue_by_status[status] = revenue_by_status.get(status, 0.0) + rate_avg
            score = r.get("confidence_score")
            conf = (
                "perfect" if score is not None and score >= 90
                else "good" if score is not None and score >= 70
                else "medium" if score is not None and score >= 50
                else "low"
            )
            revenue_by_confidence[conf] = revenue_by_confidence.get(conf, 0.0) + rate_avg
        revenue_at_risk_2024_by_status = {s: round(v, 2) for s, v in revenue_by_status.items()}
        revenue_at_risk_2024_by_confidence = {c: round(v, 2) for c, v in revenue_by_confidence.items()}
    else:
        revenue_at_risk_2024_by_status = {}
        revenue_at_risk_2024_by_confidence = {}

    # Recommendations by problem type: quantify (count, revenue) + recommend per type. Report is centered on this.
    recommendations_by_problem_type: list[dict[str, Any]] = []
    for status, count in (status_counts or {}).items():
        if status == "Ready" or not count:
            continue
        rev = float((revenue_at_risk_2024_by_status or {}).get(status, 0) or 0)
        rec = PROBLEM_TYPE_RECOMMENDATIONS.get(status, "Resolve so combinations pass Medicaid NPI checks.")
        recommendations_by_problem_type.append({
            "problem_type": status,
            "invalid_combo_count": count,
            "revenue_at_risk_2024": round(rev, 2),
            "recommendation": rec,
        })
    recommendations_by_problem_type.sort(
        key=lambda x: (-x["revenue_at_risk_2024"], -x["invalid_combo_count"])
    )

    # Opportunity × Confidence matrix: for each problem type, counts and revenue by confidence band (perfect / good / medium / low).
    from collections import defaultdict
    _bands = ("perfect", "good", "medium", "low")
    matrix_by_type: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {b: {"count": 0, "revenue": 0.0} for b in _bands}
    )
    for r in invalid_combos:
        status = str(r.get("readiness_status") or "Needs review").strip()
        if status == "Ready":
            continue
        score = r.get("confidence_score")
        conf = (
            "perfect" if score is not None and score >= 90
            else "good" if score is not None and score >= 70
            else "medium" if score is not None and score >= 50
            else "low"
        )
        rev = float(r.get("est_revenue_mid") or r.get("est_revenue_high") or 0)
        if rev <= 0 and revenue_at_risk_2024 > 0:
            rev = revenue_at_risk_2024 / len(invalid_combos)
        matrix_by_type[status][conf]["count"] += 1
        matrix_by_type[status][conf]["revenue"] += rev
    opportunity_confidence_matrix: list[dict[str, Any]] = []
    for problem_type in (recommendations_by_problem_type or []):
        pt = problem_type.get("problem_type")
        if not pt or pt not in matrix_by_type:
            continue
        m = matrix_by_type[pt]
        high_count = m["perfect"]["count"] + m["good"]["count"]
        high_revenue = round(m["perfect"]["revenue"] + m["good"]["revenue"], 2)
        opportunity_confidence_matrix.append({
            "problem_type": pt,
            "perfect_count": m["perfect"]["count"],
            "perfect_revenue": round(m["perfect"]["revenue"], 2),
            "good_count": m["good"]["count"],
            "good_revenue": round(m["good"]["revenue"], 2),
            "high_count": high_count,
            "high_revenue": high_revenue,
            "medium_count": m["medium"]["count"],
            "medium_revenue": round(m["medium"]["revenue"], 2),
            "low_count": m["low"]["count"],
            "low_revenue": round(m["low"]["revenue"], 2),
        })

    # Revenue breakdown by location and taxonomy (when revenue > 0), plus assumptions for translation
    revenue_by_location: list[dict[str, Any]] = []
    revenue_by_taxonomy: list[dict[str, Any]] = []
    revenue_assumptions: dict[str, Any] = {}
    if revenue_at_risk_2024 > 0 and invalid_combos:
        from collections import defaultdict
        by_loc: dict[tuple[str, str, str], float] = defaultdict(float)
        by_tax: dict[str, float] = defaultdict(float)
        ben_values: list[float] = []
        for r in invalid_combos:
            mid = float(r.get("est_revenue_mid") or r.get("est_revenue_high") or 0)  # fallback for run-rate path
            if mid <= 0:
                continue
            loc_key = (str(r.get("org_name") or "").strip(), str(r.get("site_city") or "").strip(), str(r.get("site_state") or "").strip())
            by_loc[loc_key] += mid
            tax = str(r.get("provider_taxonomy_code") or "").strip()
            if tax:
                by_tax[tax] += mid
            b = r.get("assumed_beneficiaries_per_provider")
            if b is not None:
                try:
                    ben_values.append(float(b))
                except (TypeError, ValueError):
                    pass
        revenue_by_location = [
            {"org_name": k[0], "site_city": k[1], "site_state": k[2], "revenue_at_risk_2024": round(v, 2)}
            for k, v in sorted(by_loc.items(), key=lambda x: -x[1])[:20]
        ]
        revenue_by_taxonomy = [
            {"provider_taxonomy_code": k, "revenue_at_risk_2024": round(v, 2)}
            for k, v in sorted(by_tax.items(), key=lambda x: -x[1])[:20]
        ]
        formula = "est_revenue = assumed_beneficiaries_per_provider × revenue_per_beneficiary (state median by taxonomy)"
        if invalid_combos[0].get("est_revenue_mid") is not None:
            source = "dbt bh_roster_revenue_impact (fl_medicaid_taxonomy_revenue_rates)"
        else:
            source = "state run rate per physician by taxonomy (org fallback when available)"
        revenue_assumptions = {
            "formula": formula,
            "source": source,
            "assumed_beneficiaries_per_provider": "state median by taxonomy (FL DOGE 2024)",
            "revenue_per_beneficiary": "state p25/p50/p75 by taxonomy (conservative/mid/high)",
        }
        if ben_values:
            revenue_assumptions["assumed_beneficiaries_range"] = {
                "min": round(min(ben_values), 2),
                "max": round(max(ben_values), 2),
                "approx_median": round(sorted(ben_values)[len(ben_values) // 2], 2),
            }
        total_with_rev = len([r for r in invalid_combos if float(r.get("est_revenue_mid") or r.get("est_revenue_high") or 0) > 0])
        revenue_assumptions["total_invalid_combos_with_revenue"] = total_with_rev
        if ben_values:
            revenue_assumptions["total_assumed_beneficiaries"] = round(sum(ben_values), 0)

    # Top 3 recommendations by code (biggest revenue-impact taxonomies + actionable recommendation)
    top_recommendations_by_code: list[dict[str, Any]] = []
    if revenue_by_taxonomy and invalid_combos and revenue_at_risk_2024 > 0:
        top_recommendations_by_code = _build_top_recommendations_by_code(
            revenue_by_taxonomy, invalid_combos, top_n=3
        )

    # Confidence breakdown for invalid combos (four-tier: perfect >=90, good 70-89, medium 50-69, low <50 or missing)
    confidence_breakdown = {
        "perfect": sum(1 for r in invalid_combos if (r.get("confidence_score") or 0) >= 90),
        "good": sum(1 for r in invalid_combos if 70 <= (r.get("confidence_score") or 0) < 90),
        "medium": sum(1 for r in invalid_combos if 50 <= (r.get("confidence_score") or 0) < 70),
        "low": sum(1 for r in invalid_combos if (r.get("confidence_score") or 0) < 50 or r.get("confidence_score") is None),
    }
    # High-confidence exposure = perfect + good (for exec summary)
    confidence_high = confidence_breakdown["perfect"] + confidence_breakdown["good"]

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

    # Worked example: one NPI/taxonomy showing revenue estimate (dbt est_revenue_mid or run rate)
    worked_example: dict[str, Any] | None = None
    if invalid_combos:
        if invalid_combos[0].get("est_revenue_mid") is not None:
            for r in invalid_combos[:50]:
                mid = float(r.get("est_revenue_mid") or 0)
                if mid > 0:
                    worked_example = {
                        "servicing_npi": r.get("servicing_npi"),
                        "servicing_provider_name": r.get("servicing_provider_name") or "(unnamed)",
                        "provider_taxonomy_code": r.get("provider_taxonomy_code"),
                        "site_city": r.get("site_city"),
                        "site_state": r.get("site_state"),
                        "site_zip": r.get("site_zip"),
                        "run_rate_per_physician": round(mid, 2),
                        "annual_estimate": round(mid, 2),
                        "explanation": "Estimated annual revenue impact from dbt (state per-beneficiary rate × beneficiaries per provider for this taxonomy).",
                    }
                    break
        else:
            org_rates = _compute_org_run_rates_by_taxonomy(run_rate_by_taxonomy_location or [])
            state_rates = run_rate_by_taxonomy_state or {}
            for r in invalid_combos[:50]:
                tax = str(r.get("provider_taxonomy_code") or "").strip()
                org = str(r.get("org_npi") or "").strip()
                rate = 0.0
                source = ""
                if (tax, org) in org_rates and org_rates[(tax, org)][0] > 0:
                    rate = org_rates[(tax, org)][0]
                    source = "org average"
                elif tax in state_rates:
                    rate = state_rates[tax]
                    source = f"{state_filter} state average"
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
                        "explanation": f"Annual Medicaid run rate for this taxonomy ({source}) from 2024 DOGE; applied to this provider.",
                    }
                    break

    result = {
        "org_name": org_name,
        "org_npis": list(org_npis),
        "methodology_overview": "Locations from roster; NPIs per location with reconciliation; four Medicaid NPI checks per NPI and per (NPI, taxonomy, ZIP9) combo; invalid combos, missed opportunities, ghost billing (DOGE).",
        "location_count": len(locations),
        "total_npis": len(all_npis),
        "npis_with_readiness": len(npis_with_readiness),
        "npis_no_readiness": len(npis_no_readiness),
        "npis_org_misaligned": len(npis_org_misaligned),
        "npis_all_checks_pass": len(ready_npis),
        "npis_at_least_one_fail": len(fail_npis),
        "invalid_combo_count": len(invalid_combos),
        "ghost_billing_claim_count": ghost_claims,
        "ghost_billing_total_paid": ghost_paid,
        "ghost_billing_npi_count": len(ghost_billing),
        "readiness_status_breakdown": status_counts,
        "next_steps": "; ".join(next_steps) if next_steps else "No critical issues.",
        "revenue_at_risk_2024": round(revenue_at_risk_2024, 2),
        "revenue_at_risk_2024_low": round(revenue_at_risk_2024_low, 2),
        "revenue_at_risk_2024_high": round(revenue_at_risk_2024_high, 2),
        "deprecated_taxonomy_revenue": round(deprecated_taxonomy_revenue, 2),
        "billing_impact_note": (
            "Based on dbt bh_roster_revenue_impact: per-beneficiary rate (p25/p50/p75) × beneficiaries per provider by taxonomy."
            if (revenue_at_risk_2024 and invalid_combos and invalid_combos[0].get("est_revenue_mid") is not None)
            else "Based on 2024 DOGE run rate per physician by taxonomy (org avg/high; fallback to state avg). Ignores location." if (revenue_at_risk_2024 or revenue_at_risk_2024_high) else None
        ),
        "revenue_at_risk_2024_by_status": revenue_at_risk_2024_by_status if revenue_at_risk_2024 else {},
        "revenue_at_risk_2024_by_confidence": revenue_at_risk_2024_by_confidence if revenue_at_risk_2024 else {},
        "confidence_breakdown": confidence_breakdown,
        "readiness_score": int(readiness_score),
        "estimated_missed_opportunities_revenue_20pct": estimated_missed_opportunities_revenue_20pct,
        "worked_example": worked_example,
        "revenue_by_location": revenue_by_location,
        "revenue_by_taxonomy": revenue_by_taxonomy,
        "revenue_assumptions": revenue_assumptions,
        "top_recommendations_by_code": top_recommendations_by_code,
        "recommendations_by_problem_type": recommendations_by_problem_type,
        "opportunity_confidence_matrix": opportunity_confidence_matrix,
        "confidence_definitions": CONFIDENCE_DEFINITIONS,
    }
    return result


def _why_belongs(reconciliation: str, source_type: str, roster_org_name: str) -> str:
    """Synthesize human-readable 'why we think this NPI belongs to this org'."""
    if reconciliation == "user_added":
        return "Manually added by user."
    if reconciliation == "system":
        return "System roster: org and location match from bh_roster (PML/NPPES/billing)."
    if reconciliation == "address_match":
        org = (roster_org_name or "").strip()
        if org:
            return f"Address match at L2 location; roster shows org: {org}."
        return "Address match at L2 location (user validated these addresses)."
    return f"Roster source: {source_type or 'unknown'}."


def _fetch_taxonomy_labels_from_bq(
    bq_client: Any,
    project: str,
    marts_dataset: str,
    codes: list[str],
) -> dict[str, str]:
    """Fetch taxonomy_code -> taxonomy_description from nucc_taxonomy mart. Returns empty dict on failure."""
    if not codes:
        return {}
    table = f"`{project}.{marts_dataset}.nucc_taxonomy`"
    codes_safe = [c.replace("'", "\\'") for c in codes[:2000]]  # limit for query
    codes_list = ",".join(repr(c) for c in codes_safe)
    query = f"""
    SELECT taxonomy_code, taxonomy_description
    FROM {table}
    WHERE taxonomy_code IN ({codes_list})
    """
    try:
        rows = list(bq_client.query(query).result())
        return {str(r.get("taxonomy_code") or ""): str(r.get("taxonomy_description") or "") for r in rows if r.get("taxonomy_code")}
    except Exception as e:
        logger.debug("nucc_taxonomy lookup failed (table may not exist): %s", e)
        return {}


def _build_primary_report(
    locations: list[dict[str, Any]],
    npis_per_location: dict[str, list[dict[str, Any]]],
    combos: list[dict[str, Any]],
    *,
    taxonomy_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Build primary report: locations, distinct NPIs (with why they belong), taxonomies covered, billing activity.
    This is the simple sheet to show first before the detailed report.
    """
    # 1. Locations
    loc_list = [
        {
            "site_address_line_1": loc.get("site_address_line_1"),
            "site_city": loc.get("site_city"),
            "site_state": loc.get("site_state"),
            "site_zip": loc.get("site_zip"),
            "match_source": loc.get("match_source", "l1"),
            "site_source": loc.get("site_source", ""),
            "site_reason": loc.get("site_reason", ""),
        }
        for loc in locations
    ]

    # NPI -> max confidence from combos and roster (confidence indicates strength of roster attribution)
    npi_confidence: dict[str, int | float] = {}
    for r in combos:
        npi = str(r.get("servicing_npi") or "").strip()
        if not npi:
            continue
        score = r.get("confidence_score")
        if score is not None:
            try:
                v = int(score) if isinstance(score, (int, float)) else int(float(score))
                npi_confidence[npi] = max(npi_confidence.get(npi, 0), v)
            except (ValueError, TypeError):
                pass
    # Merge roster confidence from npis_per_location (for NPIs not in readiness / different org)
    for _lid, nlist in npis_per_location.items():
        for n in nlist:
            npi = str(n.get("servicing_npi") or "").strip()
            if not npi:
                continue
            score = n.get("confidence_score")
            if score is not None:
                try:
                    v = int(score) if isinstance(score, (int, float)) else int(float(score))
                    npi_confidence[npi] = max(npi_confidence.get(npi, 0), v)
                except (ValueError, TypeError):
                    pass

    def _confidence_band(score: int | float | None) -> str:
        """Four-tier: perfect | good | medium | low (per business rules)"""
        if score is None:
            return "low"
        s = int(score)
        if s >= 90:
            return "perfect"
        if s >= 70:
            return "good"
        if s >= 50:
            return "medium"
        return "low"

    # 2. Distinct NPIs with why we think they belong + confidence
    npi_to_info: dict[str, dict[str, Any]] = {}
    for _lid, nlist in npis_per_location.items():
        for n in nlist:
            npi = n.get("servicing_npi") or ""
            if not npi:
                continue
            rec = n.get("reconciliation") or "system"
            src = n.get("source_type") or ""
            org = n.get("roster_org_name") or ""
            why = _why_belongs(rec, src, org)
            if npi not in npi_to_info:
                npi_to_info[npi] = {
                    "servicing_npi": npi,
                    "servicing_provider_name": n.get("servicing_provider_name") or "",
                    "why_belongs": [why],
                    "roster_org_names": {org} if org else set(),
                }
            else:
                if why not in npi_to_info[npi]["why_belongs"]:
                    npi_to_info[npi]["why_belongs"].append(why)
                if org:
                    npi_to_info[npi]["roster_org_names"].add(org)
    distinct_npis = []
    for x in npi_to_info.values():
        score = npi_confidence.get(x["servicing_npi"])
        band = _confidence_band(score)
        roster_orgs = sorted((o for o in (x.get("roster_org_names") or set()) if o))
        distinct_npis.append({
            "servicing_npi": x["servicing_npi"],
            "servicing_provider_name": x["servicing_provider_name"],
            "why_belongs": "; ".join(dict.fromkeys(x["why_belongs"])),  # dedupe order-preserving
            "confidence_score": score,
            "confidence_band": band,
            "roster_org_names": " | ".join(roster_orgs) if roster_orgs else "",
        })

    # 3. Taxonomies covered (from combos)
    tax_codes: set[str] = set()
    for r in combos:
        t = (r.get("provider_taxonomy_code") or "").strip()
        if t:
            tax_codes.add(t)
    taxonomies_covered = sorted(tax_codes)
    labels = dict(TAXONOMY_CODE_LABELS)
    if taxonomy_labels:
        labels.update(taxonomy_labels)
    tax_labels = {t: (labels.get(t) or t) for t in taxonomies_covered}
    taxonomies = [{"code": t, "label": tax_labels[t]} for t in taxonomies_covered]

    # 4. Billing activity (claims, paid by taxonomy from combos)
    tax_claims: dict[str, int] = {}
    tax_paid: dict[str, float] = {}
    for r in combos:
        t = (r.get("provider_taxonomy_code") or "").strip() or "(unknown)"
        tax_claims[t] = tax_claims.get(t, 0) + int(r.get("claim_count") or 0)
        tax_paid[t] = tax_paid.get(t, 0.0) + float(r.get("total_paid") or 0)
    billing_activity = [
        {
            "provider_taxonomy_code": t,
            "taxonomy_label": labels.get(t, t),
            "claim_count": tax_claims.get(t, 0),
            "total_paid": round(tax_paid.get(t, 0), 2),
        }
        for t in sorted(tax_claims.keys())
    ]

    return {
        "locations": loc_list,
        "distinct_npis": distinct_npis,
        "taxonomies_covered": taxonomies,
        "billing_activity": billing_activity,
    }


def build_full_report(
    bq_client: Any,
    org_name: str,
    project: str,
    marts_dataset: str,
    landing_dataset: str,
    location_ids: list[str] | None = None,
    npi_overrides: dict[str, dict[str, Any]] | None = None,
    locations_override: list[dict[str, Any]] | None = None,
    *,
    state_filter: str | None = "FL",
) -> dict[str, Any]:
    """
    Build full Provider Roster / Credentialing report.
    L1 = system-imputed locations from bh_roster; L2 = locations_override (user-validated).
    L3 = merge: when locations_override is provided, it replaces L1 (universal truth).
    When state_filter is set (default FL), restrict to locations in that state.
    Returns dict: executive_summary, locations, npis_per_location, per_npi_validation, combos, invalid_combos, missed_opportunities, ghost_billing.
    """
    l1_locations = get_locations(bq_client, org_name, project, marts_dataset, state_filter=state_filter)
    if not l1_locations and not locations_override:
        return {
            "executive_summary": {"org_name": org_name, "error": "No locations found for this org name."},
            "primary_report": {"locations": [], "distinct_npis": [], "taxonomies_covered": [], "billing_activity": []},
            "locations": [],
            "npis_per_location": {},
            "per_npi_validation": [],
            "combos": [],
            "invalid_combos": [],
            "missed_opportunities": [],
            "ghost_billing": [],
        }
    # L3 = merge L1 + L2 (user-validated replaces when present)
    locations = merge_locations_l1_l2(l1_locations or [], locations_override, org_name)
    if not locations:
        return {
            "executive_summary": {"org_name": org_name, "error": "No locations after merge."},
            "primary_report": {"locations": [], "distinct_npis": [], "taxonomies_covered": [], "billing_activity": []},
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
    # Pass L3 location_ids so NPIs are fetched for the universal-truth locations
    # L1-matched: org name + location_id (from get_npis_per_location)
    # L2-new: address match only - user said these addresses belong to org (get_npis_by_address)
    location_ids_for_npi = [loc["location_id"] for loc in locations]
    npis_per_location = get_npis_per_location(
        bq_client, org_name, location_ids_for_npi, project, marts_dataset, npi_overrides,
        state_filter=state_filter,
    )
    # For L2-new locations: fetch NPIs by address (no org filter); capture org_npi/org_name per NPI.
    l2_new_locations = [loc for loc in locations if loc.get("match_source") == "l2_new"]
    org_npis_from_address: set[str] = set()  # orgs found at L2 addresses (may differ from primary org name)
    if l2_new_locations:
        npis_by_addr = get_npis_by_address(
            bq_client, l2_new_locations, project, marts_dataset, state_filter=state_filter,
        )
        for lid, nlist in npis_by_addr.items():
            if lid not in npis_per_location:
                npis_per_location[lid] = []
            for n in nlist:
                if not any(x.get("servicing_npi") == n.get("servicing_npi") for x in npis_per_location[lid]):
                    npis_per_location[lid].append(n)
                o = n.get("roster_org_npi") or ""
                if o:
                    org_npis_from_address.add(o)
    # Ensure every L3 location has an entry (empty if no bh_roster match)
    for loc in locations:
        lid = loc["location_id"]
        if lid not in npis_per_location:
            npis_per_location[lid] = []
    primary_org_npis = {loc["org_npi"] for loc in locations}
    org_npis = primary_org_npis | org_npis_from_address
    all_servicing = set()
    for nlist in npis_per_location.values():
        for n in nlist:
            all_servicing.add(n.get("servicing_npi") or "")
    all_servicing.discard("")
    readiness_rows = get_readiness_and_revenue_impact(
        bq_client, org_npis, all_servicing, project, marts_dataset
    )
    if readiness_rows is None:
        readiness_rows = get_readiness_and_combos(bq_client, org_npis, all_servicing, project, marts_dataset)
    run_rate_by_taxonomy_location = None
    run_rate_by_taxonomy_state = None
    if readiness_rows and readiness_rows[0].get("est_revenue_mid") is None:
        run_rate_by_taxonomy_location = get_billing_run_rate_by_taxonomy_location(
            bq_client, org_npis, project, marts_dataset, landing_dataset, year=2024
        )
        run_rate_by_taxonomy_state = get_run_rate_by_taxonomy_state(
            bq_client, project, marts_dataset, landing_dataset,
            state=state_filter or "FL",
            year=2024,
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
        run_rate_by_taxonomy_state=run_rate_by_taxonomy_state,
        state_filter=state_filter or "FL",
        primary_org_npis=primary_org_npis,
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

    # Build granular match report: what matched, what didn't, what we picked up
    l3_ids = {loc["location_id"] for loc in locations}
    locations_match_report = []
    for loc in locations:
        nlist = npis_per_location.get(loc["location_id"]) or []
        unique_npis = {n.get("servicing_npi") or "" for n in nlist}
        unique_npis.discard("")
        npi_count = len(unique_npis)  # unique NPIs (not combos)
        locations_match_report.append({
            "location_id": loc["location_id"],
            "site_address_line_1": loc.get("site_address_line_1"),
            "site_city": loc.get("site_city"),
            "site_state": loc.get("site_state"),
            "site_zip": loc.get("site_zip"),
            "match_source": loc.get("match_source", "l1"),
            "l1_address": loc.get("l1_address", ""),
            "l2_address": loc.get("l2_address", ""),
            "npi_count": npi_count,
            "npis_picked_up": "yes" if npi_count > 0 else "no",
        })
    l1_not_in_l2: list[dict[str, Any]] = []
    if locations_override and l1_locations:
        for l1 in l1_locations:
            if l1["location_id"] not in l3_ids:
                l1_not_in_l2.append({
                    "location_id": l1["location_id"],
                    "site_address_line_1": l1.get("site_address_line_1"),
                    "site_city": l1.get("site_city"),
                    "site_state": l1.get("site_state"),
                    "site_zip": l1.get("site_zip"),
                    "note": "L1 (system) had this; not in user L2 list",
                })

    # Taxonomy labels: BQ nucc_taxonomy (when available) + local fallback
    tax_codes_for_labels = sorted({(r.get("provider_taxonomy_code") or "").strip() for r in readiness_rows if (r.get("provider_taxonomy_code") or "").strip()})
    bq_labels = _fetch_taxonomy_labels_from_bq(bq_client, project, marts_dataset, tax_codes_for_labels)
    taxonomy_labels = {k: v for k, v in bq_labels.items() if v}

    # Primary report: simple sheet for ops (locations, distinct NPIs + why, taxonomies, billing)
    primary_report = _build_primary_report(
        locations, npis_per_location, readiness_rows, taxonomy_labels=taxonomy_labels
    )

    # Confidence report: all combos stratified by confidence band (perfect/good/medium/low)
    confidence_report = []
    for r in readiness_rows:
        score = r.get("confidence_score") or 0
        band = "perfect" if score >= 90 else "good" if score >= 70 else "medium" if score >= 50 else "low"
        row = dict(r)
        row["confidence_band"] = band
        confidence_report.append(row)
    # Sort by confidence_band (perfect first) then by score desc
    band_order = {"perfect": 0, "good": 1, "medium": 2, "low": 3}
    confidence_report.sort(
        key=lambda x: (band_order.get(x.get("confidence_band", ""), 4), -(x.get("confidence_score") or 0))
    )

    return {
        "executive_summary": executive,
        "primary_report": primary_report,
        "locations": locations,
        "npis_per_location": {k: v for k, v in npis_per_location.items()},
        "per_npi_validation": per_npi_validation,
        "combos": readiness_rows,
        "confidence_report": confidence_report,
        "invalid_combos": invalid_combos,
        "missed_opportunities": missed_opportunities,
        "ghost_billing": ghost_billing,
        "locations_match_report": locations_match_report,
        "l1_not_in_l2": l1_not_in_l2,
    }
