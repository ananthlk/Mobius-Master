"""CMS Coverage API client - Medicare Coverage Database (NCDs, LCDs)."""
import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from app.config import CMS_COVERAGE_BASE, CMS_LICENSE_TOKEN

logger = logging.getLogger(__name__)

# Reports endpoints (typically no token): national-coverage-ncd, local-coverage-final-lcds, etc.
# Data endpoints often require License Agreement token


def _cms_request(path: str, use_token: bool = False) -> dict[str, Any] | list[Any] | None:
    """GET request to CMS Coverage API."""
    base = (CMS_COVERAGE_BASE or "").rstrip("/")
    url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
    headers = {"Accept": "application/json"}
    if use_token and CMS_LICENSE_TOKEN:
        headers["Authorization"] = f"Bearer {CMS_LICENSE_TOKEN}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("CMS Coverage API request failed: %s", e)
        return None


def search_coverage(
    query: str | None = None,
    document_type: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Search coverage documents. Uses reports endpoints to list NCDs/LCDs.
    query: optional keyword; document_type: ncd, lcd, article, or None for all.
    """
    results: list[dict[str, Any]] = []
    q_lower = (query or "").strip().lower()

    if not document_type or document_type.lower() in ("ncd", "national"):
        data = _cms_request("/v1/reports/national-coverage-ncd/")
        if isinstance(data, dict) and "data" in data:
            items = data.get("data") or []
        elif isinstance(data, dict) and "results" in data:
            items = data.get("results") or []
        elif isinstance(data, list):
            items = data
        else:
            items = []
        for item in (items[:limit * 2] if q_lower else items[:limit]):
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or item.get("document_title") or "")
            doc_id = item.get("document_id") or item.get("id") or ""
            if q_lower and q_lower not in (title or "").lower() and q_lower not in str(doc_id).lower():
                continue
            results.append({
                "type": "NCD",
                "document_id": doc_id,
                "document_display_id": item.get("document_display_id"),
                "title": title,
                "last_updated": item.get("last_updated"),
            })

    if not document_type or document_type.lower() in ("lcd", "local"):
        data = _cms_request("/v1/reports/local-coverage-final-lcds/")
        if isinstance(data, dict) and "data" in data:
            items = data.get("data") or []
        elif isinstance(data, dict) and "results" in data:
            items = data.get("results") or []
        elif isinstance(data, list):
            items = data
        else:
            items = []
        for item in (items[:limit * 2] if q_lower else items[:limit]):
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or item.get("document_title") or "")
            doc_id = str(item.get("document_id") or item.get("id") or "")
            if q_lower and q_lower not in (title or "").lower() and q_lower not in str(doc_id).lower():
                continue
            results.append({
                "type": "LCD",
                "document_id": doc_id,
                "document_display_id": item.get("document_display_id"),
                "title": title,
                "last_updated": item.get("last_updated"),
                "contractor": item.get("contractor_id"),
            })

    return {
        "count": len(results),
        "documents": results[:limit],
    }


def get_coverage_document(document_id: str, document_type: str = "ncd") -> dict[str, Any] | None:
    """Fetch a single coverage document by ID. document_type: ncd, lcd, article."""
    if not document_id:
        return None
    dt = (document_type or "ncd").lower()
    path = f"/v1/data/{dt}/" if dt in ("ncd", "lcd", "article") else "/v1/data/ncd/"
    # API may use different path structure; try common patterns
    data = _cms_request(f"{path}?id={urllib.parse.quote(document_id)}", use_token=True)
    if not data:
        data = _cms_request(f"{path}{urllib.parse.quote(document_id)}", use_token=True)
    return data if isinstance(data, dict) else None
