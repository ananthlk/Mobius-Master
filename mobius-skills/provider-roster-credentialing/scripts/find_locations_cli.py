#!/usr/bin/env python3
"""
Find all practice locations for an organization (Step 2).

Takes org NPIs (from find_org_cli) and optionally initial sites. Queries DOGE for
servicing NPIs, then NPPES/PML for addresses. Returns distinct locations.

Usage:
  # From NPIs (comma-separated or from find_org output)
  uv run python scripts/find_locations_cli.py --npis 1811334402,1609113588,1982867255

  # From org name (searches NPPES/PML, gets NPIs, then finds locations)
  uv run python scripts/find_locations_cli.py "David Lawrence Center"

  # With initial sites from find_org (JSON file)
  uv run python scripts/find_locations_cli.py --npis 1811334402,1609113588 --sites sites.json

  # Output
  --json   Output JSON

Env: BQ_PROJECT, BQ_LANDING_MEDICAID_DATASET

Note: stg_doge must have billing_npi and servicing_npi columns.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from google.cloud import bigquery
except ImportError:
    print("Install: pip install google-cloud-bigquery", file=sys.stderr)
    sys.exit(1)

from app.location_identification import find_locations_for_org
from app.org_search import search_org_names


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find all practice locations for an organization (Step 2)"
    )
    parser.add_argument(
        "org_name",
        nargs="?",
        default=None,
        help="Org name (searches NPPES/PML for NPIs, then finds locations)",
    )
    parser.add_argument("--npis", help="Comma-separated org NPIs (from find_org_cli)")
    parser.add_argument("--sites", help="JSON file: list of {address_line_1, city, state, zip5} initial sites")
    parser.add_argument("--state", default="FL", help="State filter (default: FL)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
    landing = os.environ.get("BQ_LANDING_MEDICAID_DATASET")

    try:
        bq = bigquery.Client(project=project)
    except Exception as e:
        print(f"BigQuery client failed: {e}", file=sys.stderr)
        return 1

    org_npis: list[str] = []
    initial_sites: list[dict] | None = None

    if args.npis:
        org_npis = [n.strip() for n in args.npis.split(",") if n.strip()]
    elif args.org_name:
        print(f"Searching for org '{args.org_name}'...", file=sys.stderr)
        results = search_org_names(
            bq,
            args.org_name,
            state_filter=args.state,
            limit=50,
            include_pml=bool(landing),
            project=project,
            landing_dataset=landing,
        )
        org_npis = list(dict.fromkeys(str(r.get("npi", "")) for r in results if r.get("npi")))
        print(f"Found {len(org_npis)} NPIs", file=sys.stderr)
    else:
        parser.error("Provide org name or --npis")
        return 1

    if not org_npis:
        print("No org NPIs to search. Exiting.", file=sys.stderr)
        return 1

    if args.sites:
        try:
            with open(args.sites) as f:
                data = json.load(f)
            initial_sites = data if isinstance(data, list) else data.get("sites", data.get("results", []))
        except Exception as e:
            print(f"Could not load sites file: {e}", file=sys.stderr)
            initial_sites = None

    locations = find_locations_for_org(
        bq,
        org_npis,
        initial_sites=initial_sites,
        state_filter=args.state,
        project=project,
        landing_dataset=landing,
    )

    if args.json:
        print(json.dumps({"locations": locations, "count": len(locations)}, indent=2))
    else:
        if not locations:
            print("No locations found.")
        else:
            print(f"Found {len(locations)} location(s):\n")
            for i, loc in enumerate(locations, 1):
                addr = f"{loc.get('site_address_line_1','')}, {loc.get('site_city','')}, {loc.get('site_state','')} {loc.get('site_zip5','')}".strip(", ")
                src = loc.get("site_source", "")
                print(f"  {i}. {addr}")
                print(f"     source: {src}")
                if loc.get("npi"):
                    print(f"     npi: {loc['npi']}")
                if loc.get("name"):
                    print(f"     name: {loc['name']}")
                print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
