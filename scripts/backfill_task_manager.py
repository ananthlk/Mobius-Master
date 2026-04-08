#!/usr/bin/env python3
"""One-time backfill: push existing roster_truth.open_tasks and credentialing
pml_flagged rows into the unified mobius_task table via the task-manager skill.

Safe to re-run — the bulk-import endpoint uses ON CONFLICT DO UPDATE.

Usage:
    python scripts/backfill_task_manager.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import httpx
import psycopg2
from dotenv import load_dotenv

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _env in [
    os.path.join(_root, "mobius-chat", ".env"),
    os.path.join(_root, "mobius-config", ".env"),
    os.path.join(_root, ".env"),
]:
    if os.path.exists(_env):
        load_dotenv(_env, override=False)

TASK_MANAGER_URL = (
    os.environ.get("CHAT_SKILLS_TASK_MANAGER_URL") or "http://localhost:8015"
).rstrip("/")
DB_URL = (
    os.environ.get("CHAT_RAG_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
).replace("+asyncpg", "")

DRY_RUN = "--dry-run" in sys.argv


def _post_bulk(tasks: list[dict]) -> int:
    if DRY_RUN:
        for t in tasks[:3]:
            print(f"  [dry] {t.get('source_module'):20} {t.get('type'):15} {t.get('text','')[:60]}")
        return len(tasks)
    try:
        r = httpx.post(
            f"{TASK_MANAGER_URL}/tasks/bulk-import",
            json={"tasks": tasks},
            timeout=30.0,
        )
        r.raise_for_status()
        return int(r.json().get("imported", 0))
    except Exception as e:
        print(f"  ERROR bulk-import: {e}")
        return 0


SEV_MAP = {"critical": "critical", "warning": "warning", "info": "info",
           "low": "low", "none": "none"}


def sev(raw: str | None) -> str:
    return SEV_MAP.get((raw or "").lower(), "low")


def backfill_roster_truth(conn) -> int:
    """Read all non-empty open_tasks from roster_truth and bulk-import."""
    cur = conn.cursor()
    cur.execute("""
        SELECT org_name, provider_key, provider_name,
               npi_roster, npi_validated, open_tasks
        FROM roster_truth
        WHERE open_tasks IS NOT NULL
          AND open_tasks != '[]'::jsonb
    """)
    rows = cur.fetchall()
    print(f"\n[roster_truth] {len(rows)} rows with open_tasks")

    batch: list[dict] = []
    for org_name, provider_key, provider_name, npi_roster, npi_validated, tasks in rows:
        npi = str(npi_validated or npi_roster or provider_key or "")
        pname = provider_name or str(provider_key)
        for t in (tasks or []):
            dim = t.get("dim") or ""
            ttype = t.get("type") or "open"
            reason = t.get("reason") or ""
            text = f"{ttype.replace('_', ' ').title()} — {dim}: {reason}" if reason else \
                   f"{ttype.replace('_', ' ').title()} on {dim}"
            batch.append({
                "org_name": org_name,
                "source_module": "roster_open",
                "source_ref": npi,
                "provider_name": pname,
                "npi": npi,
                "type": ttype,
                "severity": sev(t.get("severity")),
                "status": "open",
                "text": text,
                "detail": reason,
                "dim": dim,
                "run_id": None,
            })

    print(f"  → {len(batch)} tasks to import (roster drift/promote tasks)")
    if not batch:
        return 0

    # Send in chunks of 200
    imported = 0
    for i in range(0, len(batch), 200):
        chunk = batch[i:i + 200]
        n = _post_bulk(chunk)
        imported += n
        print(f"  chunk {i//200 + 1}: imported {n}")
    return imported


def backfill_pml_flagged(conn) -> int:
    """Read pml_flagged from latest credentialing run per org and import."""
    cur = conn.cursor()
    # Get latest run per org
    cur.execute("""
        SELECT DISTINCT ON (body->>'org_name')
            run_id,
            body->>'org_name' as org_name,
            body->'orchestrator_state_dict'->'pml_flagged' as pml_flagged
        FROM credentialing_runs
        WHERE body->'orchestrator_state_dict'->'pml_flagged' IS NOT NULL
        ORDER BY body->>'org_name', created_at DESC
    """)
    rows = cur.fetchall()
    print(f"\n[credentialing/pml] {len(rows)} runs with pml_flagged")

    batch: list[dict] = []
    for run_id, org_name, pml_flagged in rows:
        if not pml_flagged or not isinstance(pml_flagged, list):
            continue
        for p in pml_flagged:
            npi = str(p.get("npi") or "")
            pname = p.get("provider_name") or npi
            issues = p.get("issues") or []
            warnings = p.get("warnings") or []
            all_issues = issues + warnings
            issue_text = "; ".join(str(x) for x in all_issues[:3]) if all_issues else "PML alignment issue"
            # One task per flagged provider (dim=pml_alignment)
            batch.append({
                "org_name": org_name or "",
                "source_module": "credentialing",
                "source_ref": npi or run_id,   # NPI makes each provider unique in dedup key
                "provider_name": pname,
                "npi": npi,
                "type": "pml_flagged",
                "severity": "warning",
                "status": "open",
                "text": f"PML flagged: {pname} — {issue_text[:120]}",
                "detail": json.dumps({"issues": issues, "warnings": warnings, "recommendation": p.get("recommendation")}),
                "dim": "pml_alignment",
                "run_id": run_id,
            })

    print(f"  → {len(batch)} PML tasks to import")
    if not batch:
        return 0

    imported = _post_bulk(batch)
    print(f"  imported {imported}")
    return imported


def backfill_recon_tasks(conn) -> int:
    """Check localStorage-equivalent recon_tasks stored in credentialing run body."""
    cur = conn.cursor()
    cur.execute("""
        SELECT run_id, body->>'org_name' as org_name,
               body->'recon_tasks' as recon_tasks
        FROM credentialing_runs
        WHERE body->'recon_tasks' IS NOT NULL
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    print(f"\n[credentialing/recon] {len(rows)} runs with recon_tasks in body")

    batch: list[dict] = []
    for run_id, org_name, recon_tasks in rows:
        if not recon_tasks or not isinstance(recon_tasks, list):
            continue
        for t in recon_tasks:
            batch.append({
                **t,
                "org_name": org_name or t.get("org_name") or "",
                "source_module": "roster_recon",
                "run_id": run_id,
            })

    print(f"  → {len(batch)} recon tasks to import")
    if not batch:
        return 0

    imported = _post_bulk(batch)
    print(f"  imported {imported}")
    return imported


def main():
    if not DB_URL:
        print("ERROR: no database URL (set CHAT_RAG_DATABASE_URL)")
        sys.exit(1)

    print(f"Task manager URL: {TASK_MANAGER_URL}")
    print(f"Database: {DB_URL[:40]}...")
    if DRY_RUN:
        print("DRY RUN — no writes to task manager\n")

    # Health check
    try:
        r = httpx.get(f"{TASK_MANAGER_URL}/health", timeout=5.0)
        print(f"Task manager health: {r.json()}")
    except Exception as e:
        print(f"ERROR: task manager not reachable: {e}")
        sys.exit(1)

    conn = psycopg2.connect(DB_URL)

    total = 0
    total += backfill_roster_truth(conn)
    total += backfill_pml_flagged(conn)
    total += backfill_recon_tasks(conn)

    conn.close()
    print(f"\n{'[DRY RUN] Would import' if DRY_RUN else 'Total imported'}:  {total} tasks")


if __name__ == "__main__":
    main()
