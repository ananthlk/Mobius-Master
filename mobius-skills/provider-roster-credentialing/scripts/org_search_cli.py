#!/usr/bin/env python3
"""
CLI for Step 1 org search (name or address). Usage:

  # Name search
  uv run python scripts/org_search_cli.py "David Lawrence"
  uv run python scripts/org_search_cli.py "Aspire" --state FL
  uv run python scripts/org_search_cli.py "Henderson" --limit 10

  # Address search (free-form or components)
  uv run python scripts/org_search_cli.py --address "434 W Kennedy Blvd, Tampa, FL 33609"
  uv run python scripts/org_search_cli.py --address "6350 Davis Blvd, Naples, FL 34104"
  uv run python scripts/org_search_cli.py --street "6350 Davis Blvd" --city Naples --state FL --zip 34104

Env: BQ_PROJECT, BQ_LANDING_MEDICAID_DATASET (optional)
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

from app.org_search import search_org_names, search_org_by_address


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step 1: Search org/provider by name or address in NPPES and PML"
    )
    parser.add_argument("name", nargs="?", default=None, help='Org/provider name (e.g. "David Lawrence")')
    parser.add_argument("--address", help="Address search: free-form string (e.g. '123 Main St, Miami, FL 33101')")
    parser.add_argument("--street", help="Address search: street (use with --city, --state, --zip)")
    parser.add_argument("--city", help="Address search: city")
    parser.add_argument("--state", default="FL", help="State filter (default: FL)")
    parser.add_argument("--zip", help="Address search: ZIP or ZIP+4")
    parser.add_argument("--limit", type=int, default=20, help="Max matches per source (default: 20)")
    parser.add_argument("--entity-type", default="2", help="NPPES entity type: 2=orgs (default), 1=individuals, 'all'=both")
    parser.add_argument("--no-pml", action="store_true", help="Skip PML search (NPPES only)")
    parser.add_argument("--no-google", action="store_true", help="Skip Google address validation (local only, faster)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
    landing = os.environ.get("BQ_LANDING_MEDICAID_DATASET")
    client = bigquery.Client(project=project)
    et_filter = None if getattr(args, "entity_type", "2") == "all" else getattr(args, "entity_type", "2")

    # Address search
    if args.address or (args.street or args.city or args.zip):
        norm, results = search_org_by_address(
            client,
            address_raw=args.address,
            address_line_1=args.street,
            city=args.city,
            state=args.state,
            postal_code=args.zip,
            limit=args.limit,
            include_pml=not args.no_pml,
            use_google=not args.no_google,
            entity_type_filter=et_filter,
            project=project,
            landing_dataset=landing,
        )
        if norm is None:
            print("Could not normalize address (need at least ZIP5).", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps({"normalized_address": norm, "results": results}, indent=2))
        else:
            print(f"Normalized: {norm.get('address_line_1', '')}, {norm.get('city', '')} {norm.get('state', '')} {norm.get('zip5', '')}")
            print()
            if not results:
                print("No matches found.")
            else:
                print(f"Found {len(results)} match(es):\n")
                for i, r in enumerate(results, 1):
                    addr = f"{r.get('address_line_1','')}, {r.get('city','')} {r.get('state','')} {r.get('zip5','')}".strip(", ")
                    print(f"  {i}. {r['name']}")
                    print(f"     NPI: {r['npi']}  |  Source: {r['source']}  |  Type: {r['entity_type']}")
                    print(f"     Address: {addr}")
                    print()
        return 0

    # Name search
    if not args.name:
        parser.error("Provide name or use --address / --street --city --zip for address search")
    results = search_org_names(
        client,
        args.name,
        state_filter=args.state,
        limit=args.limit,
        entity_type_filter=et_filter,
        include_pml=not args.no_pml,
        project=project,
        landing_dataset=landing,
    )

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if not results:
            print("No matches found.")
        else:
            print(f"Found {len(results)} match(es):\n")
            for i, r in enumerate(results, 1):
                print(f"  {i}. {r['name']}")
                print(f"     NPI: {r['npi']}  |  Source: {r['source']}  |  Type: {r['entity_type']}")
                print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
