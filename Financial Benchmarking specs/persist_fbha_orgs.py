#!/usr/bin/env python3
"""
Persist FBHA Step 1 results into org_profile table.
Creates org_profile rows with confirmed_npis for each org.
Enables financial_benchmarks skill for all persisted orgs.

Usage:
    python3 persist_fbha_orgs.py [--dry-run]
"""
import json, sys, re
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras

DB_URL = "postgresql://postgres:MobiusDev123%24@127.0.0.1:5433/mobius_chat"
SPECS = Path("/Users/ananth/Mobius/Financial Benchmarking specs")


def slug(name: str) -> str:
    """Normalize org name to slug."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# Map FBHA names to existing org_profile slugs to avoid duplicates
SLUG_OVERRIDES = {
    "David Lawrence Centers": "david-lawrence-center",
    "Centerstone Florida": "centerstone-of-florida",
    "Henderson Behavioral Health": "henderson-behavioral-health",
}


def main():
    dry_run = "--dry-run" in sys.argv

    results = json.loads((SPECS / "fbha_step1_results.json").read_text())
    orgs_with_npis = [r for r in results if r["npi_count"] > 0]

    print(f"Orgs to persist: {len(orgs_with_npis)}")
    if dry_run:
        print("DRY RUN — no DB writes")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Check existing orgs
    cur.execute("SELECT org_slug, org_name FROM org_profile")
    existing = {r[0]: r[1] for r in cur.fetchall()}
    print(f"Existing org_profile rows: {len(existing)}")

    now = datetime.now(timezone.utc).isoformat()
    created = 0
    updated = 0
    skipped = 0

    for r in orgs_with_npis:
        name = r["fbha_name"]
        city = r["fbha_city"]
        org_slug = SLUG_OVERRIDES.get(name, slug(name))

        # Build confirmed_npis array
        confirmed_npis = []
        for npi_rec in r["npis"]:
            confirmed_npis.append({
                "npi": str(npi_rec.get("npi", "")),
                "name": npi_rec.get("name", ""),
                "entity_type": "2",
                "source": npi_rec.get("source", "nppes"),
                "taxonomy_code": npi_rec.get("taxonomy_code", ""),
                "confirmed_at": now,
                "run_id": "fbha_batch_2026-04-06",
            })

        # Active skills — enable financial_benchmarks
        active_skills = {
            "financial_benchmarks": {"enabled": True}
        }

        # Aliases from NPPES names
        nppes_names = list(set(
            npi_rec.get("name", "") for npi_rec in r["npis"]
            if npi_rec.get("name", "")
        ))
        aliases = [name] + [n for n in nppes_names if n.lower() != name.lower()]

        if org_slug in existing:
            if dry_run:
                print(f"  UPDATE {org_slug:50s} ({len(confirmed_npis)} NPIs)")
            else:
                # Merge NPIs — don't overwrite if existing has more
                cur.execute(
                    "SELECT confirmed_npis FROM org_profile WHERE org_slug = %s",
                    (org_slug,)
                )
                row = cur.fetchone()
                existing_npis = row[0] if row and row[0] else []
                if isinstance(existing_npis, str):
                    existing_npis = json.loads(existing_npis)

                # Merge: keep existing, add new by NPI
                existing_npi_set = {n.get("npi") for n in existing_npis if isinstance(n, dict)}
                for npi_rec in confirmed_npis:
                    if npi_rec["npi"] not in existing_npi_set:
                        existing_npis.append(npi_rec)

                cur.execute("""
                    UPDATE org_profile
                    SET confirmed_npis = %s,
                        org_name_aliases = %s,
                        active_skills = org_profile.active_skills || %s,
                        updated_at = NOW()
                    WHERE org_slug = %s
                """, (
                    json.dumps(existing_npis),
                    json.dumps(aliases),
                    json.dumps(active_skills),
                    org_slug,
                ))
                print(f"  UPDATE {org_slug:50s} ({len(existing_npis)} NPIs total)")
            updated += 1
        else:
            if dry_run:
                print(f"  INSERT {org_slug:50s} ({len(confirmed_npis)} NPIs)")
            else:
                cur.execute("""
                    INSERT INTO org_profile
                        (org_slug, org_name, org_name_aliases, confirmed_npis,
                         active_skills, confirmed_at, confirmed_by, run_id_origin)
                    VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s)
                    ON CONFLICT (org_slug) DO UPDATE SET
                        confirmed_npis = EXCLUDED.confirmed_npis,
                        org_name_aliases = EXCLUDED.org_name_aliases,
                        active_skills = org_profile.active_skills || EXCLUDED.active_skills,
                        updated_at = NOW()
                """, (
                    org_slug,
                    name,
                    json.dumps(aliases),
                    json.dumps(confirmed_npis),
                    json.dumps(active_skills),
                    "fbha_batch_script",
                    "fbha_batch_2026-04-06",
                ))
                print(f"  INSERT {org_slug:50s} ({len(confirmed_npis)} NPIs)")
            created += 1

    if not dry_run:
        conn.commit()

    cur.execute("SELECT count(*) FROM org_profile")
    total = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Created: {created}, Updated: {updated}, Skipped: {skipped}")
    print(f"Total org_profile rows: {total}")
    if dry_run:
        print("(DRY RUN — nothing written)")


if __name__ == "__main__":
    main()
