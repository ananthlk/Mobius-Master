#!/usr/bin/env python3
"""
Analyze why providers fail the active roster cutoff.
Loads step 3 output, fetches NPPES/PML status, applies penalties, and reports breakdown.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPT_DIR.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

# Load env
_root = _SKILL_ROOT.parent
for env_path in (_root / "mobius-config" / ".env", _root / ".env"):
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path, override=False)
        except Exception:
            pass
        break


def main() -> int:
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else _SKILL_ROOT / "reports" / "roster_run_new"
    csv_path = run_dir / "step3_find_associated_providers.csv"
    if not csv_path.exists():
        print(f"Not found: {csv_path}")
        print("Usage: uv run python scripts/analyze_roster_penalties.py [path/to/run_dir]")
        return 1

    # Load providers from CSV (may be from old API - no roster_status/penalties)
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)

    # Need org_name and locations for find_associated_providers - get from step1/step2
    org_name = "David Lawrence"  # default
    step1 = run_dir / "step1_identify_org.json"
    step2 = run_dir / "step2_find_locations.json"
    if step2.exists():
        loc_data = json.loads(step2.read_text(encoding="utf-8"))
        locations = loc_data.get("locations") or []
    else:
        locations = []

    # Get unique NPIs and their pre-penalty scores from CSV
    npi_to_row = {}
    for r in rows:
        npi = (r.get("npi") or "").strip()
        if npi:
            # Pre-penalty score from CSV (old API) or we'll recompute
            score = int(r.get("association_likelihood") or 0)
            if npi not in npi_to_row or int(npi_to_row[npi].get("association_likelihood") or 0) < score:
                npi_to_row[npi] = dict(r)

    npis = list(npi_to_row.keys())
    print(f"Loaded {len(npis)} unique NPIs from {csv_path}")
    if not npis or not locations:
        print("Need NPIs and locations. Exiting.")
        return 1

    try:
        from google.cloud import bigquery
        bq = bigquery.Client(project=os.environ.get("BQ_PROJECT", "mobius-os-dev"))
    except Exception as e:
        print(f"BigQuery not available: {e}")
        return 1

    from app.associate_providers import (
        _fetch_nppes_status,
        _fetch_pml_status,
        _org_name_mismatch,
        ACTIVE_ROSTER_CUTOFF,
        _PENALTY_NAME_NOT_FOUND,
        _PENALTY_NOT_IN_NPPES,
        _PENALTY_NPPES_DEACTIVATED,
        _PENALTY_PML_INACTIVE,
        _PENALTY_ORG_NAME_MISMATCH,
    )

    proj = os.environ.get("BQ_PROJECT", "mobius-os-dev")
    land_ds = os.environ.get("BQ_LANDING_MEDICAID_DATASET") or "landing_medicaid_npi_dev"

    nppes_status = _fetch_nppes_status(bq, npis, proj)
    pml_status = _fetch_pml_status(bq, npis, proj, land_ds)

    # Apply penalties and track why each failed
    cutoff = ACTIVE_ROSTER_CUTOFF
    breakdown = {
        "active": 0,
        "historic": 0,
        "penalty_name_not_found": 0,
        "penalty_not_in_nppes": 0,
        "penalty_nppes_deactivated": 0,
        "penalty_pml_inactive": 0,
        "penalty_org_name_mismatch": 0,
    }
    score_dist = {}
    failed_reasons: list[tuple[str, int, str]] = []  # (npi, final_score, reasons)

    for npi, row in npi_to_row.items():
        score = int(row.get("association_likelihood") or 0)
        name = (row.get("name") or "").strip()

        ns = nppes_status.get(npi, {"in_nppes": False, "active": False, "org_name": ""})
        ps = pml_status.get(npi, {"in_pml": False, "active": False})

        reasons = []
        if not name:
            score = max(0, score - _PENALTY_NAME_NOT_FOUND)
            reasons.append("no_name")
            breakdown["penalty_name_not_found"] += 1
        if not ns["in_nppes"]:
            score = max(0, score - _PENALTY_NOT_IN_NPPES)
            reasons.append("not_in_nppes")
            breakdown["penalty_not_in_nppes"] += 1
        elif not ns["active"]:
            score = max(0, score - _PENALTY_NPPES_DEACTIVATED)
            reasons.append("nppes_deactivated")
            breakdown["penalty_nppes_deactivated"] += 1
        if ps.get("in_pml") and not ps.get("active"):
            score = max(0, score - _PENALTY_PML_INACTIVE)
            reasons.append("pml_inactive")
            breakdown["penalty_pml_inactive"] += 1
        if org_name and _org_name_mismatch(org_name, ns.get("org_name") or ""):
            score = max(0, score - _PENALTY_ORG_NAME_MISMATCH)
            reasons.append("org_name_mismatch")
            breakdown["penalty_org_name_mismatch"] += 1

        final = min(100, score)
        score_dist[final] = score_dist.get(final, 0) + 1

        if final >= cutoff:
            breakdown["active"] += 1
        else:
            breakdown["historic"] += 1
            if reasons:
                failed_reasons.append((npi, final, ",".join(reasons)))

    # Not-in-NPPES breakdown: how many are in PML?
    not_in_nppes_npis = [npi for npi in npis if not nppes_status.get(npi, {}).get("in_nppes")]
    in_pml_but_not_nppes = [n for n in not_in_nppes_npis if pml_status.get(n, {}).get("in_pml")]
    in_pml_active_but_not_nppes = [n for n in in_pml_but_not_nppes if pml_status.get(n, {}).get("active")]

    print("\n" + "=" * 60)
    print("ROSTER PENALTY ANALYSIS")
    print("=" * 60)
    print(f"Org: {org_name}")
    print(f"Cutoff: {cutoff}")
    print(f"Total NPIs: {len(npi_to_row)}")
    print()
    print("Outcome:")
    print(f"  Active (score >= {cutoff}): {breakdown['active']}")
    print(f"  Historic (score < {cutoff}): {breakdown['historic']}")
    print()
    print("Not in NPPES (139): breakdown by PML:")
    print(f"  In PML:                  {len(in_pml_but_not_nppes)}")
    print(f"  In PML (active):         {len(in_pml_active_but_not_nppes)}")
    print(f"  Not in PML either:       {len(not_in_nppes_npis) - len(in_pml_but_not_nppes)}")
    if in_pml_but_not_nppes:
        print("  Sample (in PML but not NPPES):")
        for npi in in_pml_but_not_nppes[:8]:
            r = npi_to_row.get(npi, {})
            name = (r.get("name") or "")[:50]
            active = "active" if pml_status.get(npi, {}).get("active") else "inactive"
            print(f"    {npi} {name!r} (PML: {active})")
    print()
    print("Penalties applied (count of NPIs that received each):")
    print(f"  No name (NPPES/PML):     {breakdown['penalty_name_not_found']}")
    print(f"  Not in NPPES:            {breakdown['penalty_not_in_nppes']}")
    print(f"  NPPES deactivated:       {breakdown['penalty_nppes_deactivated']}")
    print(f"  PML inactive:            {breakdown['penalty_pml_inactive']}")
    print(f"  Org name mismatch:       {breakdown['penalty_org_name_mismatch']}")
    print()
    print("Final score distribution (sample):")
    for s in sorted(score_dist.keys(), reverse=True)[:15]:
        print(f"  Score {s}: {score_dist[s]} NPIs")
    if len(score_dist) > 15:
        print(f"  ... ({len(score_dist)} distinct scores)")
    print()
    print("Sample failed NPIs (first 10):")
    for npi, final, reasons in failed_reasons[:10]:
        name = (npi_to_row.get(npi) or {}).get("name", "")[:40]
        ns = nppes_status.get(npi, {})
        org = (ns.get("org_name") or "")[:50]
        print(f"  {npi} score={final} {reasons}")
        print(f"      name={name!r} nppes_org={org!r}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
