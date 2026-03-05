#!/usr/bin/env python3
"""
Fetch FL AHCA Medicaid documents from the internet and store them locally.
Run periodically to refresh. Output: data/ahca_docs/*.md
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Install: pip install httpx", file=sys.stderr)
    sys.exit(1)

# URLs to fetch (FL AHCA Medicaid initiative / provider enrollment / NPI relevant)
AHCA_URLS = [
    ("medicaid_main", "https://ahca.myflorida.com/medicaid/"),
    ("medicaid_rules", "https://ahca.myflorida.com/medicaid/rules"),
    ("medicaid_policy", "https://ahca.myflorida.com/medicaid/medicaid-policy-quality-and-operations"),
    ("state_plan", "https://ahca.myflorida.com/medicaid/medicaid-state-plan-under-title-xix-of-the-social-security-act-medical-assistance-program"),
    ("provider_assistance", "https://ahca.myflorida.com/medicaid/medicaid-policy-quality-and-operations/medicaid-operations/recipient-and-provider-assistance/provider-services"),
    ("fee_schedules", "https://ahca.myflorida.com/medicaid/rules/rule-59g-4.002-provider-reimbursement-schedules-and-billing-codes"),
]

# Base dir: provider-roster-credentialing/data/ahca_docs
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "ahca_docs"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 25.0
USER_AGENT = "Mobius-ProviderRoster/1.0 (credentialing report; fetch AHCA docs)"


def _strip_html_to_text(html: str) -> str:
    """Minimal HTML-to-text: remove tags, collapse whitespace, preserve structure."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_url(name: str, url: str) -> str | None:
    """Fetch URL and return markdown-ish text, or None on failure."""
    try:
        resp = httpx.get(url, timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        html = resp.text
        text = _strip_html_to_text(html)
        if len(text) < 100:
            return None
        return f"# {name}\nSource: {url}\nFetched: {datetime.utcnow().isoformat()}Z\n\n{text[:50000]}"  # Cap size
    except Exception as e:
        print(f"  {name}: failed - {e}", file=sys.stderr)
        return None


def main() -> int:
    print(f"Fetching FL AHCA docs to {DATA_DIR}")
    ok = 0
    for name, url in AHCA_URLS:
        print(f"  {name}...", end=" ", flush=True)
        content = fetch_url(name, url)
        if content:
            out = DATA_DIR / f"{name}.md"
            out.write_text(content, encoding="utf-8")
            print(f"ok ({len(content):,} chars)")
            ok += 1
        else:
            print("failed")
    print(f"Stored {ok}/{len(AHCA_URLS)} docs")
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
