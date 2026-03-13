"""
Step 10: Potential revenue for missed/errored NPIs.

Uses taxonomy_utilization_benchmarks (ZIP, state, national) to estimate
potential revenue for NPIs in Step 7 (missing PML enrollment) and Step 6 (flagged).
"""
from __future__ import annotations

import logging
from typing import Any

from app.utilization_benchmarks import fetch_benchmarks, get_benchmark_for_npi

logger = logging.getLogger(__name__)

# Default member proxy when no volume data available
DEFAULT_MEMBER_PROXY = 100


def estimate_potential_revenue(
    bq_client: Any,
    missing_enrollment: list[dict[str, Any]],
    flagged: list[dict[str, Any]] | None = None,
    *,
    project: str,
    marts_dataset: str,
    landing_dataset: str | None = None,
    period: str = "2024",
    member_proxy: int = DEFAULT_MEMBER_PROXY,
    org_benchmark: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Estimate potential revenue for NPIs not enrolled (Step 7) or flagged (Step 6).

    Args:
        missing_enrollment: From Step 7 (find_missing_pml_enrollment).
        flagged: Optional Step 6 flagged rows (same shape as validated).
        member_proxy: Members to assume when computing potential revenue (default 100).
        org_benchmark: Optional dict from compute_org_benchmark (utilization for this org's active NPIs).

    Returns:
        {
          "by_npi": [
            {
              "npi": str,
              "name": str,
              "source": "missing" | "flagged",
              "location_id": str,
              "site_zip5": str,
              "site_state": str,
              "taxonomy_code": str,
              "revenue_per_member": float,
              "revenue_per_claim": float,
              "claims_per_member": float,
              "estimated_potential_revenue": float,
              "benchmark_geography": str,
            },
            ...
          ],
          "summary": {
            "total_npis": int,
            "total_estimated_revenue": float,
            "with_benchmark": int,
          },
        }
    """
    entries: list[dict[str, Any]] = []

    for m in missing_enrollment or []:
        entries.append({
            "npi": str(m.get("npi") or "").strip().zfill(10),
            "name": str(m.get("name") or "").strip(),
            "source": "missing",
            "location_id": str(m.get("location_id") or ""),
            "site_zip5": (str(m.get("site_zip5") or "").strip())[:5],
            "site_state": (str(m.get("site_state") or "FL").strip().upper()) or "FL",
            "taxonomy_code": str(m.get("suggested_taxonomy_code") or "").strip(),
        })

    for f in flagged or []:
        npi = str(f.get("npi") or "").strip().zfill(10)
        if not npi:
            continue
        # Avoid duplicate if already in missing
        if any(e.get("npi") == npi and e.get("source") == "missing" for e in entries):
            continue
        zip9 = str(f.get("zip9") or "").strip()
        zip5_from_zip = (str(f.get("zip") or "").strip().replace("-", "")[:5])
        site_zip5 = (zip9[:5] if len(zip9) >= 5 else zip5_from_zip) or ""
        site_state = (str(f.get("state") or "FL").strip().upper()) or "FL"
        entries.append({
            "npi": npi,
            "name": str(f.get("provider_name") or "").strip(),
            "source": "flagged",
            "location_id": "",
            "site_zip5": site_zip5,
            "site_state": site_state,
            "taxonomy_code": str(f.get("taxonomy_code") or "").strip(),
        })

    taxonomy_codes = list(dict.fromkeys(e["taxonomy_code"] for e in entries if e["taxonomy_code"]))
    if not taxonomy_codes:
        return {
            "by_npi": [],
            "summary": {"total_npis": 0, "total_estimated_revenue": 0.0, "with_benchmark": 0},
        }

    benchmarks = fetch_benchmarks(
        bq_client,
        taxonomy_codes,
        project=project,
        marts_dataset=marts_dataset,
        period=period,
    )

    by_npi: list[dict[str, Any]] = []
    total_rev = 0.0
    with_bm = 0

    for e in entries:
        bm, geo = get_benchmark_for_npi(
            benchmarks,
            e["taxonomy_code"],
            zip5=e["site_zip5"],
            state=e["site_state"],
            org_benchmark=org_benchmark,
        )
        rev_per_member = float(bm.get("revenue_per_member") or 0)
        rev_per_claim = float(bm.get("revenue_per_claim") or 0)
        claims_per_member = float(bm.get("claims_per_member") or 0)
        has_benchmark = rev_per_member > 0 or rev_per_claim > 0
        if has_benchmark:
            with_bm += 1

        est_rev = rev_per_member * member_proxy if has_benchmark else 0.0
        total_rev += est_rev

        by_npi.append({
            "npi": e["npi"],
            "name": e["name"],
            "source": e["source"],
            "location_id": e["location_id"],
            "site_zip5": e["site_zip5"],
            "site_state": e["site_state"],
            "taxonomy_code": e["taxonomy_code"],
            "revenue_per_member": round(rev_per_member, 2),
            "revenue_per_claim": round(rev_per_claim, 2),
            "claims_per_member": round(claims_per_member, 2),
            "estimated_potential_revenue": round(est_rev, 2),
            "benchmark_geography": geo,
            "member_proxy_used": member_proxy,
        })

    out: dict[str, Any] = {
        "by_npi": by_npi,
        "summary": {
            "total_npis": len(by_npi),
            "total_estimated_revenue": round(total_rev, 2),
            "with_benchmark": with_bm,
        },
    }
    if org_benchmark:
        out["org_benchmark"] = org_benchmark
    return out
