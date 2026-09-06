"""Machine extraction of benefit limits, graded against the hand-read table.

backfill_benefit_limits.py works because 28 sentences is small enough to read by
hand. That does not survive the next fee schedule — 55 are already in the corpus
and the AHCA page lists ~140. This is the arm that replaces the hand.

The gate is the same one 048 enforces in the database, not in the prompt:

  * a unit count is not a limit until something defines the unit
  * a capped limit needs a period
  * "no cap" is a distinct sourced answer from "unknown"

So a bad extraction fails at a CHECK constraint, not at a judgement call. The
model is asked for a reading; the schema decides whether it is admissible.

Grading is against the 28 hand readings. Two honesty caveats, stated because
they change what the number means:

  1. This is not a blind eval. I wrote the hand table AND this prompt, so
     agreement partly measures whether the machine reproduces my reading rather
     than whether my reading was right. The H0032 "per provider" call would
     agree for the wrong reason. A fair grade needs a second schedule nobody has
     hand-read.
  2. The prompt is never shown the expected answer. It receives the sentence,
     the enums and the completeness rule — nothing else.

    python3 extract_benefit_limits.py [--limit N] [--verbose]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

import psycopg2

ROOT = "/Users/ananth/Mobius/"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

sys.path.insert(0, ROOT + "mobius-chat")
from dotenv import load_dotenv                                     # noqa: E402
load_dotenv(ROOT + "mobius-chat/.env")
from app.services.llm_manager import generate_sync                 # noqa: E402

sys.path.insert(0, ROOT + "docs/service-lines/scripts")
from backfill_benefit_limits import READING, REFUSED               # noqa: E402

LIMIT_TYPES = ["units", "visits", "encounters", "hours", "days", "dollars",
               "episodes", "evaluations", "admissions"]
PERIODS = ["per_service", "day", "week", "month", "quarter", "state_fiscal_year",
           "calendar_year", "episode", "admission", "lifetime"]
PER_WHOM = ["recipient", "recipient_per_provider", "provider", "episode", "admission"]

PROMPT = """You are turning one sentence from a state Medicaid fee schedule into a
structured service limit. Read ONLY the sentence. Do not use outside knowledge of
Medicaid, and do not complete anything the sentence leaves unsaid.

SENTENCE:
{sentence}

Return ONLY JSON:
{{
  "states_a_limit": true|false,
  "limit_type": one of {limit_types},
  "amount": number, or null if the sentence states no numeric cap,
  "unit_definition": "what ONE of that thing is, in the sentence's own terms", or null,
  "period": one of {periods}, or null,
  "per_whom": one of {per_whom}, or null,
  "unlimited": true only if the sentence affirmatively says there is no numeric cap,
  "reason": "if states_a_limit is false, why"
}}

Rules, applied strictly:
- A number with no stated unit is INCOMPLETE. If the sentence says "1 unit" and
  never says what a unit is, set unit_definition to null and say so — do not
  infer that a unit is a month, a visit, or anything else.
- "as medically necessary" is a real answer of NO numeric cap: amount null,
  unlimited true.
- period is the window the cap applies over. "per state fiscal year" is
  state_fiscal_year; "daily" is day; "per month" is month.
- per_whom is WHOSE allowance is capped, and only if the sentence says. "per
  recipient" is recipient. "per provider" for a per-recipient service is
  recipient_per_provider. If the sentence does not say, use null — do not guess.
- A sentence may state a cap on a DIFFERENT axis than you expect. Report the one
  the sentence actually states.
- If the sentence is not a limit at all, states_a_limit false.
"""


def ask(sentence: str, tries: int = 3) -> dict:
    """LLMManager retries the transport now; this retries a model that returns
    something unparseable, which is a different failure and still ours to absorb.
    A grading run that dies on one bad response grades nothing."""
    prompt = PROMPT.format(sentence=sentence, limit_types=LIMIT_TYPES,
                           periods=PERIODS, per_whom=PER_WHOM)
    for attempt in range(tries):
        try:
            raw, usage = generate_sync(prompt, stage="parser", max_tokens=600, parser=True)
            break
        except Exception as e:
            if attempt == tries - 1:
                return {"_error": f"{type(e).__name__}: {str(e)[:120]}", "_model": None}
            time.sleep(2 * (attempt + 1))
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {"_error": "no JSON in response", "_model": usage.get("model")}
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"_error": f"bad JSON: {e}", "_model": usage.get("model")}
    d["_model"] = usage.get("model")
    return d


def admissible(d: dict) -> tuple[bool, str]:
    """The database's constraints, applied before the write rather than after."""
    if not d.get("states_a_limit"):
        return False, d.get("reason") or "not a limit"
    if d.get("unlimited"):
        if d.get("amount") is not None:
            return False, "unlimited with an amount"
        return True, ""
    if d.get("amount") is None:
        return False, "capped but no amount"
    if d.get("limit_type") == "units" and not d.get("unit_definition"):
        return False, "unit count with no unit definition"
    if not d.get("period"):
        return False, "capped but no period"
    if d.get("limit_type") not in LIMIT_TYPES:
        return False, f"limit_type {d.get('limit_type')!r} not in the enum"
    if d.get("period") not in PERIODS:
        return False, f"period {d.get('period')!r} not in the enum"
    if d.get("per_whom") is not None and d.get("per_whom") not in PER_WHOM:
        return False, f"per_whom {d.get('per_whom')!r} not in the enum"
    return True, ""


def norm_unit(u):
    """15 minutes, quarter-hour unit and 15-minute unit are the same unit."""
    if not u:
        return None
    s = re.sub(r"[^a-z0-9]+", " ", u.lower()).strip()
    if "15" in s and "min" in s:
        return "15min"
    if "quarter" in s and "hour" in s:
        return "15min"
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    c = psycopg2.connect(DB)
    c.autocommit = True
    cur = c.cursor()
    cur.execute("""select distinct s from (select unnest(general_rule) s
                     from service_line.line_code where general_rule is not null) t
                   order by s""")
    sentences = [r[0] for r in cur.fetchall()]
    if a.limit:
        sentences = sentences[:a.limit]

    print(f"sentences: {len(sentences)}  (hand-read table holds "
          f"{len(READING)} accepted + {len(REFUSED)} refused)\n")

    agree = disagree = errors = 0
    admit_match = 0
    field_hits = {k: 0 for k in ("limit_type", "amount", "unit_definition", "period", "per_whom", "unlimited")}
    field_seen = dict(field_hits)
    rows = []

    for i, s in enumerate(sentences, 1):
        got = ask(s)
        if got.get("_error"):
            errors += 1
            print(f"[{i}/{len(sentences)}] ERROR  {got['_error']}")
            continue
        ok, why = admissible(got)
        exp = READING.get(s)
        exp_admissible = exp is not None

        # Did the machine make the same ACCEPT / REFUSE call as the hand?
        if ok == exp_admissible:
            admit_match += 1

        status = "ok" if ok else "refused"
        if not exp_admissible:
            # Hand refused it. The machine agreeing to refuse is the win here.
            same = (not ok)
            rows.append((s, status, "REFUSED (hand)", same, why))
            agree += same
            disagree += (not same)
            print(f"[{i}/{len(sentences)}] {'MATCH ' if same else 'DIFFER'} "
                  f"machine={status}, hand=refused" + (f" · {why}" if why else ""))
            continue

        e_type, e_amount, e_unit, e_period, e_whom = exp
        e_unlimited = (e_amount == "UNLIMITED")
        checks = {
            "limit_type": got.get("limit_type") == e_type,
            "amount": (got.get("amount") is None) if e_unlimited
                      else (got.get("amount") is not None and float(got["amount"]) == float(e_amount)),
            "unit_definition": norm_unit(got.get("unit_definition")) == norm_unit(e_unit),
            "period": (got.get("period") or None) == e_period,
            "per_whom": (got.get("per_whom") or None) == e_whom,
            "unlimited": bool(got.get("unlimited")) == e_unlimited,
        }
        for k, v in checks.items():
            field_seen[k] += 1
            field_hits[k] += bool(v)
        same = ok and all(checks.values())
        agree += same
        disagree += (not same)
        bad = [k for k, v in checks.items() if not v]
        rows.append((s, status, exp, same, ", ".join(bad)))
        print(f"[{i}/{len(sentences)}] {'MATCH ' if same else 'DIFFER'}"
              + (f" · {', '.join(bad)}" if bad else "")
              + ("" if ok else f" · machine refused: {why}"))
        if a.verbose and not same:
            print(f"     sentence: {s[:110]}")
            print(f"     hand:    {exp}")
            print(f"     machine: type={got.get('limit_type')} amount={got.get('amount')} "
                  f"unit={got.get('unit_definition')!r} period={got.get('period')} "
                  f"whom={got.get('per_whom')} unlimited={got.get('unlimited')}")

    n = len(sentences) - errors
    if errors:
        print(f"\n{errors} sentence(s) never got a usable response and are "
              f"excluded from the grade rather than counted as disagreement.")
    print(f"\n{'='*66}")
    print(f"full-reading agreement   {agree}/{n}  ({agree/n:.0%})")
    print(f"accept/refuse agreement  {admit_match}/{n}  ({admit_match/n:.0%})")
    print("\nper field, on the sentences the hand accepted:")
    for k in field_hits:
        if field_seen[k]:
            print(f"  {k:<18}{field_hits[k]:>3}/{field_seen[k]:<3} ({field_hits[k]/field_seen[k]:.0%})")
    print("\nNOT a blind eval: the same author wrote the hand table and this prompt.")
    print("A fair grade needs a fee schedule nobody has hand-read.")


if __name__ == "__main__":
    main()
