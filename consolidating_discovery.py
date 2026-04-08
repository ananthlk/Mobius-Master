#!/usr/bin/env python3
"""
Consolidating Org Discovery Wrapper

Takes a prioritized list of FL BH orgs and runs them through the full
agentic pipeline (Step 1 + Step 2), consolidating duplicates as they're
discovered. When org A's discovery reveals org B is the same entity
(same name or same NPIs), org B is marked as consolidated and skipped.

Usage:
    python consolidating_discovery.py [--limit N] [--dry-run] [--resume]

Input:  /tmp/fl_bh_agentic_priority.json
Output: /tmp/fl_bh_discovery_results.json (incremental, append-safe)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import hashlib

import requests

SKILL_SERVER = os.environ.get("SKILL_SERVER_URL", "http://localhost:8011")
INPUT_FILE = "/tmp/fl_bh_agentic_priority.json"
OUTPUT_FILE = "/tmp/fl_bh_discovery_results.json"
STATE_FILE = "/tmp/fl_bh_discovery_state.json"


# ── Fuzzy name matching ─────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    name = name.lower().strip()
    name = re.sub(r"[,.\-'\"()]+", " ", name)
    # Remove common suffixes
    for suffix in [" inc", " llc", " corp", " corporation", " ltd", " lp",
                   " pllc", " pa", " pl", " of florida", " fl"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    name = re.sub(r"\s+", " ", name).strip()
    return name


def names_match(a: str, b: str) -> bool:
    """Check if two org names likely refer to the same entity."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return False
    # Exact after normalization
    if na == nb:
        return True
    # One contains the other (and the shorter is at least 8 chars)
    if len(na) >= 8 and len(nb) >= 8:
        if na in nb or nb in na:
            return True
    return False


# ── API calls (with retry) ──────────────────────────────────────────────────

MAX_RETRIES = 3
RETRY_BACKOFF = [5, 15, 30]  # seconds


def _post_with_retry(url: str, payload: dict, timeout: int = 120) -> dict:
    """POST with exponential backoff on 5xx errors."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if resp.status_code >= 500 and attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"    ⟳ Retry {attempt+1}/{MAX_RETRIES} after {resp.status_code}, "
                      f"waiting {wait}s...")
                time.sleep(wait)
                continue
            raise
        except requests.exceptions.ConnectionError as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"    ⟳ Connection error, retry {attempt+1}/{MAX_RETRIES}, "
                      f"waiting {wait}s...")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("Max retries exceeded")


def search_org(name: str, state: str = "FL") -> dict:
    """Step 1: POST /search/org-names with agentic mode."""
    return _post_with_retry(
        f"{SKILL_SERVER}/search/org-names",
        {
            "name": name,
            "state": state,
            "limit": 30,
            "search_mode": "agentic",
            "include_web_enrichment": True,
            "include_edit_envelope": False,
        },
    )


def find_locations(org_npis: list[str], org_name: str, state: str = "FL") -> dict:
    """Step 2: POST /find-locations with agentic mode."""
    return _post_with_retry(
        f"{SKILL_SERVER}/find-locations",
        {
            "org_npis": org_npis,
            "state": state,
            "search_mode": "agentic",
            "org_name": org_name,
            "include_web_enrichment": True,
        },
    )


# ── Persistence to org_profile ───────────────────────────────────────────────

def _location_id(addr: str, city: str, state: str, zip5: str) -> str:
    """Deterministic location_id — matches location_identification.py."""
    raw = "|".join(str(x) if x else "" for x in (addr, city, state, zip5))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def persist_to_org_profile(
    org_name: str,
    step1_data: dict,
    step2_data: dict,
    discovered_names: set[str],
    discovered_npis: set[str],
    consolidated_orgs: list[str],
    org_meta: dict,
    run_id: str,
) -> dict | None:
    """Persist discovery results to org_profile + org_locations via skill server API.

    Returns the API response or None on failure.
    """
    # Build confirmed_npis list with metadata from step1 results
    npi_records = []
    seen_npis = set()
    for r in step1_data.get("results", []):
        npi = r.get("npi", "")
        if npi and npi not in seen_npis:
            seen_npis.add(npi)
            npi_records.append({
                "npi": npi,
                "name": r.get("name", ""),
                "entity_type": str(r.get("entity_type_code", r.get("entity_type", ""))),
                "source": r.get("source", "nppes"),
                "taxonomy_code": r.get("healthcare_provider_taxonomy_code_1", r.get("taxonomy_code", "")),
            })
    # Add any NPIs found only in step2 (locations)
    for loc in step2_data.get("locations", []):
        npi = loc.get("npi", "")
        if npi and npi not in seen_npis:
            seen_npis.add(npi)
            npi_records.append({
                "npi": npi,
                "name": loc.get("name", ""),
                "entity_type": "",
                "source": loc.get("site_source", "step2"),
                "taxonomy_code": "",
            })

    # Build aliases: all discovered name variants + consolidated org names
    aliases = sorted(discovered_names - {org_name})
    for cn in consolidated_orgs:
        if cn not in aliases:
            aliases.append(cn)

    # Build org_identifiers metadata
    org_identifiers = {
        "types": org_meta.get("types", []),
        "doge_paid_2024": org_meta.get("doge_paid_2024", 0),
        "consolidated_orgs": consolidated_orgs,
        "discovery_run_id": run_id,
        "discovery_timestamp": datetime.now().isoformat(),
        "npi_count": org_meta.get("npi_count", len(npi_records)),
    }

    # ── Step A: Upsert org identity (NPIs + aliases + metadata) ──
    try:
        resp = requests.post(
            f"{SKILL_SERVER}/org/upsert",
            json={
                "org_name": org_name,
                "confirmed_npis": npi_records,
                "run_id": run_id,
                "confirmed_by": "agentic_discovery",
                "force_refresh": True,
                "aliases": aliases,
                "org_identifiers": org_identifiers,
            },
            timeout=30,
        )
        resp.raise_for_status()
        upsert_result = resp.json()
        org_slug = upsert_result.get("org_slug", "")
        print(f"  ✓ Persisted org profile: {org_slug} — {len(npi_records)} NPIs, {len(aliases)} aliases")
    except Exception as e:
        print(f"  ✗ Failed to persist org profile: {e}")
        return None

    # ── Step B: Upsert locations ──
    if org_slug and step2_data.get("locations"):
        location_records = []
        for loc in step2_data["locations"]:
            addr = loc.get("site_address_line_1", loc.get("address", ""))
            city = loc.get("site_city", loc.get("city", ""))
            state = loc.get("site_state", "FL")
            zip5 = loc.get("site_zip5", loc.get("zip5", ""))
            lid = _location_id(addr, city, state, zip5)
            location_records.append({
                "location_id": lid,
                "address_line1": addr,
                "city": city,
                "state_cd": state,
                "zip": zip5,
                "source": loc.get("site_source", loc.get("source", "")),
                "is_primary": False,
            })
        try:
            resp = requests.post(
                f"{SKILL_SERVER}/org/{org_slug}/locations",
                json={
                    "locations": location_records,
                    "run_id": run_id,
                    "deactivate_missing": False,
                },
                timeout=30,
            )
            resp.raise_for_status()
            loc_result = resp.json()
            print(f"  ✓ Persisted {loc_result.get('count', len(location_records))} locations for {org_slug}")
        except Exception as e:
            print(f"  ✗ Failed to persist locations: {e}")

    return upsert_result


# ── Consolidation logic ──────────────────────────────────────────────────────

def extract_llm_aliases(step1_data: dict) -> list[str]:
    """Parse LLM-extracted aliases from progress lines."""
    aliases = []
    for p in step1_data.get("progress", []):
        if "LLM extracted:" in p and "aliases=" in p:
            # Parse: "LLM extracted: aliases=['Name1', 'Name2']; ..."
            try:
                aliases_part = p.split("aliases=")[1].split(";")[0].strip()
                # Safely parse the list
                parsed = json.loads(aliases_part.replace("'", '"'))
                if isinstance(parsed, list):
                    aliases.extend(parsed)
            except Exception:
                pass
        if "LLM extracted:" in p and "affiliates=" in p:
            try:
                aff_part = p.split("affiliates=")[1].split(";")[0].strip()
                parsed = json.loads(aff_part.replace("'", '"'))
                if isinstance(parsed, list):
                    aliases.extend(parsed)
            except Exception:
                pass
        if "LLM extracted:" in p and "parent=" in p:
            try:
                parent_part = p.split("parent=")[1].split(";")[0].strip()
                if parent_part and parent_part.lower() not in ("none", "null", ""):
                    aliases.append(parent_part)
            except Exception:
                pass
    return aliases


def extract_discovered_names(step1_data: dict, step2_data: dict) -> set[str]:
    """Extract all org names found during Steps 1 and 2, including LLM aliases."""
    names = set()
    for r in step1_data.get("results", []):
        n = r.get("name", "")
        if n:
            names.add(n)
    for loc in step2_data.get("locations", []):
        n = loc.get("name", "")
        if n:
            names.add(n)
    # Add LLM-extracted aliases
    for alias in extract_llm_aliases(step1_data):
        if alias:
            names.add(alias)
    return names


def extract_discovered_npis(step1_data: dict, step2_data: dict) -> set[str]:
    """Extract all NPIs found during Steps 1 and 2."""
    npis = set()
    for r in step1_data.get("results", []):
        npi = r.get("npi", "")
        if npi:
            npis.add(npi)
    for loc in step2_data.get("locations", []):
        npi = loc.get("npi", "")
        if npi:
            npis.add(npi)
    return npis


def find_consumed_orgs(
    discovered_names: set[str],
    remaining_queue: list[dict],
) -> list[int]:
    """Find indices in remaining_queue that match any discovered name."""
    consumed = []
    for i, org in enumerate(remaining_queue):
        org_name = org.get("org_name", "")
        for dn in discovered_names:
            if names_match(org_name, dn):
                consumed.append(i)
                break
    return consumed


# ── State management ─────────────────────────────────────────────────────────

def load_state() -> dict:
    """Load saved state (for resume)."""
    if Path(STATE_FILE).exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"processed": [], "consumed_norms": [], "results": []}


def save_state(state: dict):
    """Save state for resume."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_queue() -> list[dict]:
    """Load the priority queue (tier1 + tier2 combined)."""
    with open(INPUT_FILE) as f:
        data = json.load(f)
    # Combine tier1 and tier2, already sorted by doge_paid_2024 desc
    tier1 = data.get("tier1_cmhc_fqhc_with_doge", [])
    tier2 = data.get("tier2_top_bh_with_doge", [])
    return tier1 + tier2


# ── Main loop ────────────────────────────────────────────────────────────────

def run(limit: int | None = None, dry_run: bool = False, resume: bool = False):
    queue = load_queue()
    print(f"Loaded {len(queue)} orgs from priority list")

    # Load or init state
    if resume:
        state = load_state()
        consumed_norms = set(state.get("consumed_norms", []))
        results = state.get("results", [])
        print(f"Resuming: {len(results)} already processed, {len(consumed_norms)} norms consumed")
    else:
        consumed_norms = set()
        results = []

    processed_count = 0
    skipped_count = 0

    for i, org in enumerate(queue):
        if limit and processed_count >= limit:
            print(f"\n>>> Reached limit of {limit} orgs. Stopping.")
            break

        org_name = org["org_name"]
        norm = normalize_name(org_name)

        # Skip if already consumed by a prior discovery
        if norm in consumed_norms:
            skipped_count += 1
            continue

        print(f"\n{'='*80}")
        print(f"[{processed_count + 1}] Processing: {org_name}")
        print(f"    Types: {','.join(org['types'])}  NPIs: {org['npi_count']}  DOGE: ${org['doge_paid_2024']:,.0f}")
        print(f"    Queue position: {i+1}/{len(queue)}  Skipped so far: {skipped_count}")
        print(f"{'='*80}")

        if dry_run:
            consumed_norms.add(norm)
            processed_count += 1
            continue

        # ── Step 1: Search org names ──
        try:
            t0 = time.time()
            step1 = search_org(org_name)
            t1 = time.time()
            s1_results = step1.get("results", [])
            s1_npis = [r["npi"] for r in s1_results if r.get("npi")]
            s1_names = set(r.get("name", "") for r in s1_results if r.get("name"))
            llm_aliases = extract_llm_aliases(step1)
            print(f"  Step 1: {len(s1_results)} results, {len(set(s1_npis))} unique NPIs, "
                  f"{len(s1_names)} name variants [{t1-t0:.1f}s]")
            for n in sorted(s1_names):
                print(f"    • {n}")
            if llm_aliases:
                print(f"  LLM aliases: {llm_aliases}")
        except Exception as e:
            print(f"  Step 1 FAILED: {e}")
            results.append({
                "org_name": org_name, "norm": norm, "status": "error_step1",
                "error": str(e), "timestamp": datetime.now().isoformat(),
            })
            consumed_norms.add(norm)
            processed_count += 1
            save_state({"consumed_norms": list(consumed_norms), "results": results})
            continue

        if not s1_npis:
            print("  Step 1: No NPIs found. Skipping Step 2.")
            results.append({
                "org_name": org_name, "norm": norm, "status": "no_npis",
                "timestamp": datetime.now().isoformat(),
            })
            consumed_norms.add(norm)
            processed_count += 1
            save_state({"consumed_norms": list(consumed_norms), "results": results})
            continue

        # ── Step 2: Find locations ──
        try:
            t0 = time.time()
            step2 = find_locations(list(set(s1_npis)), org_name)
            t1 = time.time()
            s2_locs = step2.get("locations", [])
            print(f"  Step 2: {len(s2_locs)} locations [{t1-t0:.1f}s]")
            for loc in s2_locs[:10]:
                addr = loc.get("site_address_line_1", "")
                city = loc.get("site_city", "")
                z = loc.get("site_zip5", "")
                src = loc.get("site_source", "")
                print(f"    • {addr[:30]:30s}  {city:15s}  {z}  ({src})")
            if len(s2_locs) > 10:
                print(f"    ... and {len(s2_locs) - 10} more")
        except Exception as e:
            print(f"  Step 2 FAILED: {e}")
            step2 = {"locations": []}

        # ── Consolidation: harvest names and consume matching orgs ──
        discovered_names = extract_discovered_names(step1, step2)
        discovered_npis = extract_discovered_npis(step1, step2)

        # Mark this org's normalized name as consumed
        consumed_norms.add(norm)

        # Find queue entries that match discovered names
        newly_consumed = []
        for j, other_org in enumerate(queue):
            if j == i:
                continue
            other_norm = normalize_name(other_org["org_name"])
            if other_norm in consumed_norms:
                continue
            # Check if any discovered name matches this queue entry
            for dn in discovered_names:
                if names_match(other_org["org_name"], dn):
                    consumed_norms.add(other_norm)
                    newly_consumed.append(other_org["org_name"])
                    break

        if newly_consumed:
            print(f"\n  >>> CONSOLIDATED {len(newly_consumed)} other orgs:")
            for nc in newly_consumed:
                print(f"      ✓ {nc}")

        # Save result
        result = {
            "org_name": org_name,
            "norm": norm,
            "status": "discovered",
            "timestamp": datetime.now().isoformat(),
            "step1_npi_count": len(set(s1_npis)),
            "step1_name_variants": sorted(discovered_names),
            "step2_location_count": len(s2_locs),
            "step2_locations": [
                {
                    "address": loc.get("site_address_line_1", ""),
                    "city": loc.get("site_city", ""),
                    "zip5": loc.get("site_zip5", ""),
                    "source": loc.get("site_source", ""),
                }
                for loc in s2_locs
            ],
            "discovered_npis": sorted(discovered_npis),
            "consolidated_orgs": newly_consumed,
            "types": org["types"],
            "doge_paid_2024": org["doge_paid_2024"],
        }
        results.append(result)
        processed_count += 1

        # ── Persist to org_profile + org_locations ──
        if not dry_run:
            run_id = f"discovery_{datetime.now().strftime('%Y%m%d')}_{processed_count}"
            persist_to_org_profile(
                org_name=org_name,
                step1_data=step1,
                step2_data=step2,
                discovered_names=discovered_names,
                discovered_npis=discovered_npis,
                consolidated_orgs=newly_consumed,
                org_meta=org,
                run_id=run_id,
            )

        # Save state after each org (resume-safe)
        save_state({"consumed_norms": list(consumed_norms), "results": results})
        print(f"\n  State saved. Processed: {processed_count}, Consumed: {len(consumed_norms)}, "
              f"Remaining: {len(queue) - len(consumed_norms)}")

    # ── Final summary ──
    print(f"\n{'='*80}")
    print(f"DISCOVERY COMPLETE")
    print(f"{'='*80}")
    print(f"  Orgs processed (Step 1+2): {processed_count}")
    print(f"  Orgs skipped (consolidated): {skipped_count}")
    print(f"  Total consumed: {len(consumed_norms)}")
    print(f"  Remaining in queue: {len(queue) - len(consumed_norms)}")

    # Save final results
    with open(OUTPUT_FILE, "w") as f:
        json.dump({
            "run_timestamp": datetime.now().isoformat(),
            "input_queue_size": len(queue),
            "processed": processed_count,
            "skipped_consolidated": skipped_count,
            "total_consumed": len(consumed_norms),
            "remaining": len(queue) - len(consumed_norms),
            "results": results,
        }, f, indent=2)
    print(f"\n  Results saved to {OUTPUT_FILE}")


def persist_existing_results():
    """Re-persist already-completed discovery results to org_profile.

    Reads /tmp/fl_bh_discovery_results.json and calls the persistence API
    for each discovered org. Use this to backfill org_profile from a prior run.
    """
    if not Path(OUTPUT_FILE).exists():
        print(f"No results file found at {OUTPUT_FILE}")
        return

    with open(OUTPUT_FILE) as f:
        data = json.load(f)

    results = data.get("results", [])
    print(f"Persisting {len(results)} existing discovery results to org_profile...")

    success = 0
    for i, r in enumerate(results):
        if r.get("status") != "discovered":
            print(f"  [{i+1}] Skipping {r['org_name']} (status={r.get('status')})")
            continue

        # Reconstruct step1/step2 data from saved result
        step1_data = {
            "results": [
                {"npi": npi, "name": r["org_name"], "source": "discovery_replay"}
                for npi in r.get("discovered_npis", [])
            ],
            "progress": [],
        }
        step2_data = {
            "locations": [
                {
                    "site_address_line_1": loc.get("address", ""),
                    "site_city": loc.get("city", ""),
                    "site_state": "FL",
                    "site_zip5": loc.get("zip5", ""),
                    "site_source": loc.get("source", ""),
                }
                for loc in r.get("step2_locations", [])
            ],
        }
        discovered_names = set(r.get("step1_name_variants", []))
        discovered_npis = set(r.get("discovered_npis", []))

        run_id = f"discovery_backfill_{datetime.now().strftime('%Y%m%d')}_{i+1}"
        result = persist_to_org_profile(
            org_name=r["org_name"],
            step1_data=step1_data,
            step2_data=step2_data,
            discovered_names=discovered_names,
            discovered_npis=discovered_npis,
            consolidated_orgs=r.get("consolidated_orgs", []),
            org_meta={
                "types": r.get("types", []),
                "doge_paid_2024": r.get("doge_paid_2024", 0),
                "npi_count": r.get("step1_npi_count", 0),
            },
            run_id=run_id,
        )
        if result:
            success += 1

    print(f"\nDone: {success}/{len(results)} orgs persisted to org_profile")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consolidating Org Discovery")
    parser.add_argument("--limit", type=int, default=None, help="Max orgs to process")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, just show queue")
    parser.add_argument("--resume", action="store_true", help="Resume from saved state")
    parser.add_argument("--persist-only", action="store_true",
                        help="Re-persist existing results to org_profile (no new discovery)")
    args = parser.parse_args()

    if args.persist_only:
        persist_existing_results()
    else:
        run(limit=args.limit, dry_run=args.dry_run, resume=args.resume)
