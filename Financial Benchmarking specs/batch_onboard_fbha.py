#!/usr/bin/env python3
"""
Batch run Step 1 (org search / NPI identification) for all 66 FBHA member orgs.
Uses run_org_name_search with alternate names and agentic mode.

Usage:
    python3 batch_onboard_fbha.py [--force-all]
"""
import json, os, sys, time
from pathlib import Path

SKILL_ROOT = Path("/Users/ananth/Mobius/mobius-skills/provider-roster-credentialing")
sys.path.insert(0, str(SKILL_ROOT))

env_path = Path("/Users/ananth/Mobius/mobius-config/.env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from google.cloud import bigquery
from app.org_search import run_org_name_search

SPECS = Path("/Users/ananth/Mobius/Financial Benchmarking specs")

# Known alternate names — legal names in NPPES often differ from trade names
ALTERNATE_NAMES = {
    "David Lawrence Centers": ["David Lawrence Mental Health Center", "David Lawrence Center"],
    "Directions for Living": ["Directions for Mental Health", "Directions for Living Inc"],
    "EPIC Behavioral Healthcare": ["EPIC Community Services", "EPIC Behavioral Health"],
    "Tri-County Human Services": ["Tri County Human Services", "Tri-County Human Services Inc"],
    "CDAC Behavioral Healthcare": ["CDAC Inc", "Community Drug and Alcohol Council", "Lakeview Center CDAC"],
    "Central Florida Treatment Center": ["Central Florida Treatment Centers", "Metro Treatment of Florida"],
    "Broward Addiction Recovery Center": ["Broward Addiction Recovery", "BARC"],
    "Starting Point Behavioral Healthcare": ["Starting Point Behavioral Health", "Starting Point Inc"],
    "Park Place Behavioral Health Care": ["Park Place Behavioral Healthcare", "Park Place BHC"],
    "Eleos Wellness & Support": ["Eleos Wellness", "Personal Enrichment Through Mental Health Services", "PEMHS"],
    "Fellowship House": ["Fellowship House Inc", "Fellowship House of South Florida"],
    "Lightshare Behavioral Wellness & Recovery": ["Lightshare Behavioral", "Coastal Behavioral Healthcare"],
    "Tampa General Behavioral Health Hospital": ["Tampa General Hospital", "TGH Behavioral"],
    "The Henry and Rilla White Foundation": ["Henry and Rilla White", "White Foundation", "Disc Village White Foundation"],
    "Alpert Jewish Services of Palm Beach": ["Alpert Jewish Family", "Ruth and Norman Rales Jewish Family Services"],
    "Centerstone Florida": ["Centerstone of Florida"],
    "Henderson Behavioral Health": ["Henderson Behavioral Health Inc", "Henderson Mental Health Center"],
    "SalusCare": ["SalusCare Inc", "Lee Mental Health Center"],
    "Boley Centers": ["Boley Centers Inc", "Boley Centers for Behavioral Health"],
    "ACTS": ["Agency for Community Treatment Services", "ACTS Inc"],
    "IMPOWER": ["IMPOWER Inc", "Children's Home Society Central Florida"],
    "STEPS": ["STEPS Inc", "STEPS to Recovery"],
}


def main():
    force_all = "--force-all" in sys.argv

    fbha = json.loads((SPECS / "fbha_member_orgs.json").read_text())
    members = fbha["members"]
    bq = bigquery.Client(project=os.environ.get("BQ_PROJECT", "mobius-os-dev"))

    results = []
    for i, m in enumerate(members, 1):
        name = m["name"]
        city = m["city"]
        print(f"[{i:2d}/{len(members)}] {name:50s} ({city})", end="  ", flush=True)

        try:
            alt_names = ALTERNATE_NAMES.get(name, [])
            progress = []
            out = run_org_name_search(
                bq,
                primary_name=name,
                alternate_names=alt_names,
                state_filter="FL",
                limit=20,
                include_pml=True,
                include_practice_address=True,
                include_edit_envelope=False,
                include_web_enrichment=True,
                search_mode="agentic",
                progress=progress,
            )
            hits = out.get("results", [])
            npis = []
            for h in hits:
                npis.append({
                    "npi": h.get("npi"),
                    "name": h.get("name", ""),
                    "source": h.get("source", ""),
                    "city": h.get("city", ""),
                    "match_score": h.get("match_score"),
                    "taxonomy_code": h.get("taxonomy_code", ""),
                })
            confidence = out.get("registry_confidence", {})
            conf_reason = confidence.get("reason", "")
            best_score = confidence.get("best_score", "")
            print(f"{len(npis):3d} NPIs  conf={conf_reason}  score={best_score}")
            results.append({
                "fbha_name": name,
                "fbha_city": city,
                "status": "ok",
                "npi_count": len(npis),
                "registry_confidence": confidence,
                "npis": npis,
            })
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "fbha_name": name,
                "fbha_city": city,
                "status": "error",
                "error": str(e),
                "npi_count": 0,
                "npis": [],
            })

        time.sleep(0.5)

    # Summary
    ok = sum(1 for r in results if r["status"] == "ok")
    with_npis = sum(1 for r in results if r["npi_count"] > 0)
    total_npis = sum(r["npi_count"] for r in results)
    zero = [r["fbha_name"] for r in results if r["npi_count"] == 0]
    print(f"\n{'='*60}")
    print(f"Done: {ok}/{len(members)} succeeded, {with_npis} found NPIs, {total_npis} total NPIs")
    if zero:
        print(f"Zero NPIs ({len(zero)}): {', '.join(zero)}")

    out_file = SPECS / "fbha_step1_results.json"
    out_file.write_text(json.dumps(results, indent=2))
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()
