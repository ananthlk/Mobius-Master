"""NPI Registry lookup via NPPES API v2.1 (free, no auth)."""
import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from app.config import NPPES_NPI_BASE

logger = logging.getLogger(__name__)


def _npi_request(params: dict[str, str]) -> dict[str, Any] | None:
    """Make GET request to NPPES API. Max 200 results per request."""
    base = (NPPES_NPI_BASE or "").rstrip("/")
    if "?" in base:
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v})
        url = f"{base}&{qs}"
    else:
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v})
        url = f"{base}?version=2.1&{qs}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("NPI API request failed: %s", e)
        return None


def _simplify_result(d: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from NPPES result for display."""
    if not isinstance(d, dict):
        return {}
    nums = (d.get("result_count") or 0, len(d.get("results") or []))
    results = d.get("results") or []
    simplified = []
    for r in results:
        if not isinstance(r, dict):
            continue
        addrs = r.get("addresses") or []
        primary = addrs[0] if addrs else {}
        taxonomies = r.get("taxonomies") or []
        primary_tax = taxonomies[0] if taxonomies else {}
        simplified.append({
            "npi": r.get("number"),
            "type": r.get("enumeration_type"),
            "name": r.get("basic", {}).get("name") or r.get("organization_name"),
            "status": r.get("basic", {}).get("status"),
            "address": primary.get("address_1"),
            "city": primary.get("city"),
            "state": primary.get("state"),
            "zip": primary.get("postal_code"),
            "taxonomy": primary_tax.get("desc"),
            "taxonomy_code": primary_tax.get("code"),
        })
    return {"result_count": nums[0], "returned": len(simplified), "results": simplified}


def lookup_npi(npi_number: str) -> dict[str, Any] | None:
    """Look up provider by NPI number. Returns first match or None."""
    npi = (npi_number or "").strip()
    if not npi or not npi.isdigit() or len(npi) != 10:
        return None
    data = _npi_request({"number": npi})
    if not data:
        return None
    out = _simplify_result(data)
    results = out.get("results") or []
    return results[0] if results else None


def search_npi(
    first_name: str | None = None,
    last_name: str | None = None,
    organization: str | None = None,
    state: str | None = None,
    taxonomy: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search NPI by name, org, state, or taxonomy. Returns simplified result set."""
    params: dict[str, str] = {}
    if first_name:
        params["first_name"] = first_name
    if last_name:
        params["last_name"] = last_name
    if organization:
        params["organization_name"] = organization
    if state:
        params["state"] = state[:2].upper()
    if taxonomy:
        params["taxonomy_description"] = taxonomy
    if not params:
        return {"result_count": 0, "returned": 0, "results": []}
    params["limit"] = str(min(200, max(1, limit)))
    data = _npi_request(params)
    if not data:
        return {"result_count": 0, "returned": 0, "results": []}
    out = _simplify_result(data)
    out["results"] = (out.get("results") or [])[:limit]
    return out
