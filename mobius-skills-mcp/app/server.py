"""MCP server exposing Mobius skills: google_search, web_scrape_review, search_org_names, search_org_by_address."""
import json
import logging
import os
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

GOOGLE_SEARCH_URL = os.environ.get("CHAT_SKILLS_GOOGLE_SEARCH_URL", "http://localhost:8004/search?")
WEB_SCRAPER_URL = os.environ.get("CHAT_SKILLS_WEB_SCRAPER_URL", "http://localhost:8002/scrape/review")
PROVIDER_ROSTER_CREDENTIALING_URL = os.environ.get("CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL", "http://localhost:8010/report")


def _provider_roster_base_url() -> str:
    """Base URL for provider-roster-credentialing API (e.g. http://localhost:8010)."""
    url = (PROVIDER_ROSTER_CREDENTIALING_URL or "").strip()
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

_PORT = int(os.environ.get("PORT", "8006"))
_HOST = os.environ.get("HOST", "0.0.0.0")

mcp = FastMCP(
    "Mobius Skills",
    json_response=True,
    host=_HOST,
    port=_PORT,
)


@mcp.tool()
def google_search(query: str, max_results: int = 5) -> str:
    """Search the web using Google. Returns titles, snippets, and URLs of search results.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 5, max 10).
    """
    if not query or not str(query).strip():
        logger.warning("google_search rejected: empty query")
        return "Error: query is required and cannot be empty."
    query = str(query).strip()
    logger.info("google_search query=%s", query[:50])
    base = (GOOGLE_SEARCH_URL or "").strip()
    if not base:
        logger.warning("google_search failed: CHAT_SKILLS_GOOGLE_SEARCH_URL not configured")
        return "Error: CHAT_SKILLS_GOOGLE_SEARCH_URL not configured. Set it to the mobius-google-search API base (e.g. http://localhost:8004/search?)."
    sep = "&" if "?" in base else "?"
    url = base.rstrip("/") + sep + "q=" + urllib.parse.quote(query) + "&num=" + str(min(10, max(1, max_results)))
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            import json
            data = json.loads(resp.read().decode())
        results = data.get("results") or data.get("items") or []
        if not results:
            return "No search results found."
        lines = []
        for i, r in enumerate(results[:max_results], 1):
            title = r.get("title") or ""
            snippet = r.get("snippet") or r.get("description") or ""
            link = r.get("url") or r.get("link") or ""
            lines.append(f"[{i}] {title}\n    {snippet}\n    URL: {link}")
        return "\n\n".join(lines)
    except Exception as e:
        logger.warning("google_search failed: %s", e)
        return f"Search failed: {e}. Ensure mobius-google-search is running on port 8004 and CHAT_SKILLS_GOOGLE_SEARCH_URL is set."


@mcp.tool()
def web_scrape_review(url: str, include_summary: bool = False) -> str:
    """Scrape a single web page and extract its text content. Respects robots.txt.

    Args:
        url: The URL of the page to scrape (e.g. https://example.com/page).
        include_summary: If true, add an LLM-generated summary (requires Vertex/OpenAI).
    """
    if not url or not str(url).strip():
        logger.warning("web_scrape_review rejected: empty url")
        return "Error: url is required."
    url = str(url).strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        logger.warning("web_scrape_review rejected: invalid URL scheme url=%s", url[:80])
        return "Error: url must use http or https scheme."
    logger.info("web_scrape_review url=%s", url[:80] + ("..." if len(url) > 80 else ""))
    base = (WEB_SCRAPER_URL or "").strip()
    if not base:
        logger.warning("web_scrape_review failed: CHAT_SKILLS_WEB_SCRAPER_URL not configured")
        return "Error: CHAT_SKILLS_WEB_SCRAPER_URL not configured. Set it to the mobius-web-scraper review endpoint (e.g. http://localhost:8002/scrape/review)."
    try:
        import json
        payload = json.dumps({"url": url, "include_summary": include_summary}).encode("utf-8")
        req = urllib.request.Request(
            base,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        text = data.get("text") or ""
        summary = data.get("summary") or ""
        if not text:
            return f"No content extracted from {url}. The page may be empty or block automated access."
        out = f"URL: {url}\n\nContent:\n{text[:8000]}"
        if len(text) > 8000:
            out += "\n\n[... truncated ...]"
        if summary:
            out += f"\n\nSummary: {summary}"
        return out
    except urllib.error.HTTPError as e:
        body = ""
        if e.fp:
            try:
                body = e.fp.read().decode()
            except Exception:
                body = str(e)
        else:
            body = str(e)
        logger.warning("web_scrape_review failed: HTTP %s %s", e.code, body[:200])
        return f"Scrape failed ({e.code}): {body}"
    except Exception as e:
        logger.warning("web_scrape_review failed: %s", e)
        return f"Scrape failed: {e}. Ensure mobius-web-scraper is running on port 8002 and CHAT_SKILLS_WEB_SCRAPER_URL is set."


@mcp.tool()
def search_org_names(
    name: str,
    state: str = "FL",
    limit: int = 20,
    include_pml: bool = True,
    entity_type_filter: str | None = "2",
) -> str:
    """Search NPPES and PML for organization/provider names. Returns list of matches with NPI, name, source, entity_type. Use for Step 1 org disambiguation.

    Args:
        name: Organization or provider name to search (e.g. "David Lawrence", "Aspire").
        state: State filter (default FL).
        limit: Max matches to return (default 20).
        include_pml: Include PML results when available (default True).
        entity_type_filter: NPPES entity type: "2"=orgs (default), "1"=individuals, "all"=both.
    """
    if not name or not str(name).strip():
        return "Error: name is required."
    name = str(name).strip()
    base = _provider_roster_base_url()
    if not base:
        return "Error: CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL not configured."
    url = f"{base}/search/org-names"
    et = None if (entity_type_filter or "").lower() == "all" else (entity_type_filter or "2")
    payload = {
        "name": name,
        "state": state or "FL",
        "limit": min(50, max(1, limit)),
        "include_pml": include_pml,
        "entity_type_filter": et,
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        results = data.get("results") or []
        if not results:
            return f"No matches found for '{name}'."
        lines = [f"Found {len(results)} match(es) for '{name}':", ""]
        for i, r in enumerate(results[:limit], 1):
            lines.append(f"  {i}. {r.get('name', '')}  |  NPI: {r.get('npi', '')}  |  Source: {r.get('source', '')}  |  Type: {r.get('entity_type', '')}")
        return "\n".join(lines)
    except urllib.error.HTTPError as e:
        body = e.fp.read().decode()[:500] if e.fp else str(e)
        logger.warning("search_org_names HTTP %s %s", e.code, body)
        return f"Org name search failed ({e.code}): {body}"
    except Exception as e:
        logger.warning("search_org_names failed: %s", e)
        return f"Org name search failed: {e}"


@mcp.tool()
def search_org_by_address(
    address_raw: str | None = None,
    address_line_1: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    limit: int = 20,
    include_pml: bool = True,
    use_google: bool = True,
) -> str:
    """Search NPPES and PML by address. Returns matches with NPI, name, address. Use for Step 1 org disambiguation when user provides an address.

    Args:
        address_raw: Free-form address string (e.g. "434 W Kennedy Blvd, Tampa, FL 33609").
        address_line_1: Street address (use with city, state, postal_code).
        city: City.
        state: State (default FL).
        postal_code: ZIP or ZIP+4.
        limit: Max matches (default 20).
        include_pml: Include PML results (default True).
        use_google: Use Google address validation when available (default True).
    """
    if not address_raw and not any([address_line_1, city, postal_code]):
        return "Error: provide address_raw or (address_line_1, city, state, postal_code)."
    base = _provider_roster_base_url()
    if not base:
        return "Error: CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL not configured."
    url = f"{base}/search/org-by-address"
    payload = {
        "address_raw": address_raw or None,
        "address_line_1": address_line_1 or None,
        "city": city or None,
        "state": state or "FL",
        "postal_code": postal_code or None,
        "limit": min(50, max(1, limit)),
        "include_pml": include_pml,
        "use_google": use_google,
        "entity_type_filter": "2",
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        results = data.get("results") or []
        norm = data.get("normalized_address") or {}
        err = data.get("error", "")
        if err:
            return f"Address search: {err}"
        if not results:
            addr = address_raw or f"{address_line_1 or ''}, {city or ''}, {state or ''} {postal_code or ''}".strip(", ")
            return f"No matches found for address: {addr}"
        lines = [f"Normalized: {norm.get('address_line_1','')}, {norm.get('city','')} {norm.get('state','')} {norm.get('zip5','')}".strip(", "), ""]
        lines.append(f"Found {len(results)} match(es):")
        for i, r in enumerate(results[:limit], 1):
            addr = f"{r.get('address_line_1','')}, {r.get('city','')} {r.get('state','')} {r.get('zip5','')}".strip(", ")
            lines.append(f"  {i}. {r.get('name','')}  |  NPI: {r.get('npi','')}  |  {addr}")
        return "\n".join(lines)
    except urllib.error.HTTPError as e:
        body = e.fp.read().decode()[:500] if e.fp else str(e)
        logger.warning("search_org_by_address HTTP %s %s", e.code, body)
        return f"Org address search failed ({e.code}): {body}"
    except Exception as e:
        logger.warning("search_org_by_address failed: %s", e)
        return f"Org address search failed: {e}"


@mcp.tool()
def provider_roster_credentialing_report(
    org_name: str,
    location_ids: list[str] | None = None,
    locations_override: list[dict] | None = None,
    npi_overrides: dict | None = None,
) -> str:
    """Generate the Provider Roster / Credentialing report for an organization. Returns executive summary, key counts, invalid combos, and ghost billing. Use when the user asks for a provider roster, credentialing report, or Medicaid readiness report for an org (e.g. by name like \"David Lawrence\").

    Args:
        org_name: Organization name or substring (e.g. "David Lawrence", "Aspire").
        location_ids: Optional list of location_id to include (from a previous locations list). Omit to use all locations.
        locations_override: Optional L2 user-validated locations. List of {site_address_line_1, site_city, site_state, site_zip}. Replaces system-imputed locations when provided.
        npi_overrides: Optional dict mapping location_id to { "add": [npi,...], "remove": [npi,...] }. Omit for no overrides.
    """
    if not org_name or not str(org_name).strip():
        logger.warning("provider_roster_credentialing_report rejected: empty org_name")
        return "Error: org_name is required."
    org_name = str(org_name).strip()
    base = (PROVIDER_ROSTER_CREDENTIALING_URL or "").strip()
    if not base:
        logger.warning("provider_roster_credentialing_report failed: CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL not set")
        return "Error: CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL not configured. Set it to the provider-roster-credentialing API base (e.g. http://localhost:8010/report)."
    try:
        import json
        payload = json.dumps({
            "org_name": org_name,
            "location_ids": location_ids or None,
            "locations_override": locations_override or None,
            "npi_overrides": npi_overrides or None,
        }).encode("utf-8")
        req = urllib.request.Request(
            base,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = ""
        if e.fp:
            try:
                body = e.fp.read().decode()[:500]
            except Exception:
                body = str(e)
        logger.warning("provider_roster_credentialing_report HTTP %s %s", e.code, body)
        return f"Provider Roster / Credentialing report failed ({e.code}): {body}"
    except Exception as e:
        logger.warning("provider_roster_credentialing_report failed: %s", e)
        return f"Report failed: {e}. Ensure provider-roster-credentialing API is running and CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL is set."
    ex = data.get("executive_summary") or {}
    if ex.get("error"):
        return f"Provider Roster / Credentialing report: {ex['error']}"
    lines = [
        "# Provider Roster / Credentialing Report",
        "",
        f"**Organization:** {ex.get('org_name', '')}",
        "",
        "## Executive Summary",
        "",
        f"- Locations: {ex.get('location_count', 0)}",
        f"- Total NPIs: {ex.get('total_npis', 0)}",
        f"- NPIs (all checks pass): {ex.get('npis_all_checks_pass', 0)}",
        f"- NPIs (at least one fail): {ex.get('npis_at_least_one_fail', 0)}",
        f"- Invalid combos: {ex.get('invalid_combo_count', 0)}",
        f"- Ghost billing: {ex.get('ghost_billing_npi_count', 0)} NPI(s), {ex.get('ghost_billing_claim_count', 0)} claims, ${ex.get('ghost_billing_total_paid', 0):,.0f}",
        "",
        "**Readiness status:** " + ", ".join(f"{k}: {v}" for k, v in (ex.get("readiness_status_breakdown") or {}).items()),
        "",
        f"**Next steps:** {ex.get('next_steps', '')}",
        "",
        "---",
        "Full report (locations, NPIs, combos, invalid combos, ghost billing) is available via the API or CLI. Use the script generate_provider_roster_credentialing_report.py for CSV/Excel download.",
    ]
    return "\n".join(lines)
