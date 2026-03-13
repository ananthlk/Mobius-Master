"""ICD-10-CM lookup via NLM Clinical Tables API (free, no auth)."""
import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from app.config import ICD10_NLM_BASE

logger = logging.getLogger(__name__)

# API returns: [total, [codes], null, [[code, name], ...], total]
# https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?sf=code,name&terms=Z00


def search_icd10(terms: str, max_results: int = 15) -> list[dict[str, Any]]:
    """Search ICD-10-CM by code or description. Returns list of {code, name}."""
    terms = (terms or "").strip()
    if not terms:
        return []
    base = (ICD10_NLM_BASE or "").rstrip("/").replace("/search", "")
    url = f"{base}/search?sf=code,name&terms={urllib.parse.quote(terms)}&maxList={min(500, max(1, max_results))}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode())
        # Format: [total, [codes], null, [[code, name], ...], total]
        if isinstance(raw, list) and len(raw) >= 4:
            pairs = raw[3]
            if isinstance(pairs, list):
                return [
                    {"code": p[0] if len(p) > 0 else "", "name": p[1] if len(p) > 1 else ""}
                    for p in pairs
                    if isinstance(p, (list, tuple)) and len(p) >= 2
                ]
        return []
    except Exception as e:
        logger.warning("ICD-10 search failed: %s", e)
        return []


def lookup_icd10_code(code: str) -> dict[str, Any] | None:
    """Look up a single ICD-10-CM code by exact code (e.g. Z00.00)."""
    code = (code or "").strip()
    if not code:
        return None
    results = search_icd10(code, max_results=5)
    for r in results:
        if (r.get("code") or "").upper() == code.upper():
            return r
    if results:
        return results[0]
    return None
