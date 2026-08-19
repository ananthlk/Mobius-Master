"""Deep Research — the turn runner.

The invoker arrives with a query and its own evaluator prompt / extraction
schema. From there each turn runs two tracks and advances only when both settle:

    track A   ask -> parse -> validate -> extract -> refine the next query
    track B   dispatch feedback: Discovery ingest / Lexicon / human

Track A settles in seconds. Track B settles in minutes, hours, or days — ingest
is async and a person is asleep. So `advance()` is idempotent and resumable:
call it on a schedule, it moves whatever is due and returns. Nothing is held in
memory between turns, because nothing can be.

Advancing on track A alone re-asks the corpus that just failed and burns a turn.
Advancing on track B alone discards the refinement the answer earned. Both, or
wait — and waiting is a normal state here, not a failure.

    python3 runner.py open   --consumer X --subject Y --query "..." --evaluator-file p.txt
    python3 runner.py advance          # move every due turn; safe to run on a cron
    python3 runner.py status
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor, Json

ROOT = "/Users/ananth/Mobius/"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

# Backoff for a waiting turn. Ingest lands in minutes; a human lands tomorrow.
# Polling a human-blocked turn every 30s is noise that hides the turns that
# actually moved.
BACKOFF_S = [60, 300, 900, 3600, 10800, 21600]   # 1m 5m 15m 1h 3h 6h


def db():
    c = psycopg2.connect(DB)
    c.autocommit = True
    return c, c.cursor(cursor_factory=RealDictCursor)


def _backoff(poll_count: int) -> datetime:
    s = BACKOFF_S[min(poll_count, len(BACKOFF_S) - 1)]
    return datetime.now(timezone.utc) + timedelta(seconds=s)


# ── invocation ──────────────────────────────────────────────────────────────
def open_request(cur, *, consumer: str, subject_type: str, subject_id: str,
                 query: str, evaluator_prompt: str, extraction_schema: dict | None,
                 expects: str = "", jurisdiction: str = "", max_rounds: int = 3,
                 invoker: str = "") -> int:
    """Register an invocation and lay down turn 1.

    The evaluator prompt is required. The module does not know what a good
    answer looks like for someone else's fact store, and a generic evaluator is
    how you get confidently wrong extractions written to a certified store.
    """
    if not (evaluator_prompt or "").strip():
        raise ValueError(
            "evaluator_prompt is required — the invoker must say how to judge and "
            "extract an answer for its own fact store.")
    cur.execute("""insert into research.request
                     (consumer, subject_type, subject_id, question, expects, jurisdiction,
                      max_rounds, evaluator_prompt, extraction_schema, invoker)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   on conflict (consumer, subject_type, subject_id) do update
                     set question=excluded.question,
                         evaluator_prompt=excluded.evaluator_prompt,
                         extraction_schema=excluded.extraction_schema
                   returning id""",
                (consumer, subject_type, subject_id, query, expects or None,
                 jurisdiction or None, max_rounds, evaluator_prompt,
                 Json(extraction_schema) if extraction_schema else None,
                 invoker or consumer))
    rid = cur.fetchone()["id"]
    cur.execute("""insert into research.turn (request_id, n, query, status)
                   values (%s,1,%s,'running')
                   on conflict (request_id, n) do nothing""", (rid, query))
    return rid


# ── track B settlement ──────────────────────────────────────────────────────
def _feedback_settled(cur, turn: dict) -> tuple[bool, str]:
    """Has the feedback this turn dispatched actually landed?

    Reads the target ledgers rather than trusting a local flag — the whole point
    of dispatching to Discovery/Lexicon/a human is that they answer on their own
    clock, in their own table.
    """
    ref = turn["feedback_ref"] or {}
    kind = turn["feedback_kind"]

    if kind == "discovery":
        ids = ref.get("discovery_request_ids") or []
        if not ids:
            return True, "no discovery requests recorded"
        cur.execute("""select count(*) n from research.discovery_request
                        where id = any(%s) and outcome = 'pending'""", (ids,))
        pending = cur.fetchone()["n"]
        return (pending == 0), (f"{pending} of {len(ids)} still pending"
                                if pending else f"all {len(ids)} resolved")

    if kind == "lexicon":
        ids = ref.get("lexicon_feedback_ids") or []
        if not ids:
            return True, "no lexicon feedback recorded"
        cur.execute("""select count(*) n from research.lexicon_feedback
                        where id = any(%s) and state = 'proposed'""", (ids,))
        open_ = cur.fetchone()["n"]
        return (open_ == 0), (f"{open_} term(s) awaiting adoption"
                              if open_ else "adopted or rejected")

    if kind == "human":
        ids = ref.get("escalation_ids") or []
        if not ids:
            return True, "no escalation recorded"
        cur.execute("""select count(*) n from research.escalation
                        where id = any(%s) and state = 'open'""", (ids,))
        open_ = cur.fetchone()["n"]
        return (open_ == 0), ("awaiting a human" if open_ else "answered")

    return True, "no feedback dispatched"


# ── advance ─────────────────────────────────────────────────────────────────
def advance(cur, verbose: bool = True) -> dict:
    """Move every turn whose gate has opened. Idempotent; safe on a cron."""
    moved = {"advanced": 0, "still_waiting": 0, "completed": 0}

    cur.execute("""select t.*, r.max_rounds, r.status as request_status
                     from research.turn t
                     join research.request r on r.id = t.request_id
                    where t.status in ('running','waiting')
                      and (t.next_poll_at is null or t.next_poll_at <= now())
                    order by t.request_id, t.n""")
    turns = [dict(x) for x in cur.fetchall()]

    for t in turns:
        a_settled = t["extract_state"] != "pending"
        b_settled, why_b = _feedback_settled(cur, t)

        if not (a_settled and b_settled):
            blocked = "parser" if not a_settled else (t["feedback_kind"] or "feedback")
            cur.execute("""update research.turn
                              set status='waiting', poll_count=poll_count+1,
                                  next_poll_at=%s
                            where id=%s""", (_backoff(t["poll_count"]), t["id"]))
            moved["still_waiting"] += 1
            if verbose:
                print(f"  req {t['request_id']} turn {t['n']}: waiting on {blocked} — {why_b}")
            continue

        # Both tracks settled. Mark the gate and decide what happens next.
        cur.execute("""update research.turn
                          set both_settled_at=now(), status='complete',
                              feedback_state = case when feedback_state='dispatched'
                                                    then 'settled' else feedback_state end
                        where id=%s""", (t["id"],))
        moved["advanced"] += 1

        if t["extract_state"] == "extracted":
            cur.execute("""update research.request
                              set status='sourced', resolved_at=now() where id=%s""",
                        (t["request_id"],))
            moved["completed"] += 1
            if verbose:
                print(f"  req {t['request_id']} turn {t['n']}: extracted — request sourced")
            continue

        # Not extracted. Another turn, but only if there is a refined query and
        # rounds left. Re-asking the same question after a repair is fine; asking
        # it unchanged with no repair is how a loop spins.
        nxt = t["n"] + 1
        if nxt > (t["max_rounds"] or 3):
            cur.execute("""insert into research.escalation
                             (request_id, reason, asked, what_we_checked)
                           values (%s,'rounds_exhausted',%s,%s)
                           returning id""",
                        (t["request_id"], t["query"],
                         f"{t['n']} turns; last extract state {t['extract_state']}; "
                         f"feedback {t['feedback_kind'] or 'none'} ({why_b})"))
            cur.execute("update research.request set status='escalated' where id=%s",
                        (t["request_id"],))
            if verbose:
                print(f"  req {t['request_id']}: rounds exhausted after {t['n']} — escalated")
            continue

        next_query = t["next_query"] or t["query"]
        cur.execute("""insert into research.turn (request_id, n, query, status)
                       values (%s,%s,%s,'running')
                       on conflict (request_id, n) do nothing""",
                    (t["request_id"], nxt, next_query))
        if verbose:
            refined = "refined" if t["next_query"] else "unchanged (repair only)"
            print(f"  req {t['request_id']} turn {t['n']} -> {nxt}: {refined}")

    return moved


# ── track recording, called by the ask/parse and repair steps ───────────────
def record_extract(cur, turn_id: int, state: str, note: str = "",
                   next_query: str | None = None) -> None:
    cur.execute("""update research.turn
                      set extract_state=%s, extract_note=%s, next_query=%s
                    where id=%s""", (state, note or None, next_query, turn_id))


def dispatch_feedback(cur, turn_id: int, kind: str, ref: dict) -> None:
    """Record that this turn handed work to Discovery / Lexicon / a human.

    Settlement is read back from their ledgers, never asserted here.
    """
    cur.execute("""update research.turn
                      set feedback_state='dispatched', feedback_kind=%s,
                          feedback_ref=%s, status='waiting', next_poll_at=now()
                    where id=%s""", (kind, Json(ref), turn_id))


def status(cur) -> None:
    cur.execute("""select request_id, n, blocked_on, waiting_for, poll_count
                     from research.waiting_on order by request_id, n""")
    rows = cur.fetchall()
    print(f"open turns: {len(rows)}")
    for r in rows:
        wait = str(r["waiting_for"]).split(".")[0]
        print(f"  req {r['request_id']} turn {r['n']}: blocked on {r['blocked_on']} "
              f"({wait}, {r['poll_count']} polls)")
    cur.execute("""select status, count(*) n from research.request group by 1""")
    print("requests:", {r["status"]: r["n"] for r in cur.fetchall()})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["open", "advance", "status"])
    ap.add_argument("--consumer"); ap.add_argument("--subject")
    ap.add_argument("--subject-type", default="fact")
    ap.add_argument("--query"); ap.add_argument("--evaluator-file")
    ap.add_argument("--max-rounds", type=int, default=3)
    a = ap.parse_args()
    conn, cur = db()

    if a.command == "open":
        if not (a.consumer and a.subject and a.query and a.evaluator_file):
            sys.exit("open needs --consumer --subject --query --evaluator-file")
        rid = open_request(cur, consumer=a.consumer, subject_type=a.subject_type,
                           subject_id=a.subject, query=a.query,
                           evaluator_prompt=open(a.evaluator_file).read(),
                           extraction_schema=None, max_rounds=a.max_rounds)
        print(f"request {rid} opened, turn 1 laid down")
    elif a.command == "advance":
        print(json.dumps(advance(cur), indent=2))
    else:
        status(cur)
