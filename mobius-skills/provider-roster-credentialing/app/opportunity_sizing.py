"""
Revenue Waterfall & Opportunity Sizing (Step 10).

Five levels: A) Guaranteed, B) At-risk, C) Enrollment gap, D) Taxonomy optimization, E) Rate gap.
See docs/OPPORTUNITY_SIZING_METHODOLOGY.md.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.utilization_benchmarks import ORG_BENCHMARK_KEY, fetch_benchmarks, get_benchmark_for_npi

logger = logging.getLogger(__name__)

# File names for traceability (used when passed to critique module)
BENCHMARKS_FILE = "step1_benchmarks.csv"

DEFAULT_MEMBER_PROXY = 100


def _npi_entry(
    npi: str,
    taxonomy: str,
    zip5: str,
    state: str,
    bucket: str,
    provider_name: str = "",
    pml_source_file: str = "",
) -> dict[str, Any]:
    return {
        "npi": npi,
        "taxonomy": taxonomy,
        "zip5": zip5,
        "state": state,
        "bucket": bucket,
        "provider_name": provider_name,
        "pml_source_file": pml_source_file,
    }


def _collect_entries(
    validated: list[dict[str, Any]],
    flagged: list[dict[str, Any]],
    missing: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build unified list of NPI entries from validated, flagged, missing.
    Validated takes precedence over missing — an NPI in PML (validated) cannot also be missing.
    """
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    validated_npis = {str(r.get("npi") or "").strip().zfill(10) for r in (validated or []) if r.get("npi")}

    for r in validated or []:
        npi = str(r.get("npi") or "").strip().zfill(10)
        if not npi or npi in seen:
            continue
        seen.add(npi)
        zip9 = str(r.get("zip9") or "").strip()
        zip5 = zip9[:5] if len(zip9) >= 5 else ""
        state = (str(r.get("state") or "FL").strip().upper()) or "FL"
        tax = str(r.get("taxonomy_code") or "").strip()
        if tax:
            name = str(r.get("provider_name") or r.get("name") or "").strip()
            entries.append(_npi_entry(npi, tax, zip5, state, "valid", name, "step6_pml_validation.csv"))

    for r in flagged or []:
        npi = str(r.get("npi") or "").strip().zfill(10)
        if not npi or npi in seen:
            continue
        seen.add(npi)
        zip9 = str(r.get("zip9") or "").strip()
        zip5 = zip9[:5] if len(zip9) >= 5 else (re.sub(r"[^0-9]", "", str(r.get("zip") or ""))[:5])
        state = (str(r.get("state") or "FL").strip().upper()) or "FL"
        tax = str(r.get("taxonomy_code") or "").strip()
        if tax:
            name = str(r.get("provider_name") or r.get("name") or "").strip()
            entries.append(_npi_entry(npi, tax, zip5, state, "flagged", name, "step6_pml_validation.csv"))

    for r in missing or []:
        npi = str(r.get("npi") or "").strip().zfill(10)
        if not npi or npi in seen:
            continue
        if npi in validated_npis:
            logger.warning("Excluding NPI %s from missing — already in validated (PML). Cross-section fix.", npi)
            continue
        seen.add(npi)
        zip5 = (str(r.get("site_zip5") or "").strip())[:5]
        state = (str(r.get("site_state") or "FL").strip().upper()) or "FL"
        tax = str(r.get("suggested_taxonomy_code") or "").strip()
        if tax:
            name = str(r.get("name") or r.get("provider_name") or "").strip()
            entries.append(_npi_entry(npi, tax, zip5, state, "missing", name, "step7_missing_pml_enrollment.csv"))

    return entries


def _parse_benchmark_source(source: str) -> tuple[str, str]:
    """Parse benchmark_source into (geography_type, geography_value) for step1_benchmarks.csv lookup."""
    if not source or source == "none":
        return ("", "")
    if source == ORG_BENCHMARK_KEY:
        return ("org", "org")
    if ":" in source:
        geo_type, geo_val = source.split(":", 1)
        return (geo_type.strip(), geo_val.strip())
    return (source, "")


def _revenue_per_claim_for_taxonomy(
    benchmarks: dict[str, dict[str, dict[str, Any]]],
    taxonomy: str,
    zip5: str = "",
    state: str = "FL",
) -> float:
    """Get revenue_per_claim for a taxonomy at best available geography."""
    state_clean = (state or "FL").strip().upper() or "FL"
    zip5_clean = (zip5 or "").strip()[:5]
    for key in [
        f"zip5:{zip5_clean}" if zip5_clean else None,
        f"state:{state_clean}",
        "national:US",
    ]:
        if not key or key not in benchmarks or taxonomy not in benchmarks[key]:
            continue
        v = float(benchmarks[key][taxonomy].get("revenue_per_claim") or 0)
        if v > 0:
            return v
    return 0.0


def compute_opportunity_sizing(
    bq_client: Any,
    validated: list[dict[str, Any]],
    flagged: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    *,
    project: str,
    landing_dataset: str,
    marts_dataset: str,
    period: str = "2024",
    member_proxy: int = DEFAULT_MEMBER_PROXY,
    org_benchmark: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Compute revenue waterfall & opportunity sizing (A through E).

    Returns:
        {
          "guaranteed_revenue": float,      # A
          "at_risk_revenue": float,         # B
          "missing_pml_revenue": float,     # C
          "taxonomy_optimization_opportunity": float,  # D
          "org_vs_state_opportunity": float,           # E
          "total_opportunity": float,       # B + C + D + E
          "methodology": str,               # Text to include in report
        }
    """
    from app.pml_validation import _nppes_npi_status, _tml_codes

    entries = _collect_entries(validated, flagged, missing)
    if not entries:
        return {
            "guaranteed_revenue": 0.0,
            "at_risk_revenue": 0.0,
            "missing_pml_revenue": 0.0,
            "taxonomy_optimization_opportunity": 0.0,
            "org_vs_state_opportunity": 0.0,
            "total_opportunity": 0.0,
            "provider_counts": {"A": 0, "B": 0, "C": 0},
            "methodology": _get_methodology_text(),
            "npi_detail": [],
        }

    taxonomy_codes = list(dict.fromkeys(e["taxonomy"] for e in entries if e["taxonomy"]))
    benchmarks = fetch_benchmarks(
        bq_client,
        taxonomy_codes,
        project=project,
        marts_dataset=marts_dataset,
        period=period,
    )

    # NPPES + TML for D (taxonomy optimization)
    npis = list(dict.fromkeys(e["npi"] for e in entries))
    nppes_status = _nppes_npi_status(bq_client, npis, project)
    tml_codes = _tml_codes(bq_client, project, landing_dataset) if landing_dataset else set()

    org_rev_per_claim = float(org_benchmark.get("revenue_per_claim") or 0) if org_benchmark else 0.0
    state_key = "state:FL"

    guaranteed = 0.0
    at_risk = 0.0
    missing_rev = 0.0
    taxonomy_opt = 0.0
    rate_gap = 0.0
    npi_detail: list[dict[str, Any]] = []

    for e in entries:
        bm, benchmark_source = get_benchmark_for_npi(
            benchmarks,
            e["taxonomy"],
            zip5=e["zip5"],
            state=e["state"],
            org_benchmark=org_benchmark,
        )
        rev_per_member = float(bm.get("revenue_per_member") or 0)
        rev_per_claim_cur = float(bm.get("revenue_per_claim") or 0)
        base_revenue = rev_per_member * member_proxy if rev_per_member > 0 else 0.0

        geo_type, geo_val = _parse_benchmark_source(benchmark_source)

        # Base row fields for tick-and-tie
        row: dict[str, Any] = {
            "npi": e["npi"],
            "provider_name": (e.get("provider_name") or "")[:80],
            "bucket": e["bucket"],
            "pml_source_file": e.get("pml_source_file", ""),
            "pml_row_key": f"npi={e['npi']},taxonomy_code={e['taxonomy']}",
            "taxonomy_code": e["taxonomy"],
            "zip5": e["zip5"],
            "state": e["state"],
            "benchmark_source": benchmark_source,
            "benchmark_file": BENCHMARKS_FILE,
            "benchmark_geography_type": geo_type,
            "benchmark_geography_value": geo_val,
            "benchmark_row_key": f"taxonomy_code={e['taxonomy']},geography_type={geo_type},geography_value={geo_val}" if geo_type else "",
            "revenue_per_member": round(rev_per_member, 2),
            "revenue_per_claim": round(rev_per_claim_cur, 2),
            "member_proxy_used": member_proxy,
            "base_revenue": round(base_revenue, 2),
            "taxonomy_opt_uplift": 0.0,
            "taxonomy_opt_detail": "",
            "rate_gap_uplift": 0.0,
            "rate_gap_detail": "",
        }

        # A, B, C
        if e["bucket"] == "valid":
            guaranteed += base_revenue
        elif e["bucket"] == "flagged":
            at_risk += base_revenue
        else:
            missing_rev += base_revenue

        # D: Taxonomy optimization — best valid taxonomy vs current.
        # Only for valid/flagged (already enrolled). Exclude missing — they are not in PML yet;
        # their opportunity is C (enroll). Adding D for missing would double-count (enroll + taxonomy switch
        # when enrollment is the single recommendation).
        # Exclude entity_type=2 (organizations): suggestions like "convert residential treatment center
        # to community mental health center" don't apply — orgs can't change taxonomy type that way.
        d_uplift = 0.0
        npi_entity_type = (nppes_status.get(e["npi"], {}).get("entity_type_code") or "1").strip()
        if e["bucket"] in ("valid", "flagged") and npi_entity_type != "2":
            nppes_tax = nppes_status.get(e["npi"], {}).get("nppes_taxonomies") or set()
            valid_taxonomies = [t for t in nppes_tax if t in tml_codes] if tml_codes else list(nppes_tax)
            if not valid_taxonomies:
                valid_taxonomies = [e["taxonomy"]]

            best_tax = ""
            best_rpc = 0.0
            for t in valid_taxonomies:
                rpc = _revenue_per_claim_for_taxonomy(benchmarks, t, e["zip5"], e["state"])
                if rpc > best_rpc:
                    best_rpc = rpc
                    best_tax = t

            if best_tax and best_tax != e["taxonomy"] and rev_per_claim_cur > 0 and best_rpc > rev_per_claim_cur:
                pct_diff = (best_rpc - rev_per_claim_cur) / rev_per_claim_cur
                d_uplift = base_revenue * pct_diff
                taxonomy_opt += d_uplift
                pct_pct = round(pct_diff * 100, 1)
                row["taxonomy_opt_uplift"] = round(d_uplift, 2)
                row["taxonomy_opt_detail"] = f"best_taxonomy={best_tax};current={e['taxonomy']};best_rpc={best_rpc:.2f};current_rpc={rev_per_claim_cur:.2f};pct_diff={pct_pct}%"

        # E: Org vs state — state rate higher than org
        state_bm = benchmarks.get(state_key, {}).get(e["taxonomy"], {})
        state_rpc = float(state_bm.get("revenue_per_claim") or 0)
        e_uplift = 0.0
        if org_rev_per_claim > 0 and state_rpc > org_rev_per_claim:
            pct_diff = (state_rpc - org_rev_per_claim) / org_rev_per_claim
            e_uplift = base_revenue * pct_diff
            rate_gap += e_uplift
            pct_pct = round(pct_diff * 100, 1)
            row["rate_gap_uplift"] = round(e_uplift, 2)
            row["rate_gap_detail"] = f"state_rpc={state_rpc:.2f};org_rpc={org_rev_per_claim:.2f};pct_diff={pct_pct}%"

        npi_detail.append(row)

    total_opp = at_risk + missing_rev + taxonomy_opt + rate_gap

    # Provider counts for report consistency (avoid count×amount mismatch)
    provider_counts = {"A": len([r for r in npi_detail if (r.get("bucket") or "").strip().lower() == "valid"])}
    provider_counts["B"] = len([r for r in npi_detail if (r.get("bucket") or "").strip().lower() == "flagged"])
    provider_counts["C"] = len([r for r in npi_detail if (r.get("bucket") or "").strip().lower() == "missing"])

    return {
        "guaranteed_revenue": round(guaranteed, 2),
        "at_risk_revenue": round(at_risk, 2),
        "missing_pml_revenue": round(missing_rev, 2),
        "taxonomy_optimization_opportunity": round(taxonomy_opt, 2),
        "org_vs_state_opportunity": round(rate_gap, 2),
        "total_opportunity": round(total_opp, 2),
        "provider_counts": provider_counts,
        "methodology": _get_methodology_text(),
        "npi_detail": npi_detail,
    }


def _get_methodology_text() -> str:
    """Return methodology text to include in report."""
    try:
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "docs" / "OPPORTUNITY_SIZING_METHODOLOGY.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return (
        "Revenue Waterfall: A=Guaranteed (valid PML), B=At-risk (flagged), C=Enrollment (missing), "
        "D=Taxonomy optimization, E=Org vs state rate gap. Uplifts use revenue per claim."
    )
