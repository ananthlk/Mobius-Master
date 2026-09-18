"""Drain research.v_undelivered into the registry, and stamp delivered_at.

The contract agreed with Deep Research 2026-09-18: they own `answered` (provable,
counted from settled field_answer rows), we own `delivered`. Neither side can
assert the other's half.

Why this exists as a separate path from run_sourcing.file_finding(): that one
reads `research.attempt`, which only OUR runner writes. When Deep Research drives
a batch they record to `research.field_answer`, so file_finding() finds nothing
and the answer strands. 47 requests were sitting undelivered — 62 facts and 7
absences — the oldest being request_id 1. The write-back was never broken; it was
only ever reachable down one of the two paths that produce answers.

TWO RULES THAT ARE NOT NEGOTIABLE HERE:

  * An ABSENCE IS NOT DELIVERABLE-AND-DONE. Deep Research's caveat, and Ananth's
    rule: the source was read and does not carry the fact, which is a finding a
    person must actively close. Filing it as `sourced` would turn "we looked and
    it is not there" into "we hold an answer". Absences are reported, never filed.

  * A HUMAN DECISION IS NEVER OVERWRITTEN. Same guard as file_finding().
"""
import argparse
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open("/Users/ananth/Mobius/mobius-rag/.env")
      if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

FACT_VERDICTS = ("answered", "varies")


def compose(rows):
    """Same rules as run_sourcing.file_finding(): a bare boolean is not a statement.

    The slot name says what the boolean is ABOUT and the quote says it in the
    document's words — `prior_authorization` filed as the single word "true" is
    the value, not the finding.
    """
    seen, parts, doc = set(), [], None
    for f in rows:
        val = f["value"]
        if isinstance(val, bool) or str(val).lower() in ("true", "false"):
            said = (f["field"] or "").replace("_", " ")
            yes = str(val).lower() == "true"
            txt = (f["quote"] or "").strip() if isinstance(f["quote"], str) else ""
            txt = txt or f"{said.capitalize()} is {'required' if yes else 'not required'}."
        elif isinstance(val, (list, dict)):
            # A conditional slot arrives as {"when": ..., "value": ...}, sometimes in
            # a list. str() on that files a PYTHON REPR as the statement a reviewer
            # reads — braces, quotes and all. Caught in the dry run on req 2085
            # (rhc_encounter/prior_authorization). Same rule as the boolean above:
            # render what it MEANS, and never the literal the extractor happened to
            # use to carry it.
            def one(x):
                if isinstance(x, dict):
                    v = str(x.get("value") or x.get("text") or "").strip()
                    w = str(x.get("when") or x.get("condition") or "").strip()
                    return f"{v} ({w})" if v and w else (v or w)
                return str(x)
            items = val if isinstance(val, list) else [val]
            txt = ", ".join(t for t in (one(x) for x in items) if t)
        else:
            txt = str(val)
        txt = (txt or "").strip()
        if txt and txt not in seen:
            seen.add(txt)
            parts.append(txt)
        doc = doc or f["document"]
    return "; ".join(parts)[:4000], doc


def main(apply_it):
    conn = psycopg2.connect(DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""select u.request_id, u.subject_id, u.facts, u.absences,
                          l.requirement_id
                     from research.v_undelivered u
                     left join service_line.sourcing_link l on l.request_id = u.request_id
                    where u.consumer = 'service_line_registry'
                    order by u.request_id""")
    rows = cur.fetchall()

    filed = absent_only = held = unmapped = skipped_test = 0
    for u in rows:
        # "-al" is this seat's test-record marking convention. A test row must never
        # become a sourced fact, and it is deliberately not linked.
        if (u["subject_id"] or "").endswith("-al"):
            skipped_test += 1
            continue
        if not u["requirement_id"]:
            unmapped += 1
            print(f"  UNMAPPED   req {u['request_id']}  {u['subject_id']}")
            continue

        cur.execute("""select state from service_line.review_state
                        where subject_kind='requirement' and subject_id=%s""",
                    (str(u["requirement_id"]),))
        seen = cur.fetchone()
        if seen and (seen.get("state") or "unreviewed") != "unreviewed":
            held += 1
            print(f"  HELD       req {u['request_id']}  a person has already decided this")
            continue

        cur.execute("""select field, verdict, value, quote, document
                         from research.field_answer
                        where request_id=%s
                        order by round, field""",
                    (u["request_id"],))
        every = cur.fetchall()
        facts = [f for f in every if f["verdict"] in FACT_VERDICTS]
        # A PARTIAL SURVIVOR IS NOT AN ANSWER (contract 16). The first version of
        # this drain selected only answered slots, so a requirement whose `pos_codes`
        # was never settled filed as a confident statement of its settings — 20 of
        # the first 41 were partials and not one of them said so.
        #   insufficient = the loop never established it       (our effort)
        #   absent       = source was read and does not say it (a finding)
        # Kept apart because a partial that hides which is which reads as a blank.
        unresolved = sorted({f["field"] for f in every if f["verdict"] == "insufficient"})
        absent = sorted({f["field"] for f in every if f["verdict"] == "absent"})
        if not facts:
            # Settled with absences only. Reported, never filed — see module docstring.
            absent_only += 1
            print(f"  ABSENCE    req {u['request_id']}  {u['subject_id']}  "
                  f"({u['absences']} absence(s)) — needs active closure, NOT filed")
            continue

        statement, doc = compose(facts)
        if not statement:
            absent_only += 1
            continue
        print(f"  FILE       req {u['request_id']}  req#{u['requirement_id']}  "
              f"{u['subject_id']}\n             {statement[:110]}"
              f"{chr(10)+'             PARTIAL unresolved='+str(unresolved)+' absent='+str(absent) if (unresolved or absent) else ''}")
        if apply_it:
            cur.execute("""update service_line.standard_requirement
                              -- 'interpreted': a model read this out of a policy.
                              -- NOT 'parsed', which means a structured source, and not
                              -- 'extracted', which is not in the vocabulary at all —
                              -- the CHECK constraint caught that on the first apply.
                              set statement=%s, sourced=true, origin='interpreted',
                                  source_ref=coalesce(%s, source_ref),
                                  unresolved_slots=%s, absent_slots=%s
                            where id=%s""", (statement, doc, unresolved or None,
                         absent or None, u["requirement_id"]))
            cur.execute("update research.request set delivered_at=now() where id=%s",
                        (u["request_id"],))
        filed += 1

    print(f"\n{'APPLIED' if apply_it else 'DRY RUN'}: "
          f"{filed} to file · {absent_only} absence-only (not filed) · "
          f"{held} held for human decision · {unmapped} unmapped · "
          f"{skipped_test} test records skipped")
    if apply_it:
        conn.commit()
        print("committed; delivered_at stamped only on the rows actually filed")
    else:
        conn.rollback()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="write; default is a dry run")
    main(p.parse_args().apply)
