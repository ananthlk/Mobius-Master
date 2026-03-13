"""
Step 5: Historic billing patterns.

For servicing NPIs (split by facility vs professional): DOGE last 12 months,
breakdown by HCPCS/procedure code. Descriptions from bigquery-public-data.cms_codes.
Unknown codes (e.g. CTPT): Google search fallback, then optional LLM; results cached.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 100
_MAX_NPIS = 500
_MAX_WORKERS = 5

_CMS_PROJECT = "bigquery-public-data"
_CMS_DATASET = "cms_codes"
_HCPCS_TABLE = "hcpcs"
_ICD10_PCS_TABLE = "icd10_pcs"
_CACHE_DIR = Path(os.environ.get("HISTORIC_BILLING_CACHE_DIR", ".cache")).resolve()
_CACHE_FILE = _CACHE_DIR / "code_descriptions.json"
_DEFAULT_PERIOD_START = "2024-01"
_DEFAULT_PERIOD_END = "2024-12"


def _job_config(params: list[tuple[str, str, Any]]) -> Any:
    from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
    return QueryJobConfig(
        query_parameters=[ScalarQueryParameter(name, typ, val) for name, typ, val in params]
    )


def _load_code_cache() -> dict[str, str]:
    """Load cached code -> description from disk."""
    if not _CACHE_FILE.exists():
        return {}
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load code cache: %s", e)
        return {}


def _save_code_cache(cache: dict[str, str]) -> None:
    """Persist code cache to disk."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=0)
    except Exception as e:
        logger.warning("Failed to save code cache: %s", e)


def _fetch_hcpcs_descriptions(client: Any, codes: list[str], project: str) -> dict[str, str]:
    """Fetch HCPCS descriptions from bigquery-public-data.cms_codes.hcpcs."""
    if not codes:
        return {}
    codes_clean = list(dict.fromkeys(c for c in codes if c))[:500]
    if not codes_clean:
        return {}
    in_list = ", ".join(f"'{c.replace(chr(39), chr(39)+chr(39))}'" for c in codes_clean)
    table = f"`{_CMS_PROJECT}.{_CMS_DATASET}.{_HCPCS_TABLE}`"
    # bigquery-public-data.cms_codes.hcpcs: HCPC, LONG_DESCRIPTION, SHORT_DESCRIPTION
    query = f"""
    SELECT TRIM(CAST(HCPC AS STRING)) AS code,
           TRIM(CAST(COALESCE(LONG_DESCRIPTION, SHORT_DESCRIPTION) AS STRING)) AS description
    FROM {table}
    WHERE TRIM(CAST(HCPC AS STRING)) IN ({in_list})
    """
    try:
        rows = list(client.query(query).result())
        return {str(r.code).strip(): str(r.description or "").strip() for r in rows if r.code}
    except Exception as e:
        logger.warning("HCPCS description fetch failed: %s", e)
        return {}


def _lookup_code_via_google(code: str) -> str | None:
    """Look up HCPCS/procedure code description via Google search API. Returns description or None."""
    url_base = (
        os.environ.get("HISTORIC_BILLING_GOOGLE_SEARCH_URL")
        or os.environ.get("CHAT_SKILLS_GOOGLE_SEARCH_URL")
        or ""
    ).strip()
    if not url_base:
        return None
    sep = "&" if "?" in url_base else "?"
    query = f"{code} HCPCS procedure code description"
    url = f"{url_base.rstrip('?&')}{sep}q={urllib.parse.quote(query)}&num=2"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("items") or data.get("results") or []
        if not items:
            return None
        snippet = (items[0].get("snippet") or items[0].get("description") or "").strip()
        if snippet and len(snippet) > 10:
            return snippet[:200].rsplit(".", 1)[0] + "." if "." in snippet[:200] else snippet[:200]
        return None
    except Exception as e:
        logger.debug("Google lookup for %s failed: %s", code, e)
        return None


def _lookup_code_via_llm(code: str) -> str | None:
    """Look up code description via LLM. Returns description or None. Optional (needs mobius-chat env)."""
    try:
        import asyncio
        import sys
        chat_path = Path(__file__).resolve().parents[3] / "mobius-chat"
        if chat_path.exists() and str(chat_path) not in sys.path:
            sys.path.insert(0, str(chat_path))
        from app.services.llm_provider import get_llm_provider
        prompt = f"What is HCPCS or procedure code {code}? Reply with a one-sentence description only, no preamble."
        provider = get_llm_provider()
        text, _ = asyncio.run(provider.generate_with_usage(prompt))
        desc = (text or "").strip()
        if desc and len(desc) > 5:
            return desc[:250].rsplit(".", 1)[0] + "." if "." in desc[:250] else desc[:250]
    except Exception as e:
        logger.debug("LLM lookup for %s failed: %s", code, e)
    return None


def _lookup_code_description_fallback(code: str) -> str | None:
    """Try Google, then LLM. Returns description or None."""
    desc = _lookup_code_via_google(code)
    if desc:
        return desc
    return _lookup_code_via_llm(code)


def _entity_types_batch(client: Any, npis: list[str], project: str) -> dict[str, str]:
    """Return npi -> entity_type (facility | professional) for all NPIs in one query."""
    if not npis:
        return {}
    npis_clean = [str(n).strip().zfill(10) for n in npis if n][:_MAX_NPIS]
    if not npis_clean:
        return {}
    in_list = ", ".join(f"'{n}'" for n in npis_clean)
    query = f"""
    SELECT TRIM(CAST(npi AS STRING)) AS npi, CAST(entity_type_code AS STRING) AS entity_type
    FROM `bigquery-public-data.nppes.npi_raw`
    WHERE TRIM(CAST(npi AS STRING)) IN ({in_list})
    """
    try:
        rows = list(client.query(query).result())
        out = {}
        for r in rows:
            npi = str(r.npi or "").strip().zfill(10)
            et = str(r.entity_type or "1").strip()
            out[npi] = "facility" if et == "2" else "professional"
        return out
    except Exception:
        return {}


def get_historic_billing_patterns(
    bq_client: Any,
    associated_providers: dict[str, list[dict[str, Any]]],
    *,
    project: str,
    landing_dataset: str,
    period_start: str = _DEFAULT_PERIOD_START,
    period_end: str = _DEFAULT_PERIOD_END,
) -> dict[str, Any]:
    """
    Step 5: Historic billing patterns for servicing NPIs.

    Returns:
        {
          "summary": { "total_claims": int, "total_paid": float, "n_codes": int },
          "by_code": [
            { "hcpcs_code", "description", "entity_type", "claim_count", "total_paid", "beneficiary_count" }
          ],
          "entity_breakdown": { "facility": {...}, "professional": {...} },
        }
    """
    if not landing_dataset or not associated_providers:
        return {"summary": {"total_claims": 0, "total_paid": 0.0, "n_codes": 0}, "by_code": [], "entity_breakdown": {}}

    # Collect all servicing NPIs
    all_npis: set[str] = set()
    for providers in associated_providers.values():
        for p in providers or []:
            n = (p.get("npi") or p.get("servicing_npi") or "").strip()
            if n:
                all_npis.add(str(n).zfill(10))
    if not all_npis:
        return {"summary": {"total_claims": 0, "total_paid": 0.0, "n_codes": 0}, "by_code": [], "entity_breakdown": {}}

    npis_list = list(all_npis)[:_MAX_NPIS]
    table_doge = f"`{project}.{landing_dataset}.stg_doge`"

    def _run_doge_chunk(chunk: list[str]) -> list:
        """Run DOGE query for one chunk of NPIs. Returns list of row-like dicts."""
        if not chunk:
            return []
        in_list = ", ".join(f"'{n}'" for n in chunk)
        query = f"""
        SELECT
          TRIM(CAST(servicing_npi AS STRING)) AS servicing_npi,
          TRIM(CAST(COALESCE(hcpcs_code, '') AS STRING)) AS hcpcs_code,
          SUM(COALESCE(claim_count, 0)) AS claim_count,
          SUM(COALESCE(total_paid, 0)) AS total_paid,
          SUM(COALESCE(beneficiary_count, 0)) AS beneficiary_count
        FROM {table_doge}
        WHERE (
            TRIM(CAST(servicing_npi AS STRING)) IN ({in_list})
            OR TRIM(CAST(billing_npi AS STRING)) IN ({in_list})
          )
          AND SAFE_CAST(period_month AS STRING) >= @period_start
          AND SAFE_CAST(period_month AS STRING) <= @period_end
          AND hcpcs_code IS NOT NULL
          AND TRIM(CAST(hcpcs_code AS STRING)) != ''
        GROUP BY 1, 2
        """
        try:
            job_config = _job_config([
                ("period_start", "STRING", period_start),
                ("period_end", "STRING", period_end),
            ])
            return list(bq_client.query(query, job_config=job_config).result())
        except Exception as e:
            logger.warning("DOGE chunk query failed: %s", e)
            return []

    # Chunk NPIs and run DOGE queries in parallel
    chunks = [npis_list[i : i + _CHUNK_SIZE] for i in range(0, len(npis_list), _CHUNK_SIZE)]
    rows: list = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        futures = {ex.submit(_run_doge_chunk, c): c for c in chunks}
        for fut in as_completed(futures):
            try:
                rows.extend(fut.result())
            except Exception as e:
                logger.warning("DOGE chunk failed: %s", e)

    # Build npi -> entity_type (single batched query for all NPIs)
    npi_entity = _entity_types_batch(bq_client, npis_list, project)

    # Aggregate by (hcpcs_code, entity_type)
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        code = str(r.hcpcs_code or "").strip()
        npi = str(r.servicing_npi or "").strip().zfill(10)
        entity = npi_entity.get(npi, "professional")
        key = (code, entity)
        if key not in by_key:
            by_key[key] = {"hcpcs_code": code, "entity_type": entity, "claim_count": 0, "total_paid": 0.0, "beneficiary_count": 0}
        by_key[key]["claim_count"] += int(r.claim_count or 0)
        by_key[key]["total_paid"] += float(r.total_paid or 0)
        by_key[key]["beneficiary_count"] += int(r.beneficiary_count or 0)

    # Get descriptions: CMS first, then cache, then Google/LLM fallback for missing
    codes = list(dict.fromkeys(k[0] for k in by_key))
    cache = _load_code_cache()
    descriptions = _fetch_hcpcs_descriptions(bq_client, codes, project)
    for c in codes:
        if c not in descriptions and c in cache:
            descriptions[c] = cache[c]
    # Fallback: Google then LLM for codes still without description (limit 10 per run)
    missing = [c for c in codes if not (descriptions.get(c) or cache.get(c))]
    _MAX_FALLBACK = 10
    for c in missing[:_MAX_FALLBACK]:
        fallback = _lookup_code_description_fallback(c)
        if fallback:
            descriptions[c] = fallback
            cache[c] = fallback
    if cache:
        _save_code_cache(cache)

    # Filter out taxonomy-format codes (323P00000X) — Section E requires HCPCS, not NUCC taxonomy
    from app.step_output_validation import validate_historic_billing_codes
    by_code_raw: list[dict[str, Any]] = []
    for (code, entity), row in sorted(by_key.items(), key=lambda x: (-x[1]["claim_count"], x[0])):
        desc = descriptions.get(code, "") or cache.get(code, "") or "(description not available)"
        by_code_raw.append({
            "hcpcs_code": code,
            "description": desc,
            "entity_type": entity,
            "claim_count": row["claim_count"],
            "total_paid": round(row["total_paid"], 2),
            "beneficiary_count": row["beneficiary_count"],
        })

    by_code, _removed = validate_historic_billing_codes(by_code_raw)
    total_claims = sum(r["claim_count"] for r in by_code)
    total_paid = sum(r["total_paid"] for r in by_code)

    # Entity breakdown
    entity_breakdown: dict[str, dict[str, Any]] = {"facility": {"claim_count": 0, "total_paid": 0.0, "n_codes": 0}, "professional": {"claim_count": 0, "total_paid": 0.0, "n_codes": 0}}
    for row in by_code:
        et = row["entity_type"]
        if et in entity_breakdown:
            entity_breakdown[et]["claim_count"] += row["claim_count"]
            entity_breakdown[et]["total_paid"] += row["total_paid"]
            entity_breakdown[et]["n_codes"] += 1
        else:
            entity_breakdown["professional"]["claim_count"] += row["claim_count"]
            entity_breakdown["professional"]["total_paid"] += row["total_paid"]
            entity_breakdown["professional"]["n_codes"] += 1

    return {
        "summary": {"total_claims": total_claims, "total_paid": round(total_paid, 2), "n_codes": len(by_code)},
        "by_code": by_code,
        "entity_breakdown": entity_breakdown,
    }


