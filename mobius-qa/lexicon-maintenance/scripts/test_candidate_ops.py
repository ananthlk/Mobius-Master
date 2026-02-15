#!/usr/bin/env python3
"""
Test candidate operations: reject and add_alias.
Run with: python -m app.scripts.test_candidate_ops
Or: cd mobius-qa/lexicon-maintenance && python scripts/test_candidate_ops.py
"""
import os
import sys

# Ensure app is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

API_BASE = os.getenv("VITE_API_BASE", "http://localhost:8010")


def main():
    print("=== Candidate Ops Test ===\n")

    # 1. Fetch proposed candidates
    r = requests.get(f"{API_BASE}/policy/lexicon/overview", params={"status": "proposed", "limit": 100, "min_score": "0"})
    r.raise_for_status()
    data = r.json()
    rows = [x for x in (data.get("rows") or []) if x.get("row_type") == "candidate"]
    print(f"1. Proposed candidates: {len(rows)}")

    if not rows:
        print("   No proposed candidates. Skipping tests (nothing to reject/add_alias).")
        return

    cand = rows[0]
    norm = cand.get("normalized") or cand.get("key") or ""
    if not norm:
        norm = str(cand.get("id", ""))
    ids = cand.get("ids") or []
    if not ids:
        print("   No ids in candidate row (API may need restart). Skipping.")
        return
    print(f"   First candidate: {norm!r} (ids={len(ids)})\n")

    # 1b. Debug: raw DB state before any op (requires restart of QA lexicon API)
    dr = requests.get(f"{API_BASE}/policy/candidates/debug", params={"normalized": norm})
    if dr.ok:
        jd = dr.json()
        print(f"   DEBUG before: {jd.get('count', 0)} rows in DB, states={[r.get('state') for r in jd.get('rows', [])]}\n")
    else:
        print(f"   DEBUG: /policy/candidates/debug not available (restart QA lexicon API for debug)\n")

    # 2. Fetch approved tags (for add_alias target)
    r2 = requests.get(f"{API_BASE}/policy/lexicon/overview", params={"status": "approved", "limit": 50})
    r2.raise_for_status()
    tag_rows = [x for x in (r2.json().get("rows") or []) if x.get("row_type") == "tag"]
    target_tag = None
    if tag_rows:
        t = tag_rows[0]
        target_tag = {"kind": (t.get("kind") or "d").strip().lower(), "code": (t.get("code") or "").strip()}
        if target_tag["kind"] in ("p", "d", "j") and target_tag["code"]:
            print(f"2. Target tag for add_alias: {target_tag['kind']}.{target_tag['code']}\n")
        else:
            target_tag = None

    # 3. Test REJECT (review-bulk)
    print("3. Test REJECT (review-bulk)")
    reject_resp = requests.post(
        f"{API_BASE}/policy/candidates/aggregate/review-bulk",
        json={
            "id_list": ids,
            "state": "rejected",
            "reviewer": "test-script",
            "reviewer_notes": "Test reject",
        },
        headers={"Content-Type": "application/json"},
    )
    reject_resp.raise_for_status()
    j = reject_resp.json()
    updated = j.get("updated") or []
    errors = j.get("errors") or []
    print(f"   updated: {len(updated)}, errors: {len(errors)}")
    if errors:
        print(f"   errors: {errors}")
    else:
        print(f"   SUCCESS: {norm!r} rejected\n")

    # 4. Verify: candidate should NOT appear in proposed, SHOULD appear in rejected
    r3 = requests.get(f"{API_BASE}/policy/lexicon/overview", params={"status": "proposed", "limit": 500, "min_score": "0"})
    r3.raise_for_status()
    after_proposed = [x for x in (r3.json().get("rows") or []) if x.get("row_type") == "candidate"]
    still_there = [x for x in after_proposed if (x.get("normalized") or x.get("key") or "").strip().lower() == norm.strip().lower()]

    r_rej = requests.get(f"{API_BASE}/policy/lexicon/overview", params={"status": "rejected", "limit": 500, "min_score": "0"})
    r_rej.raise_for_status()
    rejected_rows = [x for x in (r_rej.json().get("rows") or []) if x.get("row_type") == "candidate"]
    in_rejected = [x for x in rejected_rows if (x.get("normalized") or x.get("key") or "").strip().lower() == norm.strip().lower()]

    if still_there:
        print(f"   FAIL: {norm!r} still in proposed ({len(still_there)} rows)")
    else:
        print(f"   PASS: {norm!r} no longer in proposed")
    if in_rejected:
        print(f"   PASS: {norm!r} appears in rejected")
    else:
        print(f"   FAIL: {norm!r} NOT in rejected (update may not have persisted)")
    # Debug: raw DB state after reject
    dr2 = requests.get(f"{API_BASE}/policy/candidates/debug", params={"normalized": norm})
    if dr2.ok:
        jd2 = dr2.json()
        print(f"   DEBUG after reject: {jd2.get('count', 0)} rows, states={[r.get('state') for r in jd2.get('rows', [])]}\n")

    # 5. Restore to proposed (so we can test add_alias) - only if we have something to restore
    print("5. Restore to proposed (for add_alias test)")
    restore_resp = requests.post(
        f"{API_BASE}/policy/candidates/aggregate/review-bulk",
        json={
            "id_list": ids,
            "state": "proposed",
            "reviewer": "test-script",
            "reviewer_notes": "Restored for add_alias test",
        },
        headers={"Content-Type": "application/json"},
    )
    restore_resp.raise_for_status()
    jr = restore_resp.json()
    ru = jr.get("updated") or []
    er = jr.get("errors") or []
    print(f"   updated: {len(ru)}, errors: {len(er)}")
    if er:
        print(f"   restore errors: {er}")
    print()

    # 6. Test ADD_ALIAS (apply-operations)
    if target_tag and norm:
        print("6. Test ADD_ALIAS (apply-operations)")
        alias_resp = requests.post(
            f"{API_BASE}/policy/candidates/apply-operations",
            json={
                "operations": [
                    {
                        "op": "add_alias",
                        "normalized": norm,
                        "target_kind": target_tag["kind"],
                        "target_code": target_tag["code"],
                        "reason": "Test add alias",
                        "confidence": 0.95,
                    }
                ]
            },
            headers={"Content-Type": "application/json"},
        )
        alias_resp.raise_for_status()
        ja = alias_resp.json()
        results = ja.get("results") or []
        applied = ja.get("applied_count", 0)
        failed = ja.get("failed_count", 0)
        print(f"   applied: {applied}, failed: {failed}")
        for res in results:
            print(f"   result: {res}")
        if failed > 0:
            print(f"   FAIL: add_alias had failures")
        else:
            print(f"   SUCCESS: add_alias applied\n")

        # 7. Verify: candidate should NOT appear in proposed (absorbed as alias)
        r4 = requests.get(f"{API_BASE}/policy/lexicon/overview", params={"status": "proposed", "limit": 500, "min_score": "0"})
        r4.raise_for_status()
        after_alias = [x for x in (r4.json().get("rows") or []) if x.get("row_type") == "candidate"]
        still_there2 = [x for x in after_alias if (x.get("normalized") or x.get("key") or "").strip().lower() == norm.strip().lower()]
        if still_there2:
            print(f"7. FAIL: {norm!r} still in proposed after add_alias")
        else:
            print(f"7. PASS: {norm!r} no longer in proposed (absorbed as alias)")
    else:
        print("6. Skipping add_alias (no approved tag for target)")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
