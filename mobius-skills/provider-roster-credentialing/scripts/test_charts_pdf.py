#!/usr/bin/env python3
"""Test charts-pdf endpoint: verify PDF is generated and returned."""
import json
import os
import sys
import urllib.request

API_BASE = (os.environ.get("CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL") or "http://localhost:8011").rstrip("/")
# charts-pdf expects base URL without /report - orchestrator uses base from env
BASE = API_BASE.replace("/report", "").rstrip("/") or API_BASE

def main():
    url = f"{BASE}/report-from-steps/charts-pdf"
    body = {
        "org_name": "Test Org",
        "final_md": "# Test Report\n\nThis is a test.\n\n## Section\n\nSome content.",
        "step_outputs": [
            {"step_id": "opportunity_sizing", "label": "Opportunity", "csv_content": "level,amount\nA,100000\nB,5000\nC,20000\nD,3000\nE,10000\nTotal,48000", "row_count": 6},
        ],
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:500]}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

    has_final_md = bool(out.get("final_md"))
    has_pdf = bool(out.get("pdf_base64"))
    pdf_len = len(out.get("pdf_base64") or "")
    charts = out.get("charts") or []

    print(f"final_md: {len(out.get('final_md') or '')} chars")
    print(f"pdf_base64: {'yes' if has_pdf else 'NO'} ({pdf_len} bytes)")
    print(f"charts: {len(charts)}")
    if has_pdf:
        print("OK: PDF generated")
        return 0
    else:
        print("FAIL: No pdf_base64 in response")
        return 1

if __name__ == "__main__":
    sys.exit(main())
