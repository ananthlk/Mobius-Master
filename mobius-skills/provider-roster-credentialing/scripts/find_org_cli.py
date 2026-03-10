#!/usr/bin/env python3
"""
Step 1 find-org CLI: name or URL → Google search (if name) → tree scrape (2 levels) → LLM extract → org search → merge.

Uses existing skills via HTTP: google-search, web-scraper (POST /scrape tree mode). LLM extraction via Gemini/Vertex
or OpenAI. Does NOT build separate modules.

Usage:
  # From org name (searches web for website, scrapes, extracts, searches NPPES/PML)
  uv run python scripts/find_org_cli.py "David Lawrence Center"
  uv run python scripts/find_org_cli.py "Henderson Behavioral Health"

  # From URL (scrapes directly, extracts, searches NPPES/PML)
  uv run python scripts/find_org_cli.py "https://davidlawrencecenter.org"

  # Skip scrape; search by name only (faster)
  uv run python scripts/find_org_cli.py "Aspire" --name-only

  # Options
  --state FL --limit 20 --no-pml --json

Env:
  CHAT_SKILLS_GOOGLE_SEARCH_URL   (default: http://localhost:8004/search?)
  CHAT_SKILLS_WEB_SCRAPER_URL     (default: http://localhost:8002/scrape/review)
  BQ_PROJECT, BQ_LANDING_MEDICAID_DATASET
  OPENAI_API_KEY or VERTEX_PROJECT_ID / GEMINI_API_KEY  (for LLM extraction; use --no-llm to skip)

Requires: mobius-skills/google-search, mobius-skills/web-scraper + worker (e.g. via mstart).
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from google.cloud import bigquery
except ImportError:
    print("Install: pip install google-cloud-bigquery", file=sys.stderr)
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("Install: pip install httpx", file=sys.stderr)
    sys.exit(1)

from app.org_search import search_org_names, search_org_by_address

GOOGLE_SEARCH_URL = os.environ.get("CHAT_SKILLS_GOOGLE_SEARCH_URL", "http://localhost:8004/search?").strip()
WEB_SCRAPER_URL = os.environ.get("CHAT_SKILLS_WEB_SCRAPER_URL", "http://localhost:8002/scrape/review").strip()


def _web_scraper_base() -> str:
    """Base URL for web-scraper API (e.g. http://localhost:8002)."""
    u = (WEB_SCRAPER_URL or "").strip()
    if "/scrape" in u:
        return u.split("/scrape")[0].rstrip("/")
    return u.replace("/scrape/review", "").rstrip("/") or "http://localhost:8002"

# US address: number street, City, ST 12345 or 12345
_ADDR_RE = re.compile(
    r"\d+[\w\s\.\#\-]+(?:,\s*)[A-Za-z\s]+(?:,\s*)(?:[A-Z]{2}|Florida)\s+(?:\d{5}(?:-\d{4})?)",
    re.IGNORECASE,
)
# Simpler: ends with state and ZIP
_ADDR_SIMPLE_RE = re.compile(r"([\d\w\s\.\#\-,]+(?:FL|Florida)\s+\d{5}(?:-\d{4})?)", re.IGNORECASE)


def _is_url(s: str) -> bool:
    return bool(s and (s.startswith("http://") or s.startswith("https://")))


def _domain_to_name(url: str) -> str:
    """Derive plausible org name from URL (e.g. davidlawrencecenters.org -> David Lawrence Centers)."""
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.netloc or parsed.path or "").lower()
        host = host.replace("www.", "").split(":")[0]
        if not host:
            return ""
        # Get domain without TLD (e.g. davidlawrencecenters)
        parts = host.split(".")
        base = parts[0] if parts else host
        # Split camelCase or replace separators with spaces, title case
        base = re.sub(r"[-_]", " ", base)
        words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|[A-Z]+", base) if base != base.lower() else base.split()
        if not words:
            words = [w for w in re.split(r"[\s\-_]+", base) if w]
        return " ".join(w.title() if isinstance(w, str) else w for w in words).strip() or base.title()
    except Exception:
        return ""


def _google_search(query: str, max_results: int = 5) -> list[dict]:
    """Call mobius-skills/google-search. Returns list of {title, snippet, url}."""
    if not GOOGLE_SEARCH_URL:
        return []
    sep = "&" if "?" in GOOGLE_SEARCH_URL else "?"
    url = f"{GOOGLE_SEARCH_URL.rstrip('/')}{sep}q={_url_quote(query)}&num={min(10, max(1, max_results))}"
    try:
        r = httpx.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"Google search failed: {e}", file=sys.stderr)
        return []
    items = data.get("items") or data.get("results") or []
    return [
        {"title": i.get("title", ""), "snippet": i.get("snippet", i.get("description", "")), "url": i.get("url", i.get("link", ""))}
        for i in items
    ]


def _url_quote(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(s, safe="")


def _web_scrape_tree(url: str, max_depth: int = 2, max_pages: int = 30, poll_interval: float = 2.0) -> str:
    """Tree scrape: POST /scrape with mode=tree, poll until done, return combined page text."""
    base = _web_scraper_base()
    scrape_url = f"{base}/scrape"
    try:
        r = httpx.post(
            scrape_url,
            json={
                "url": url,
                "mode": "tree",
                "max_depth": max_depth,
                "max_pages": max_pages,
                "include_content": True,
                "include_summary": False,
            },
            timeout=15,
        )
        r.raise_for_status()
        job_id = r.json().get("job_id", "")
        if not job_id:
            print("Tree scrape: no job_id returned", file=sys.stderr)
            return ""
    except Exception as e:
        print(f"Tree scrape start failed: {e}", file=sys.stderr)
        return ""
    status_url = f"{base}/scrape/{job_id}"
    for _ in range(120):  # ~4 min max
        time.sleep(poll_interval)
        try:
            sr = httpx.get(status_url, timeout=10)
            sr.raise_for_status()
            data = sr.json()
        except Exception as e:
            print(f"Tree scrape poll failed: {e}", file=sys.stderr)
            return ""
        status = data.get("status", "")
        if status == "completed":
            pages = data.get("pages", [])
            texts = [p.get("text", "") for p in pages if p.get("text")]
            combined = "\n\n".join(texts).strip()
            print(f"Tree scrape: {len(pages)} page(s), {len(combined)} chars", file=sys.stderr)
            return combined
        if status == "failed":
            err = data.get("error", "unknown")
            print(f"Tree scrape failed: {err}", file=sys.stderr)
            return ""
    print("Tree scrape timed out", file=sys.stderr)
    return ""


def _web_scrape_review(url: str) -> str:
    """Single-page scrape: POST /scrape/review. Returns page text."""
    if not WEB_SCRAPER_URL:
        return ""
    try:
        r = httpx.post(WEB_SCRAPER_URL, json={"url": url, "include_summary": False}, timeout=30)
        r.raise_for_status()
        data = r.json()
        return (data.get("text") or "").strip()
    except Exception as e:
        print(f"Web scrape failed: {e}", file=sys.stderr)
        return ""


def _extract_via_llm(text: str, fallback_name: str | None = None) -> tuple[list[str], list[str]]:
    """
    Use LLM to extract org names, addresses, and location details from scraped text.
    Returns (names, addresses). Falls back to heuristic if LLM unavailable or fails.
    """
    text = (text or "")[:50000].strip()
    if not text:
        return ([fallback_name] if fallback_name else [], [])

    system = """You extract organization names, addresses, and location details from healthcare/behavioral health website content.
Return ONLY valid JSON in this exact shape (no markdown, no extra text):
{"org_names": ["string", ...], "addresses": ["full US address string", ...], "locations": ["campus/location name", ...]}

Rules:
- org_names: legal or common org names (e.g. "David Lawrence Centers for Behavioral Health")
- addresses: complete US addresses with street, city, state, ZIP (e.g. "6075 Bathey Lane, Naples, FL 34116")
- locations: campus/site names if mentioned (e.g. "Main Campus", "Golden Gate")
- Deduplicate. Prefer the primary organization name from page title/headings."""
    user = f"Content:\n\n{text}"

    try:
        from app.report_writer import _call_gemini, _call_openai
        model_gemini = os.getenv("VERTEX_MODEL") or os.getenv("CHAT_VERTEX_MODEL") or "gemini-1.5-flash"
        model_openai = "gpt-4o-mini"
        if os.getenv("OPENAI_API_KEY", "").strip():
            raw = _call_openai(system, user, model_openai)
        else:
            raw = _call_gemini(system, user, model_gemini)
    except Exception as e:
        print(f"LLM extraction failed ({e}), using heuristic", file=sys.stderr)
        return _extract_org_names_and_addresses(text, fallback_name)

    raw = (raw or "").strip()
    # Strip markdown code fence if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"```\s*$", "", raw)
    try:
        data = json.loads(raw)
        names = list(dict.fromkeys([s for s in (data.get("org_names") or []) if s and isinstance(s, str)]))[:15]
        addrs = list(dict.fromkeys([s for s in (data.get("addresses") or []) if s and isinstance(s, str)]))[:15]
        locs = list(dict.fromkeys([s for s in (data.get("locations") or []) if s and isinstance(s, str)]))[:5]
        # Locations can be search terms too (e.g. "Golden Gate" + org name)
        for loc in locs:
            if loc and loc not in names and len(names) < 15:
                names.append(loc)
        if not names and fallback_name:
            names = [fallback_name.strip()]
        return (names, addrs)
    except json.JSONDecodeError as e:
        print(f"LLM returned invalid JSON ({e}), using heuristic", file=sys.stderr)
        return _extract_org_names_and_addresses(text, fallback_name)


def _extract_org_names_and_addresses(text: str, fallback_name: str | None = None) -> tuple[list[str], list[str]]:
    """
    Heuristic extraction (fallback when LLM unavailable).
    Returns (names, addresses).
    """
    text = (text or "")[:15000]
    names: list[str] = []
    addresses: list[str] = []

    for m in _ADDR_SIMPLE_RE.finditer(text):
        addr = m.group(1).strip()
        if len(addr) > 10 and addr not in addresses:
            addresses.append(addr)

    suffixes = ("center", "centers", "health", "partners", "services", "care", "inc", "llc", "corp", "association", "foundation")
    for line in re.split(r"[\n\.;]", text):
        line = line.strip()
        if len(line) < 5 or len(line) > 120:
            continue
        lower = line.lower()
        if any(x in lower for x in ("home", "about", "contact", "privacy", "©", "copyright")):
            continue
        words = line.split()
        if len(words) >= 2:
            last = words[-1].rstrip(".,;")
            if last.lower() in suffixes or (len(words) >= 3 and words[0][0].isupper()):
                candidate = " ".join(words[:5]).strip()
                if candidate and candidate not in names and len(candidate) > 3:
                    names.append(candidate)

    if not names and fallback_name and fallback_name.strip():
        names = [fallback_name.strip()]
    return (names[:10], addresses[:10])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step 1: Find org candidates from name or URL (Google search + scrape + org search)"
    )
    parser.add_argument("input", help="Org name or website URL")
    parser.add_argument("--name-only", action="store_true", help="Skip Google/scrape; search by name directly")
    parser.add_argument("--tree-depth", type=int, default=2, help="Tree scrape max depth (default: 2)")
    parser.add_argument("--tree-pages", type=int, default=30, help="Tree scrape max pages (default: 30)")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM extraction; use heuristic only")
    parser.add_argument("--state", default="FL", help="State filter (default: FL)")
    parser.add_argument("--limit", type=int, default=20, help="Max matches per search (default: 20)")
    parser.add_argument("--no-pml", action="store_true", help="Skip PML (NPPES only)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
    landing = os.environ.get("BQ_LANDING_MEDICAID_DATASET") if not args.no_pml else None

    try:
        bq = bigquery.Client(project=project)
    except Exception as e:
        print(f"BigQuery client failed: {e}", file=sys.stderr)
        return 1

    input_str = (args.input or "").strip()
    if not input_str:
        parser.error("Provide name or URL")
        return 1

    names_to_search: list[str] = []
    addresses_to_search: list[str] = []

    extract_fn = _extract_org_names_and_addresses if args.no_llm else _extract_via_llm

    if args.name_only:
        names_to_search = [input_str]
    elif _is_url(input_str):
        fallback = _domain_to_name(input_str) or input_str
        print(f"Tree scraping (depth={args.tree_depth}, max_pages={args.tree_pages})...", file=sys.stderr)
        text = _web_scrape_tree(input_str, max_depth=args.tree_depth, max_pages=args.tree_pages)
        if not text:
            print("No content from scrape. Falling back to name search.", file=sys.stderr)
            names_to_search = [fallback] if fallback else [input_str]
        else:
            names_to_search, addresses_to_search = extract_fn(text, fallback_name=fallback)
            if not names_to_search and not addresses_to_search:
                names_to_search = [fallback] if fallback else [input_str]
            print(f"Extracted {len(names_to_search)} name(s), {len(addresses_to_search)} address(es)", file=sys.stderr)
    else:
        print("Searching web for website...", file=sys.stderr)
        results = _google_search(f"{input_str} website", max_results=5)
        url = None
        for r in results:
            u = (r.get("url") or "").strip()
            if u and not any(x in u.lower() for x in ("facebook.com", "twitter.com", "linkedin.com", "youtube.com")):
                url = u
                break
        if url:
            print(f"Tree scraping {url[:60]}...", file=sys.stderr)
            text = _web_scrape_tree(url, max_depth=args.tree_depth, max_pages=args.tree_pages)
            if text:
                names_to_search, addresses_to_search = extract_fn(text, fallback_name=input_str)
        if not names_to_search and not addresses_to_search:
            names_to_search = [input_str]
        if not names_to_search:
            names_to_search = [input_str]
        print(f"Searching NPPES/PML for {len(names_to_search)} name(s), {len(addresses_to_search)} address(es)", file=sys.stderr)

    seen_npis: set[str] = set()
    merged: list[dict] = []

    for name in names_to_search:
        if not name.strip():
            continue
        rows = search_org_names(
            bq,
            name,
            state_filter=args.state,
            limit=args.limit,
            include_pml=not args.no_pml,
            project=project,
            landing_dataset=landing,
        )
        for r in rows:
            npi = str(r.get("npi", ""))
            if npi and npi not in seen_npis:
                seen_npis.add(npi)
                merged.append({**r, "match_source": "name", "match_query": name})

    for addr in addresses_to_search:
        if not addr.strip():
            continue
        norm, rows = search_org_by_address(
            bq,
            address_raw=addr,
            limit=args.limit,
            include_pml=not args.no_pml,
            project=project,
            landing_dataset=landing,
        )
        for r in rows:
            npi = str(r.get("npi", ""))
            if npi and npi not in seen_npis:
                seen_npis.add(npi)
                merged.append({**r, "match_source": "address", "match_query": addr})

    if args.json:
        print(json.dumps({"results": merged, "count": len(merged)}, indent=2))
    else:
        if not merged:
            print("No matches found.")
        else:
            print(f"Found {len(merged)} candidate(s):\n")
            for i, r in enumerate(merged, 1):
                addr_part = ""
                if "address_line_1" in r:
                    addr_part = f"  {r.get('address_line_1','')}, {r.get('city','')} {r.get('state','')} {r.get('zip5','')}".strip(", ")
                else:
                    addr_part = f"  (from {r.get('match_source','')}: {r.get('match_query','')[:50]})"
                print(f"  {i}. {r.get('name','')}")
                print(f"     NPI: {r.get('npi','')}  |  Source: {r.get('source','')}  |  Type: {r.get('entity_type','')}")
                if addr_part.strip():
                    print(addr_part)
                print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
