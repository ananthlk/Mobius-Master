"""Search implementations: Google Custom Search API and DuckDuckGo fallback."""
from __future__ import annotations

import logging
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


def google_custom_search(query: str, api_key: str, cx: str, num: int = 5) -> list[dict[str, Any]]:
    """Call Google Custom Search JSON API. Returns list of {title, snippet, url}."""
    if not api_key or not cx:
        return []
    url = (
        "https://www.googleapis.com/customsearch/v1"
        f"?key={urllib.parse.quote(api_key)}"
        f"&cx={urllib.parse.quote(cx)}"
        f"&q={urllib.parse.quote(query)}"
        f"&num={min(10, max(1, num))}"
    )
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode()
        import json
        out = json.loads(data)
        items = out.get("items") or []
        return [
            {
                "title": i.get("title") or "",
                "snippet": i.get("snippet") or "",
                "url": i.get("link") or "",
            }
            for i in items
        ]
    except Exception as e:
        logger.warning("Google Custom Search API failed: %s", e)
        return []


def duckduckgo_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Fallback: DuckDuckGo search via ddgs package (no API key)."""
    try:
        from ddgs import DDGS
        results = list(DDGS().text(query, max_results=max_results))
        return [
            {
                "title": r.get("title") or "",
                "snippet": r.get("body") or r.get("snippet") or "",
                "url": r.get("href") or r.get("url") or "",
            }
            for r in results
        ]
    except ImportError:
        logger.warning("ddgs not installed; pip install ddgs")
        return []
    except Exception as e:
        logger.warning("DuckDuckGo search failed: %s", e)
        return []


def search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Run search: Google Custom Search if configured, else DuckDuckGo fallback."""
    from app.config import GOOGLE_CSE_API_KEY, GOOGLE_CSE_CX, USE_DUCKDUCKGO_FALLBACK

    if GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX:
        results = google_custom_search(query, GOOGLE_CSE_API_KEY, GOOGLE_CSE_CX, num=max_results)
        if results:
            return results
        logger.info("Google CSE returned no results; trying DuckDuckGo fallback")

    if USE_DUCKDUCKGO_FALLBACK:
        return duckduckgo_search(query, max_results=max_results)
    return []
