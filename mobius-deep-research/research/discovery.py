"""Deep Research — the Discovery seam (ingest STUBBED).

Ingest belongs to the RAG agent under MOBIUS_DISCOVERY_INGEST_CONTRACT.md. This
module is only my side of it: build a well-formed request, submit it, record
whichever of their four outcomes came back, and afterwards check whether the gap
I cited actually moved.

`submit()` is a stub. It records the request and returns `pending` without
calling anything, so the loop, the ledger and the UX are all exercisable today
and swapping in the real endpoint later touches one function.

Three contract rules are honoured here rather than assumed:

  * Every request names the gap it is meant to close. A request without one is
    refused before it is written — that is the site-driven crawling the
    contract exists to prevent.

  * No local dedup. We never suppress a submission to avoid a duplicate, and a
    `duplicate` outcome is recorded as a success and never retried. A fetcher
    cannot tell a duplicate from a product variant from a period series; the
    gate decides. Suppressing locally is how this year's attestation forms
    nearly got retired in favour of last year's.

  * Dates are only ever what the document states. There is no computed-date
    path in this file and no column to put one in.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = "/Users/ananth/Mobius/"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

Outcome = Literal["pending", "created", "duplicate", "rejected", "ours", "error"]

# Their outcomes, and what each means for us. `duplicate` and `ours` are
# terminal successes — the corpus has the document, which is what we wanted.
TERMINAL_SUCCESS = {"created", "duplicate", "ours"}
NEVER_RETRY = {"duplicate", "ours", "rejected"}


@dataclass
class DiscoveryRequest:
    url: str
    discovery_reason: str
    filename: str | None = None
    gap_id: int | None = None
    # Only what the document itself says. Leave None rather than deriving one.
    document_stated_date: str | None = None

    def validate(self) -> None:
        if not (self.discovery_reason or "").strip():
            raise ValueError(
                "discovery_reason is required: name the gap this closes, or do not "
                "submit. Requests without a cited gap cannot be evaluated afterwards.")
        if not (self.url or "").startswith(("http://", "https://")):
            raise ValueError(f"url must be absolute: {self.url!r}")


def db():
    c = psycopg2.connect(DB)
    c.autocommit = True
    return c, c.cursor(cursor_factory=RealDictCursor)


# ── submit ──────────────────────────────────────────────────────────────────
def submit(req: DiscoveryRequest, cur) -> int:
    """Record and submit one discovery request.

    STUB: records the request and returns without calling Discovery. Deliberately
    does NOT check whether we already hold the URL — that check is exactly the
    local dedup the contract forbids. Submit; let their gate answer.
    """
    req.validate()
    cur.execute("""insert into research.discovery_request
                     (gap_id, url, filename, discovery_reason, document_stated_date,
                      submitted_at, outcome, detail)
                   values (%s,%s,%s,%s,%s, now(), 'pending', %s)
                   returning id""",
                (req.gap_id, req.url, req.filename, req.discovery_reason,
                 req.document_stated_date,
                 "STUB: not yet sent — awaiting Discovery endpoint"))
    return cur.fetchone()["id"]


def record_outcome(request_id: int, outcome: Outcome, cur,
                   document_id: str | None = None, detail: str = "") -> None:
    """Record whichever of the four outcomes came back.

    `duplicate` and `ours` are successes. Nothing in this module retries them —
    a 409 means the corpus already has the document, which is the outcome we
    wanted.
    """
    cur.execute("""update research.discovery_request
                      set outcome=%s, document_id=%s, detail=%s, updated_at=now()
                    where id=%s""",
                (outcome, document_id, detail or None, request_id))


def should_retry(outcome: Outcome) -> bool:
    return outcome not in NEVER_RETRY and outcome not in TERMINAL_SUCCESS


# ── did the gap move? ───────────────────────────────────────────────────────
# The contract's closing rule. A batch that fetched 40 documents and moved no
# gap is a finding about the gap, not a success to repeat.
def measure_before(discovery_reason: str, metric: str, value: float, cur) -> int:
    cur.execute("""insert into research.gap_measurement
                     (discovery_reason, metric, value_before) values (%s,%s,%s)
                   returning id""", (discovery_reason, metric, value))
    return cur.fetchone()["id"]


def measure_after(measurement_id: int, value: float, cur, note: str = "") -> str:
    cur.execute("select value_before from research.gap_measurement where id=%s",
                (measurement_id,))
    before = float(cur.fetchone()["value_before"])
    verdict = "moved" if value < before else ("worse" if value > before else "unmoved")
    cur.execute("""update research.gap_measurement
                      set value_after=%s, measured_after_at=now(), verdict=%s, note=%s
                    where id=%s""", (value, verdict, note or None, measurement_id))
    return verdict


def report(cur) -> str:
    """What to say after a batch — including when the answer is 'nothing moved'."""
    cur.execute("""select discovery_reason, metric, value_before, value_after,
                          verdict, submitted, documents_created, already_had, rejected
                     from research.discovery_effect order by discovery_reason""")
    lines = []
    for r in cur.fetchall():
        if r["value_after"] is None:
            lines.append(f"  {r['discovery_reason']}: {r['submitted']} submitted, "
                         f"not yet re-measured")
            continue
        moved = float(r["value_before"]) - float(r["value_after"])
        verdict = r["verdict"]
        line = (f"  {r['discovery_reason']}: {r['metric']} "
                f"{r['value_before']:g} -> {r['value_after']:g} ({verdict}); "
                f"{r['documents_created']} created, {r['already_had']} already held, "
                f"{r['rejected']} rejected")
        if verdict == "unmoved" and r["documents_created"]:
            line += ("\n      ^ fetched documents and closed nothing — the gap or the "
                     "candidate selection is wrong, not the fetching")
        lines.append(line)
    return "\n".join(lines) or "  (no measured batches yet)"


if __name__ == "__main__":
    conn, cur = db()
    print("Discovery seam — ingest stubbed pending MOBIUS_DISCOVERY_INGEST_CONTRACT.md\n")
    cur.execute("select outcome, count(*) n from research.discovery_request group by 1")
    rows = cur.fetchall()
    print("submissions:", {r["outcome"]: r["n"] for r in rows} or "none")
    print("\ngap effect:")
    print(report(cur))
