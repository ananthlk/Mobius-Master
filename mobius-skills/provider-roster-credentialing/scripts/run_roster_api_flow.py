#!/usr/bin/env python3
"""
Run the Provider Roster API flow (Steps 1–6) and save step outputs for baseline comparison.

Use the last run as baseline, rerun with new logic, and diff before/after each step.

Prerequisites:
  - Provider-roster API running (e.g. uvicorn app.main:app --port 8010)
  - CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL=http://localhost:8010 (or set --api-url)
  - BigQuery env: BQ_PROJECT, BQ_LANDING_MEDICAID_DATASET

Usage:
  # First run (baseline): save outputs for comparison
  uv run python scripts/run_roster_api_flow.py --org-name "David Lawrence" --output-dir reports/baseline

  # Second run (after code changes): compare against baseline
  uv run python scripts/run_roster_api_flow.py --org-name "David Lawrence" --output-dir reports/new --baseline-dir reports/baseline

  # Run and save without comparison
  uv run python scripts/run_roster_api_flow.py --org-name "David Lawrence"
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPT_DIR.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

# Load env (mobius-config at workspace root; mobius-skills and mobius-config are siblings)
_workspace_root = _SKILL_ROOT.parent.parent
for env_path in (
    _workspace_root / "mobius-config" / ".env",
    _workspace_root / ".env",
    _SKILL_ROOT.parent / ".env",
    _SKILL_ROOT / ".env",
):
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path, override=False)
        except Exception:
            pass


def _api_base() -> str:
    url = (os.environ.get("CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL") or "").strip()
    if url:
        return url.rstrip("/")
    return "http://localhost:8010"


def _post(path: str, body: dict, timeout: int = 120) -> dict:
    base = _api_base()
    url = f"{base}{path}"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _to_csv(rows: list[dict], fieldnames: list[str] | None = None) -> str:
    import io
    if not rows:
        return ""
    keys = fieldnames or list(rows[0].keys())
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if v is None else str(v)) for k, v in r.items()})
    return out.getvalue()


def _flatten_providers(associated: dict) -> list[dict]:
    rows = []
    for loc_id, provs in (associated or {}).items():
        for p in provs or []:
            rows.append({"location_id": loc_id, **{k: v for k, v in p.items() if k != "location_id"}})
    return rows


def _run_flow(org_name: str, api_base: str, output_dir: Path) -> dict:
    """Run the flow and save step outputs. Returns summary dict for comparison."""
    os.environ["CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL"] = api_base
    summary: dict = {}

    # Step 1: Ensure revenue metrics (utilization benchmarking) — always run first
    print("Step 1: Ensuring revenue metrics (utilization benchmarking)…")
    step9 = _post("/ensure-benchmarks", {"period": "2024", "state": "FL"})
    summary["benchmarks_status"] = step9.get("status", "unknown")
    if step9.get("status") == "ok":
        print("  ✓ Benchmarks table populated.")
    else:
        print(f"  ⚠ Benchmarks: {step9.get('error', step9.get('status', 'unknown'))}")

    # Step 1: Search org
    print("Step 1: Search org…")
    step1 = _post("/search/org-names", {"name": org_name, "state": "FL", "limit": 20})
    org_results = step1.get("results") or []
    org_npis = [r.get("npi") for r in org_results if r.get("npi")]
    org_npis = [str(n).strip().zfill(10) for n in org_npis if n][:50]
    summary["org_npis_count"] = len(org_npis)
    (output_dir / "step1_identify_org.json").write_text(json.dumps(step1, indent=2), encoding="utf-8")
    rows1 = [{"npi": r.get("npi"), "name": r.get("name"), "source": r.get("source")} for r in org_results]
    (output_dir / "step1_identify_org.csv").write_text(_to_csv(rows1) or "npi,name,source\n(no results)", encoding="utf-8")
    print(f"  Found {len(org_npis)} org NPIs")

    if not org_npis:
        print("  No org NPIs; stopping.")
        return summary

    # Step 2: Find locations
    print("Step 2: Find locations…")
    step2 = _post("/find-locations", {"org_npis": org_npis, "state": "FL"})
    locations = step2.get("locations") or []
    summary["locations_count"] = len(locations)
    (output_dir / "step2_find_locations.json").write_text(json.dumps(step2, indent=2), encoding="utf-8")
    (output_dir / "step2_find_locations.csv").write_text(
        _to_csv(locations) or "location_id,site_address,site_city,site_state,site_zip5\n(no locations)", encoding="utf-8"
    )
    print(f"  Found {len(locations)} locations")

    if not locations:
        print("  No locations; stopping.")
        return summary

    # Step 3: Find associated providers (includes active roster, roster_status)
    print("Step 3: Find associated providers…")
    step3 = _post("/find-associated-providers", {
        "org_npis": org_npis,
        "locations": locations,
        "org_name": org_name,
    })
    associated = step3.get("associated_providers") or {}
    active_roster = step3.get("active_roster") or {}
    total_providers = sum(len(v) for v in associated.values())
    active_providers = sum(len(v) for v in active_roster.values())
    summary["providers_total"] = total_providers
    summary["providers_active"] = active_providers
    summary["active_roster_cutoff"] = step3.get("active_roster_cutoff")
    (output_dir / "step3_find_associated_providers.json").write_text(json.dumps({
        k: v for k, v in step3.items() if k != "associated_providers"
    } | {"associated_providers_keys": list(associated.keys()), "active_roster_keys": list(active_roster.keys())}, indent=2), encoding="utf-8")
    prov_rows = _flatten_providers(associated)
    cols = ["location_id", "npi", "name", "entity_type", "match_type", "association_likelihood", "roster_status", "name_status"]
    (output_dir / "step3_find_associated_providers.csv").write_text(
        _to_csv(prov_rows, cols) or "location_id,npi,name,entity_type,match_type,association_likelihood,roster_status,name_status\n(no providers)", encoding="utf-8"
    )
    active_rows = _flatten_providers(active_roster)
    (output_dir / "step3_active_roster.csv").write_text(
        _to_csv(active_rows, cols) or "location_id,npi,name,entity_type,match_type,association_likelihood,roster_status\n(no active providers)", encoding="utf-8"
    )
    print(f"  Total providers: {total_providers}, Active roster: {active_providers}")

    # Downstream uses active_roster
    downstream = active_roster if active_roster else associated

    # Org benchmark: utilization metrics for active roster NPIs (used by Step 10)
    print("Org benchmark: utilization for active roster…")
    step_org_bm = _post("/org-benchmark", {"active_roster": downstream, "period": "2024"})
    org_benchmark = step_org_bm if isinstance(step_org_bm, dict) and step_org_bm.get("revenue_per_member") is not None else None
    if org_benchmark:
        print(f"  Org: ${org_benchmark.get('revenue_per_member', 0):,.0f}/member, {org_benchmark.get('member_count', 0)} members, {org_benchmark.get('npi_count', 0)} NPIs")
    else:
        print("  (no DOGE data for active roster)")

    # Step 4: Find services by location
    print("Step 4: Find services by location…")
    step4 = _post("/find-services-by-location", {
        "org_npis": org_npis,
        "locations": locations,
        "associated_providers": downstream,
        "state": "FL",
    })
    svc_by_loc = step4.get("services_by_location") or {}
    svc_rows = []
    for loc_id, rows in svc_by_loc.items():
        for r in rows or []:
            svc_rows.append({"location_id": loc_id, **r})
    summary["services_count"] = len(svc_rows)
    (output_dir / "step4_find_services_by_location.csv").write_text(
        _to_csv(svc_rows) or "location_id,taxonomy_code,taxonomy_description,medicaid_approved\n(no services)", encoding="utf-8"
    )
    print(f"  Found {len(svc_rows)} service rows")

    # Step 5: Historic billing
    print("Step 5: Historic billing patterns…")
    step5 = _post("/historic-billing-patterns", {
        "associated_providers": downstream,
        "period_start": "2024-01",
        "period_end": "2024-12",
    })
    by_code = step5.get("by_code") or []
    sm = step5.get("summary") or {}
    summary["historic_claims"] = sm.get("total_claims", 0)
    summary["historic_paid"] = sm.get("total_paid", 0)
    summary["historic_codes"] = len(by_code)
    (output_dir / "step5_historic_billing.csv").write_text(
        _to_csv(by_code) or "hcpcs_code,description,entity_type,claim_count,total_paid\n(no billing)", encoding="utf-8"
    )
    print(f"  {sm.get('total_claims', 0)} claims, ${sm.get('total_paid', 0):,.0f} paid")

    # Step 5b: FL HCPCS-level state benchmarks (for Section E rate gap table)
    print("Step 5b: HCPCS state benchmarks (FL)…")
    step5b = _post("/hcpcs-state-benchmarks", {"period": "2024", "state": "FL"})
    hcpcs_rows = step5b.get("rows") or []
    hcpcs_cols = ["hcpcs_code", "claim_count", "total_paid", "revenue_per_claim"]
    (output_dir / "step5b_hcpcs_state_benchmarks.csv").write_text(
        _to_csv(hcpcs_rows, hcpcs_cols) or "hcpcs_code,claim_count,total_paid,revenue_per_claim\n(no benchmarks)",
        encoding="utf-8",
    )
    print(f"  {len(hcpcs_rows)} HCPCS codes with FL state avg")

    # Step 6: PML validation (for active NPIs)
    print("Step 6: PML validation…")
    step6 = _post("/pml-validation", {
        "org_npis": org_npis,
        "locations": locations,
        "associated_providers": downstream,
        "program_state": "FL",
        "product": "medicaid",
    })
    validated = step6.get("validated") or []
    flagged = step6.get("flagged") or []
    sm6 = step6.get("summary") or {}
    summary["pml_valid"] = sm6.get("valid", 0)
    summary["pml_flagged"] = sm6.get("flagged", 0)
    summary["pml_total"] = sm6.get("total", 0)
    pml_rows = []
    for r in validated + flagged:
        pml_rows.append({
            "npi": r.get("npi"),
            "provider_name": (r.get("provider_name") or "")[:60],
            "taxonomy_code": r.get("taxonomy_code"),
            "zip9": r.get("zip9"),
            "valid": "yes" if r.get("valid") else "no",
            "issues": ";".join(r.get("issues") or []),
        })
    (output_dir / "step6_pml_validation.csv").write_text(
        _to_csv(pml_rows) or "npi,provider_name,taxonomy_code,zip9,valid,issues\n(no PML rows)", encoding="utf-8"
    )
    active_count = sum(1 for provs in (downstream or {}).values() for p in provs or [])
    pml_npi_count = len(set(r.get("npi") for r in pml_rows if r.get("npi")))
    not_in_pml = max(0, active_count - pml_npi_count)
    summary["missing_pml_count"] = not_in_pml
    print(f"  PML: {summary['pml_valid']} valid, {summary['pml_flagged']} flagged ({summary['pml_total']} rows)")
    if not_in_pml:
        print(f"  Note: {not_in_pml} active roster NPI(s) have no PML rows (not enrolled in Medicaid)")

    # Step 7: Missing PML enrollment (suggest taxonomy + location for each)
    print("Step 7: Missing PML enrollment…")
    step7 = _post("/missing-pml-enrollment", {
        "locations": locations,
        "active_roster": active_roster if active_roster else downstream,
    })
    missing_list = step7.get("missing") or []
    sm7 = step7.get("summary") or {}
    summary["missing_pml_enrollment"] = sm7.get("total", 0)
    cols7 = ["npi", "name", "location_id", "site_address_line_1", "site_city", "site_state", "site_zip5", "site_zip9", "suggested_taxonomy_code", "suggested_taxonomy_description", "nppes_taxonomies", "tml_approved"]
    (output_dir / "step7_missing_pml_enrollment.csv").write_text(
        _to_csv(missing_list, cols7) or "npi,name,location_id,site_address_line_1,site_city,site_state,site_zip5,site_zip9,suggested_taxonomy_code,suggested_taxonomy_description,tml_approved\n(no missing)",
        encoding="utf-8",
    )
    print(f"  {len(missing_list)} provider(s) to enroll with suggested taxonomy + location")

    # Benchmarks CSV: filtered to client-relevant taxonomies and ZIPs
    taxonomy_codes = set()
    for r in validated + flagged:
        t = (r.get("taxonomy_code") or "").strip()
        if t:
            taxonomy_codes.add(t)
    for r in missing_list:
        t = (r.get("suggested_taxonomy_code") or "").strip()
        if t:
            taxonomy_codes.add(t)
    for loc_id, rows in (step4.get("services_by_location") or {}).items():
        for r in rows or []:
            t = (r.get("taxonomy_code") or "").strip()
            if t:
                taxonomy_codes.add(t)
    zip5_list = []
    for loc in locations:
        z = (str(loc.get("site_zip5") or loc.get("site_zip") or "").strip())[:5]
        if len(z) == 5 and z not in zip5_list:
            zip5_list.append(z)
    bm_export = _post("/benchmarks-export", {
        "period": "2024",
        "taxonomy_codes": list(taxonomy_codes) if taxonomy_codes else None,
        "zip5_list": zip5_list if zip5_list else None,
    })
    bm_rows = bm_export.get("rows") or []
    bm_cols = ["taxonomy_code", "geography_type", "geography_value", "period", "claim_count", "total_revenue", "member_count", "claims_per_member", "revenue_per_member", "revenue_per_claim"]
    (output_dir / "step1_benchmarks.csv").write_text(
        _to_csv(bm_rows, bm_cols) or "taxonomy_code,geography_type,geography_value,period,claim_count,total_revenue,member_count,claims_per_member,revenue_per_member,revenue_per_claim\n(no benchmarks)",
        encoding="utf-8",
    )
    print(f"  ✓ Benchmarks CSV (filtered): {len(bm_rows)} rows ({len(taxonomy_codes)} taxonomies, {len(zip5_list)} ZIPs)")

    # Step 10: Opportunity sizing (revenue waterfall A–E)
    print("Step 10: Opportunity sizing (revenue waterfall)…")
    step10 = _post("/opportunity-sizing", {
        "validated": validated,
        "flagged": flagged,
        "missing_enrollment": missing_list,
        "org_benchmark": org_benchmark,
        "member_proxy": 100,
    })
    summary["guaranteed_revenue"] = step10.get("guaranteed_revenue", 0)
    summary["at_risk_revenue"] = step10.get("at_risk_revenue", 0)
    summary["missing_pml_revenue"] = step10.get("missing_pml_revenue", 0)
    summary["taxonomy_optimization_opportunity"] = step10.get("taxonomy_optimization_opportunity", 0)
    summary["org_vs_state_opportunity"] = step10.get("org_vs_state_opportunity", 0)
    summary["total_opportunity"] = step10.get("total_opportunity", 0)
    (output_dir / "step10_opportunity_sizing.json").write_text(
        json.dumps({k: v for k, v in step10.items() if k != "methodology"}, indent=2),
        encoding="utf-8",
    )
    (output_dir / "step10_opportunity_sizing_methodology.md").write_text(
        step10.get("methodology", ""),
        encoding="utf-8",
    )
    pc = step10.get("provider_counts") or {}
    opp_rows = [
        {"level": "A", "label": "Guaranteed revenue", "amount": step10.get("guaranteed_revenue", 0), "provider_count": pc.get("A")},
        {"level": "B", "label": "At-risk revenue", "amount": step10.get("at_risk_revenue", 0), "provider_count": pc.get("B")},
        {"level": "C", "label": "Missing PML revenue", "amount": step10.get("missing_pml_revenue", 0), "provider_count": pc.get("C")},
        {"level": "D", "label": "Taxonomy optimization opportunity", "amount": step10.get("taxonomy_optimization_opportunity", 0), "provider_count": None},
        {"level": "E", "label": "Org vs state opportunity", "amount": step10.get("org_vs_state_opportunity", 0), "provider_count": None},
        {"level": "Total", "label": "Total opportunity (B+C+D+E)", "amount": step10.get("total_opportunity", 0), "provider_count": None},
    ]
    (output_dir / "step10_opportunity_sizing.csv").write_text(
        _to_csv(opp_rows, ["level", "label", "amount", "provider_count"]),
        encoding="utf-8",
    )
    npi_detail = step10.get("npi_detail") or []
    npi_detail_cols = [
        "npi", "provider_name", "bucket", "pml_source_file", "pml_row_key", "taxonomy_code", "zip5", "state",
        "benchmark_source", "benchmark_file", "benchmark_geography_type", "benchmark_geography_value", "benchmark_row_key",
        "revenue_per_member", "revenue_per_claim", "member_proxy_used", "base_revenue",
        "taxonomy_opt_uplift", "taxonomy_opt_detail", "rate_gap_uplift", "rate_gap_detail",
    ]
    (output_dir / "step10_opportunity_sizing_detail.csv").write_text(
        _to_csv(npi_detail, npi_detail_cols) or "npi,provider_name,bucket,pml_source_file,pml_row_key,taxonomy_code,zip5,state,benchmark_source,benchmark_file,benchmark_geography_type,benchmark_geography_value,benchmark_row_key,revenue_per_member,revenue_per_claim,member_proxy_used,base_revenue,taxonomy_opt_uplift,taxonomy_opt_detail,rate_gap_uplift,rate_gap_detail\n(no detail)",
        encoding="utf-8",
    )
    print(f"  Guaranteed: ${step10.get('guaranteed_revenue', 0):,.0f} | At-risk: ${step10.get('at_risk_revenue', 0):,.0f} | Missing: ${step10.get('missing_pml_revenue', 0):,.0f}")
    print(f"  Taxonomy opt: ${step10.get('taxonomy_optimization_opportunity', 0):,.0f} | Rate gap: ${step10.get('org_vs_state_opportunity', 0):,.0f} | Total opportunity: ${step10.get('total_opportunity', 0):,.0f}")
    pc = step10.get("provider_counts") or {}
    if pc:
        print(f"  Provider counts: A={pc.get('A', '—')} | B={pc.get('B', '—')} | C={pc.get('C', '—')}")
    # Validate step outputs
    from app.step_output_validation import validate_opportunity_sizing
    val_errors = validate_opportunity_sizing(step10, validated, flagged, missing_list)
    if val_errors:
        for err in val_errors:
            print(f"  ⚠ VALIDATION: {err}")
    else:
        print(f"  ✓ NPI-level detail: {len(npi_detail)} rows (tick-and-tie to step6/step7 + step1_benchmarks)")

    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _compare(baseline_dir: Path, new_dir: Path) -> None:
    """Print before/after comparison."""
    def load_summary(d: Path) -> dict:
        p = d / "summary.json"
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    b = load_summary(baseline_dir)
    n = load_summary(new_dir)
    print("\n" + "=" * 60)
    print("BEFORE vs AFTER (baseline vs new run)")
    print("=" * 60)
    keys = ["org_npis_count", "locations_count", "providers_total", "providers_active", "services_count",
            "historic_claims", "historic_paid", "historic_codes", "pml_total", "pml_valid", "pml_flagged",
            "missing_pml_enrollment", "guaranteed_revenue", "at_risk_revenue", "missing_pml_revenue",
            "total_opportunity"]
    for k in keys:
        vb = b.get(k, "—")
        vn = n.get(k, "—")
        if k == "historic_paid" and isinstance(vb, (int, float)) and isinstance(vn, (int, float)):
            diff = vn - vb
            sign = "+" if diff >= 0 else ""
            print(f"  {k}: {vb} → {vn} ({sign}{diff})")
        elif vb != vn:
            print(f"  {k}: {vb} → {vn}")
        else:
            print(f"  {k}: {vb}")
    print("=" * 60)


# Map output files to report step_ids (report-from-steps expects these)
_REPORT_STEP_MAP = {
    "step1_identify_org.csv": "identify_org",
    "step2_find_locations.csv": "find_locations",
    "step3_find_associated_providers.csv": "find_associated_providers",
    "step4_find_services_by_location.csv": "find_services_by_location",
    "step5_historic_billing.csv": "historic_billing_patterns",
    "step5b_hcpcs_state_benchmarks.csv": "hcpcs_state_benchmarks",
    "step6_pml_validation.csv": "step_6",
    "step7_missing_pml_enrollment.csv": "step_7",
    "step10_opportunity_sizing.csv": "opportunity_sizing",
    "step10_opportunity_sizing_detail.csv": "opportunity_sizing_detail",
}


def _assemble_step_outputs(output_dir: Path) -> list[dict]:
    """Build step_outputs from saved flow outputs for report-from-steps."""
    steps = []
    for filename, step_id in _REPORT_STEP_MAP.items():
        path = output_dir / filename
        if path.exists():
            csv_content = path.read_text(encoding="utf-8")
            rows = list(csv.DictReader(io.StringIO(csv_content))) if csv_content.strip() else []
            steps.append({
                "step_id": step_id,
                "label": step_id.replace("_", " ").title(),
                "csv_content": csv_content,
                "row_count": len(rows),
            })
    return steps


def _run_report_local(org_name: str, output_dir: Path) -> dict | None:
    """Run report pipeline in-process (no HTTP). Uses current code."""
    step_outputs = _assemble_step_outputs(output_dir)
    if not step_outputs:
        print("  No step outputs; skipping report.")
        return None
    try:
        from app.waterfall_report import (
            TickAndTieError,
            build_report_context,
            generate_waterfall_draft,
            run_waterfall_composer,
            run_waterfall_validator,
        )
        from app.report_pipeline import run_narrative_critic
    except ImportError as e:
        print(f"  Import failed: {e}")
        return None
    try:
        context = build_report_context(step_outputs)
    except TickAndTieError as e:
        print(f"  Tick-and-tie failed: {e}")
        return None
    import os
    provider = os.environ.get("REPORT_LLM_PROVIDER", "gemini")
    draft_md = generate_waterfall_draft(context, org_name, provider=provider)
    validation_report = run_waterfall_validator(draft_md, context, provider=provider)
    critique_report = run_narrative_critic(draft_md, provider=provider) or ""
    final_md = run_waterfall_composer(
        draft_md, validation_report, context, org_name,
        critique_report=critique_report, provider=provider,
    )
    wt = context.get("waterfall_totals") or {}
    (output_dir / "report_response.json").write_text(json.dumps({
        "validation_status": (
            "BLOCK" if "Validation Status: BLOCK" in (validation_report or "") else
            "COMPOSE_FIX" if "Validation Status: COMPOSE_FIX" in (validation_report or "") else
            "PASS"
        ),
    }, indent=2), encoding="utf-8")
    (output_dir / "report_final.md").write_text(final_md, encoding="utf-8")
    (output_dir / "report_validation.txt").write_text(validation_report or "", encoding="utf-8")
    (output_dir / "report_draft.md").write_text(draft_md, encoding="utf-8")
    print(f"  Report saved: {output_dir / 'report_final.md'}")
    return {"final_md": final_md, "validation_report": validation_report}


def _run_report(api_base: str, org_name: str, output_dir: Path) -> dict | None:
    """Call report-from-steps and save draft/validation/final to output_dir."""
    import time
    from http.client import IncompleteRead, RemoteDisconnected

    step_outputs = _assemble_step_outputs(output_dir)
    if not step_outputs:
        print("  No step outputs; skipping report.")
        return None
    payload = {"org_name": org_name, "step_outputs": step_outputs}
    resp = None
    for attempt in range(4):
        try:
            resp = _post("/report-from-steps", payload, timeout=600)
            break
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode() if e.fp else ""
            except Exception:
                pass
            try:
                err_data = json.loads(body) if body else {}
                (output_dir / "report_error.json").write_text(json.dumps(err_data, indent=2), encoding="utf-8")
                detail = err_data.get("detail", body)
                if isinstance(detail, dict):
                    detail = json.dumps(detail)
                print(f"  Report API error {e.code}: {str(detail)[:800]}")
            except Exception:
                print(f"  Report API error {e.code}: {body[:800]}")
            raise
        except (IncompleteRead, RemoteDisconnected, ConnectionResetError, BrokenPipeError, OSError) as e:
            if attempt < 3:
                delay = 8 * (attempt + 1)
                print(f"  Report request failed ({e}), retrying in {delay}s…")
                time.sleep(delay)
            else:
                raise
    (output_dir / "report_response.json").write_text(json.dumps({
        k: v for k, v in resp.items() if k != "pdf_base64"
    }, indent=2), encoding="utf-8")
    if resp.get("final_md"):
        (output_dir / "report_final.md").write_text(resp["final_md"], encoding="utf-8")
        print(f"  Report saved: {output_dir / 'report_final.md'}")
    if resp.get("validation_report"):
        (output_dir / "report_validation.txt").write_text(resp["validation_report"], encoding="utf-8")
    return resp


def main() -> int:
    parser = argparse.ArgumentParser(description="Run roster API flow and save step outputs for baseline comparison.")
    parser.add_argument("--org-name", required=True, help='Organization name (e.g. "David Lawrence")')
    parser.add_argument("--output-dir", default=None, help="Output directory (default: reports/roster_run_<timestamp>)")
    parser.add_argument("--baseline-dir", default=None, help="Baseline directory for before/after comparison")
    parser.add_argument("--api-url", default=None, help="Provider-roster API base URL")
    parser.add_argument("--report", action="store_true", help="After flow, call report-from-steps and save report")
    parser.add_argument("--local-report", action="store_true", help="Run report in-process (no HTTP); use with --report")
    args = parser.parse_args()

    api_base = (args.api_url or os.environ.get("CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL") or "http://localhost:8010").rstrip("/")
    if args.api_url:
        os.environ["CHAT_SKILLS_PROVIDER_ROSTER_CREDENTIALING_URL"] = api_base

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        output_dir = _SKILL_ROOT / "reports" / "roster_run" / ts
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {output_dir}")
    print(f"API: {api_base}\n")

    try:
        summary = _run_flow(args.org_name.strip(), api_base, output_dir)
    except urllib.error.URLError as e:
        print(f"Could not reach API at {api_base}: {e}")
        print("Start provider-roster API: cd mobius-skills/provider-roster-credentialing && uvicorn app.main:app --port 8010")
        return 1
    except Exception as e:
        print(f"Flow failed: {e}")
        raise

    if args.baseline_dir:
        baseline = Path(args.baseline_dir)
        if baseline.exists():
            _compare(baseline, output_dir)
        else:
            print(f"Baseline dir not found: {baseline}")

    if args.report:
        print("\nGenerating report…")
        try:
            if args.local_report:
                _run_report_local(args.org_name.strip(), output_dir)
            else:
                _run_report(api_base, args.org_name.strip(), output_dir)
        except Exception as e:
            print(f"Report failed: {e}")
            return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
