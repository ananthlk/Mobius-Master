"""Deep Research — the acquire arm.

Handles exactly one gap class: `not_in_corpus`. The document that would answer
the question exists, we know its URL, and we do not hold it. Fetch it, put it
through the canonical ingest path, wait for it to become retrievable, then
re-ask.

Deliberately narrow. It refuses to run on a gap it has not first proved is an
acquisition gap — the whole point of the classifier is that most misses are not
missing documents, and re-fetching something we already hold is the failure
mode this module exists to prevent.

Every step writes to research.* before it acts, so a run that dies halfway
leaves a readable trail rather than a mystery.

    python3 acquire.py --consumer service_line_registry [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = "/Users/ananth/Mobius/"
RAG = os.environ.get("MOBIUS_RAG_URL", "http://127.0.0.1:8000")
MANIFEST = ROOT + "docs/ahca-manifests/ahca_BH_sources.csv"
STAGING = "/private/tmp/claude-502/-Users-ananth-Mobius/deep-research-staging"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

# Jurisdiction stamped on anything we ingest from this manifest. AHCA publishes
# it, it binds Florida Medicaid, and retrieval filters on these three.
PAYER, STATE, PROGRAM = "AHCA", "FL", "Medicaid"


def db():
    c = psycopg2.connect(DB)
    c.autocommit = True
    return c, c.cursor(cursor_factory=RealDictCursor)


# ── candidate resolution ────────────────────────────────────────────────────
def manifest_rows() -> list[dict]:
    return list(csv.DictReader(open(MANIFEST)))


def newest(cands: list[dict]) -> dict | None:
    """Prefer the most recent effective date; the manifest's dates are messy
    strings, so sort on what we have rather than parsing them."""
    if not cands:
        return None
    return sorted(cands, key=lambda r: (r.get("effective") or ""), reverse=True)[0]


def prove_not_in_corpus(cur, filename: str) -> tuple[bool, str]:
    """A gap is only an acquisition gap if we genuinely do not hold the file."""
    cur.execute("select id, status from documents where filename=%s", (filename,))
    row = cur.fetchone()
    if row:
        return False, f"already held as {row['id']} (status={row['status']})"
    return True, "no document with this filename in the corpus"


# ── fetch ───────────────────────────────────────────────────────────────────
def fetch(url: str, dest: str) -> tuple[bool, str]:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mobius-deep-research/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            f.write(r.read())
    except Exception as exc:
        return False, f"download failed: {exc}"
    size = os.path.getsize(dest)
    if size < 1024:
        return False, f"downloaded {size} bytes — too small to be the document"
    with open(dest, "rb") as f:
        magic = f.read(5)
    if not magic.startswith(b"%PDF"):
        return False, f"not a PDF (magic={magic!r})"
    return True, f"{size} bytes"


# ── ingest ──────────────────────────────────────────────────────────────────
def upload(path: str, source_url: str) -> tuple[str | None, str]:
    """POST /upload — the canonical path. Auto-queues extract -> chunk ->
    embed -> publish, so everything lands the same way a UI upload does."""
    boundary = "----mobiusdeepresearch"
    name = os.path.basename(path)
    with open(path, "rb") as f:
        payload = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()

    qs = urllib.parse.urlencode({
        "payer": PAYER, "state": STATE, "program": PROGRAM,
        "source_url": source_url, "agent_scope": "agent",
    })
    req = urllib.request.Request(
        f"{RAG}/upload?{qs}", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.load(r)
    except Exception as exc:
        detail = ""
        if hasattr(exc, "read"):
            try:
                detail = exc.read().decode()[:300]
            except Exception:
                pass
        return None, f"upload failed: {exc} {detail}"
    doc_id = data.get("document_id") or data.get("id") or (data.get("document") or {}).get("id")
    return doc_id, json.dumps(data)[:200]


def wait_until_retrievable(cur, doc_id: str, timeout_s: int = 900) -> tuple[bool, str]:
    """Retrievable means: extraction done AND chunks exist. Anything less and a
    re-ask would fail for a reason that has nothing to do with the source."""
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        cur.execute("select status from documents where id=%s", (doc_id,))
        row = cur.fetchone()
        status = (row or {}).get("status")
        cur.execute("select count(*) n from document_pages where document_id=%s", (doc_id,))
        pages = cur.fetchone()["n"]
        cur.execute("select count(*) n from hierarchical_chunks where document_id=%s", (doc_id,))
        chunks = cur.fetchone()["n"]
        last = f"status={status} pages={pages} chunks={chunks}"
        if status == "completed" and chunks > 0:
            return True, last
        if status in ("failed", "error"):
            return False, last
        time.sleep(15)
    return False, f"timed out after {timeout_s}s ({last})"


# ── the arm ─────────────────────────────────────────────────────────────────
def run(consumer: str, dry_run: bool) -> None:
    conn, cur = db()
    rows = manifest_rows()

    # Lines with no rendered_as codes at all are the acquisition candidates:
    # the registry named the line but holds nothing priced for it.
    cur.execute("""
        select l.key, l.name, l.rule_ref
          from service_line.line l
         where l.scope = 'serve'
           and not exists (select 1 from service_line.line_code c
                            where c.line_key = l.key and c.binding_role = 'rendered_as')
           and l.key in ('bh_overlay','sipp','behavior_analysis','specialized_therapeutic')
         order by l.key""")
    targets = cur.fetchall()
    print(f"acquisition candidates: {len(targets)}\n")

    PATTERNS = {
        "bh_overlay": ["BHOS Fee Schedule", "Behavioral Health Overlay Services Fee"],
        "sipp": ["SIPP Billing Codes"],
        "behavior_analysis": ["BA Fee Schedule", "Behavior Analysis Fee Schedule"],
        "specialized_therapeutic": ["Specialized Therapeutic Services"],
    }

    for t in targets:
        key = t["key"]
        print(f"══ {key} — {t['name'][:52]}")
        cands = [r for r in rows
                 if any(p.lower() in r["filename"].lower() for p in PATTERNS.get(key, []))]
        cand = newest(cands)
        if not cand:
            print("   no candidate in manifest — cannot acquire\n")
            continue

        ok, why = prove_not_in_corpus(cur, cand["filename"])
        print(f"   candidate: {cand['filename'][:58]}")
        print(f"   check:     {why}")
        if not ok:
            print("   -> not an acquisition gap; skipping\n")
            continue

        # Record the request + gap before acting.
        cur.execute("""insert into research.request
                         (consumer, subject_type, subject_id, question, expects, jurisdiction)
                       values (%s,'service_line',%s,%s,%s,'FL Medicaid')
                       on conflict (consumer, subject_type, subject_id)
                         do update set question=excluded.question
                       returning id""",
                    (consumer, key,
                     f"What codes, modifiers and service definitions does Florida Medicaid "
                     f"publish for {t['name']}?",
                     "A fee schedule listing procedure codes with modifiers and descriptions"))
        rid = cur.fetchone()["id"]
        cur.execute("""insert into research.gap
                         (request_id, gap_class, evidence, candidate_document, candidate_url)
                       values (%s,'not_in_corpus',%s,%s,%s) returning id""",
                    (rid, f"Manifest names this document for the line; {why}",
                     cand["filename"], cand["url"]))
        gid = cur.fetchone()["id"]
        cur.execute("""insert into research.repair (gap_id, action, detail, state)
                       values (%s,'acquire',%s,'proposed') returning id""",
                    (gid, json.dumps({"url": cand["url"], "filename": cand["filename"]})))
        repair_id = cur.fetchone()["id"]

        if dry_run:
            print("   -> dry run; would download + ingest\n")
            continue

        dest = os.path.join(STAGING, cand["filename"])
        ok, detail = fetch(cand["url"], dest)
        print(f"   download:  {detail}")
        if not ok:
            cur.execute("update research.repair set state='failed', error=%s where id=%s",
                        (detail, repair_id))
            print()
            continue

        doc_id, detail = upload(dest, cand["url"])
        print(f"   ingest:    {doc_id or detail}")
        if not doc_id:
            cur.execute("update research.repair set state='failed', error=%s where id=%s",
                        (detail, repair_id))
            print()
            continue

        ok, detail = wait_until_retrievable(cur, doc_id)
        print(f"   retrieval: {detail}")
        cur.execute("""update research.repair
                          set state=%s, applied_at=now(),
                              detail = detail || %s::jsonb, error=%s
                        where id=%s""",
                    ("applied" if ok else "failed",
                     json.dumps({"document_id": doc_id, "result": detail}),
                     None if ok else detail, repair_id))
        cur.execute("update research.gap set candidate_document_id=%s where id=%s",
                    (doc_id, gid))
        print(f"   -> {'ingested; ready to re-ask' if ok else 'ingest incomplete'}\n")

    print("\n── acquisition ledger ──")
    cur.execute("""select rp.state, count(*) n from research.repair rp
                    where rp.action='acquire' group by 1 order by 2 desc""")
    for r in cur.fetchall():
        print(f"  {r['state']}: {r['n']}")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--consumer", default="service_line_registry")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.consumer, a.dry_run)
