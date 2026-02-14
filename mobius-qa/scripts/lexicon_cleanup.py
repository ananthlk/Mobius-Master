#!/usr/bin/env python3
"""
One-time lexicon cleanup script.

Fixes typos, broken parent_code, near-duplicates, inactive rows, and normalises
spec format so both the QA UI (strong_phrases) and RAG tagger (phrases) work.

Run:
    QA_DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/mobius_qa' \
    python3 mobius-qa/scripts/lexicon_cleanup.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys

import psycopg2
import psycopg2.extras

DRY_RUN = "--dry-run" in sys.argv


def _url() -> str:
    u = os.environ.get("QA_DATABASE_URL", "")
    if not u:
        sys.exit("QA_DATABASE_URL is required")
    return u


def _log(msg: str):
    print(f"  {'[DRY-RUN] ' if DRY_RUN else ''}{msg}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_entry(cur, kind: str, code: str) -> dict | None:
    cur.execute(
        "SELECT id, kind, code, parent_code, spec, active FROM policy_lexicon_entries WHERE kind=%s AND code=%s LIMIT 1",
        (kind, code),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _update_spec(cur, entry_id, spec: dict):
    cur.execute(
        "UPDATE policy_lexicon_entries SET spec=%s::jsonb, updated_at=NOW() WHERE id=%s",
        (json.dumps(spec), entry_id),
    )


def _set_parent(cur, kind: str, code: str, parent_code: str):
    cur.execute(
        "UPDATE policy_lexicon_entries SET parent_code=%s, updated_at=NOW() WHERE kind=%s AND code=%s",
        (parent_code, kind, code),
    )
    _log(f"SET parent_code={parent_code} on {kind}.{code}")


def _rename(cur, kind: str, old_code: str, new_code: str, new_parent: str | None = None):
    """Rename a tag code. Also update children whose parent_code was old_code."""
    updates = "code=%s, updated_at=NOW()"
    params: list = [new_code]
    if new_parent is not None:
        updates += ", parent_code=%s"
        params.append(new_parent)
    params.extend([kind, old_code])
    cur.execute(f"UPDATE policy_lexicon_entries SET {updates} WHERE kind=%s AND code=%s", params)
    # Reparent children
    cur.execute(
        "UPDATE policy_lexicon_entries SET parent_code=%s, updated_at=NOW() WHERE kind=%s AND parent_code=%s",
        (new_code, kind, old_code),
    )
    _log(f"RENAME {kind}.{old_code} -> {kind}.{new_code}")


def _merge_into(cur, kind: str, source_code: str, target_code: str):
    """Merge source tag INTO target: copy phrases, then delete source."""
    src = _get_entry(cur, kind, source_code)
    tgt = _get_entry(cur, kind, target_code)
    if not src or not tgt:
        _log(f"SKIP merge {kind}.{source_code} -> {kind}.{target_code} (missing)")
        return
    src_spec = src["spec"] if isinstance(src["spec"], dict) else {}
    tgt_spec = tgt["spec"] if isinstance(tgt["spec"], dict) else {}

    # Merge strong_phrases / phrases
    for key in ("strong_phrases", "phrases"):
        src_list = src_spec.get(key) or []
        tgt_list = tgt_spec.get(key) or []
        existing = {str(p).strip().lower() for p in tgt_list}
        for p in src_list:
            if str(p).strip().lower() not in existing:
                tgt_list.append(p)
        if tgt_list:
            tgt_spec[key] = tgt_list

    _update_spec(cur, tgt["id"], tgt_spec)
    # Reparent source's children to target
    cur.execute(
        "UPDATE policy_lexicon_entries SET parent_code=%s, updated_at=NOW() WHERE kind=%s AND parent_code=%s",
        (target_code, kind, source_code),
    )
    # Delete source
    cur.execute("DELETE FROM policy_lexicon_entries WHERE id=%s", (src["id"],))
    _log(f"MERGE {kind}.{source_code} -> {kind}.{target_code} (deleted source)")


def _deactivate(cur, kind: str, code: str):
    cur.execute(
        "DELETE FROM policy_lexicon_entries WHERE kind=%s AND code=%s",
        (kind, code),
    )
    _log(f"DELETE {kind}.{code}")


def _normalise_spec(cur, entry_id, spec: dict) -> dict:
    """Ensure spec has both 'phrases' and 'strong_phrases' in sync."""
    strong = spec.get("strong_phrases") or []
    legacy = spec.get("phrases") or []
    # Union both lists (normalised dedupe)
    seen = set()
    merged = []
    for p in (strong + legacy):
        if isinstance(p, str) and p.strip():
            norm = p.strip().lower()
            if norm not in seen:
                seen.add(norm)
                merged.append(p.strip())
    if merged:
        spec["phrases"] = merged
        spec["strong_phrases"] = merged
    return spec


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    conn = psycopg2.connect(_url())
    conn.autocommit = not DRY_RUN  # In dry-run, don't commit
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    print("=== Phase 1: Fix typos ===")

    # quality_porgram -> quality_program
    if _get_entry(cur, "d", "quality_porgram"):
        if _get_entry(cur, "d", "quality_program"):
            _merge_into(cur, "d", "quality_porgram", "quality_program")
        else:
            _rename(cur, "d", "quality_porgram", "quality_program")
    # Fix children: quality_porgram.* -> quality_program.*
    cur.execute(
        "SELECT code FROM policy_lexicon_entries WHERE kind='d' AND code LIKE 'quality_porgram.%'"
    )
    for row in cur.fetchall():
        old = row["code"]
        new = old.replace("quality_porgram.", "quality_program.")
        _rename(cur, "d", old, new, new_parent="quality_program")

    # biling_codes -> billing_codes
    if _get_entry(cur, "d", "biling_codes"):
        if _get_entry(cur, "d", "billing_codes"):
            _merge_into(cur, "d", "biling_codes", "billing_codes")
        else:
            _rename(cur, "d", "biling_codes", "billing_codes")
    # Fix children
    cur.execute(
        "SELECT code FROM policy_lexicon_entries WHERE kind='d' AND code LIKE 'biling_codes.%'"
    )
    for row in cur.fetchall():
        old = row["code"]
        new = old.replace("biling_codes.", "billing_codes.")
        _rename(cur, "d", old, new, new_parent="billing_codes")

    print("\n=== Phase 2: Delete redundant / inactive rows ===")

    # provider_manual.provider_manual -> redundant
    _deactivate(cur, "d", "provider_manual.provider_manual")

    # submit_claims (INACTIVE) -> merge into claims.submission
    if _get_entry(cur, "d", "submit_claims"):
        if _get_entry(cur, "d", "claims.submission"):
            _merge_into(cur, "d", "submit_claims", "claims.submission")
        else:
            _deactivate(cur, "d", "submit_claims")

    # prior_authorization (root INACTIVE) -> already covered by pharmacy.* and utilization_management.*
    e = _get_entry(cur, "d", "prior_authorization")
    if e and not e.get("active", True):
        _deactivate(cur, "d", "prior_authorization")

    # availity_essentials_portal (INACTIVE)
    e = _get_entry(cur, "d", "availity_essentials_portal")
    if e and not e.get("active", True):
        _deactivate(cur, "d", "availity_essentials_portal")

    # provider.contact_information (P-kind INACTIVE)
    e = _get_entry(cur, "p", "provider.contact_information")
    if e and not e.get("active", True):
        _deactivate(cur, "p", "provider.contact_information")

    print("\n=== Phase 3: Fix orphaned parent_code ===")

    # Auto-fix: any code with dot-notation but no parent_code gets parent from prefix
    cur.execute(
        "SELECT kind, code FROM policy_lexicon_entries WHERE code LIKE '%%.%%' AND (parent_code IS NULL OR parent_code = '')"
    )
    orphans = cur.fetchall()
    for row in orphans:
        code = row["code"]
        kind = row["kind"]
        # Derive parent from code: "claims.submission" -> "claims"
        parts = code.rsplit(".", 1)
        if len(parts) == 2:
            parent = parts[0]
            # Only set if the parent exists
            if _get_entry(cur, kind, parent):
                _set_parent(cur, kind, code, parent)
            else:
                _log(f"SKIP orphan {kind}.{code}: parent {parent} does not exist")

    # Create J-tag parent categories that don't exist yet
    j_parents_needed = set()
    cur.execute(
        "SELECT code FROM policy_lexicon_entries WHERE kind='j' AND code LIKE '%%.%%' AND (parent_code IS NULL OR parent_code = '')"
    )
    for row in cur.fetchall():
        parent = row["code"].rsplit(".", 1)[0]
        if not _get_entry(cur, "j", parent):
            j_parents_needed.add(parent)
    for jp in sorted(j_parents_needed):
        cur.execute(
            """INSERT INTO policy_lexicon_entries(id, kind, code, parent_code, spec, active, created_at, updated_at)
               VALUES (gen_random_uuid(), 'j', %s, NULL, %s::jsonb, true, NOW(), NOW())""",
            (jp, json.dumps({"description": jp.replace("_", " ").title(), "category": jp, "phrases": [], "strong_phrases": []})),
        )
        _log(f"CREATE j.{jp} (parent category)")

    # Now re-run orphan fix for J-tags
    cur.execute(
        "SELECT kind, code FROM policy_lexicon_entries WHERE kind='j' AND code LIKE '%%.%%' AND (parent_code IS NULL OR parent_code = '')"
    )
    for row in cur.fetchall():
        code = row["code"]
        parent = code.rsplit(".", 1)[0]
        if _get_entry(cur, "j", parent):
            _set_parent(cur, "j", code, parent)

    print("\n=== Phase 4: Merge near-duplicates ===")

    # substance_use_disorder_treatment -> substance_use_disorders
    if _get_entry(cur, "d", "health_care_services.substance_use_disorder_treatment"):
        if _get_entry(cur, "d", "health_care_services.substance_use_disorders"):
            _merge_into(cur, "d", "health_care_services.substance_use_disorder_treatment", "health_care_services.substance_use_disorders")
        else:
            _rename(cur, "d", "health_care_services.substance_use_disorder_treatment", "health_care_services.substance_use_disorders", "health_care_services")

    # provider_responsibilities -> merge into responsibilities
    if _get_entry(cur, "d", "provider_responsibilities") and _get_entry(cur, "d", "responsibilities"):
        _merge_into(cur, "d", "provider_responsibilities", "responsibilities")

    # Molina-specific contacts -> merge into generic provider_contact
    for molina_code in ("contact_information.molina_provider_contact", "contact_information.molina_provider_contact_center"):
        if _get_entry(cur, "d", molina_code):
            target = "contact_information.provider_contact"
            if _get_entry(cur, "d", target):
                _merge_into(cur, "d", molina_code, target)
            else:
                _log(f"SKIP merge {molina_code}: target {target} does not exist")

    # provider_contact_center -> merge into provider_contact
    if _get_entry(cur, "d", "contact_information.provider_contact_center") and _get_entry(cur, "d", "contact_information.provider_contact"):
        _merge_into(cur, "d", "contact_information.provider_contact_center", "contact_information.provider_contact")

    # contact_information.contact_center -> merge into contact_information.provider_contact
    if _get_entry(cur, "d", "contact_information.contact_center") and _get_entry(cur, "d", "contact_information.provider_contact"):
        _merge_into(cur, "d", "contact_information.contact_center", "contact_information.provider_contact")

    # digital_correspondence + digital_correspondence_hub -> merge into correspondence_hub
    for dup in ("tools.portal.digital_correspondence", "tools.portal.digital_correspondence_hub"):
        if _get_entry(cur, "d", dup):
            target = "tools.portal.correspondence_hub"
            if _get_entry(cur, "d", target):
                _merge_into(cur, "d", dup, target)

    # tools.portal.essentials_portal -> merge into tools.portal.availity_essentials
    if _get_entry(cur, "d", "tools.portal.essentials_portal") and _get_entry(cur, "d", "tools.portal.availity_essentials"):
        _merge_into(cur, "d", "tools.portal.essentials_portal", "tools.portal.availity_essentials")

    # medicaid_managed_care -> alias of managed_care
    if _get_entry(cur, "d", "medicaid_managed_care") and _get_entry(cur, "d", "managed_care"):
        _merge_into(cur, "d", "medicaid_managed_care", "managed_care")

    print("\n=== Phase 5: Consolidate provider domain ===")

    # Create 'provider' root if not exists
    if not _get_entry(cur, "d", "provider"):
        cur.execute(
            """INSERT INTO policy_lexicon_entries(id, kind, code, parent_code, spec, active, created_at, updated_at)
               VALUES (gen_random_uuid(), 'd', 'provider', NULL, %s::jsonb, true, NOW(), NOW())""",
            (json.dumps({"description": "Provider-related domains", "category": "provider", "phrases": ["provider"], "strong_phrases": ["provider"]}),),
        )
        _log("CREATE d.provider (root)")

    # Reparent provider_* roots under 'provider'
    for old_root in ("provider_manual", "provider_network", "provider_relations", "provider_services"):
        e = _get_entry(cur, "d", old_root)
        if e and not e.get("parent_code"):
            _set_parent(cur, "d", old_root, "provider")

    print("\n=== Phase 6: Normalise spec format (phrases <-> strong_phrases) ===")

    cur.execute("SELECT id, spec FROM policy_lexicon_entries")
    all_rows = cur.fetchall()
    normalised = 0
    for row in all_rows:
        spec = row["spec"] if isinstance(row["spec"], dict) else {}
        original = json.dumps(spec, sort_keys=True)
        updated = _normalise_spec(cur, row["id"], dict(spec))
        if json.dumps(updated, sort_keys=True) != original:
            _update_spec(cur, row["id"], updated)
            normalised += 1
    _log(f"Normalised spec on {normalised} entries")

    print("\n=== Phase 7: Bump lexicon revision ===")
    cur.execute(
        "UPDATE policy_lexicon_meta SET revision = COALESCE(revision, 0) + 1, updated_at = NOW()"
    )
    cur.execute("SELECT revision FROM policy_lexicon_meta ORDER BY updated_at DESC LIMIT 1")
    rev_row = cur.fetchone()
    _log(f"Lexicon revision now: {rev_row['revision'] if rev_row else '?'}")

    # Summary
    cur.execute("SELECT kind, count(*) FROM policy_lexicon_entries WHERE active=true GROUP BY kind ORDER BY kind")
    print("\n=== Final tag counts ===")
    for row in cur.fetchall():
        print(f"  {row['kind'].upper()}: {row['count']}")

    cur.execute("SELECT count(*) AS n FROM policy_lexicon_entries")
    print(f"  Total: {cur.fetchone()['n']}")

    if DRY_RUN:
        conn.rollback()
        print("\n[DRY-RUN] No changes committed. Remove --dry-run to apply.")
    else:
        conn.commit()
        print("\nDone! Changes committed.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
