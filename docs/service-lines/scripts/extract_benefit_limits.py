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
  2. The prompt is never shown the expected answer. It receives the sentences,
     the enums and the completeness rule — nothing else.

The unit of work is ONE BILLABLE SERVICE, not one sentence. Grading the
per-sentence version showed that was the design error behind its worst
disagreement: on H0032 the model read "one treatment plan per provider"
literally, because the sentence capping treatment plans "per recipient" was in a
different call. Sentences on the same (code, modifier) constrain each other and
have to be read together.

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

PROMPT = """You are turning a state Medicaid fee schedule's service-limit text into
structured limits for ONE billable service. Read ONLY what is given. Do not use
outside knowledge of Medicaid, and do not complete anything left unsaid.

SERVICE: {code}{mod}

The schedule states the following about it. They are given together on purpose:
a later sentence often constrains an earlier one, and a sentence read alone can
mean something the pair does not.

{sentences}

One service may carry SEVERAL limits on different axes — commonly a daily cap
and an annual cap. Return every limit stated, not just the largest.

Return ONLY JSON:
{{
  "limits": [
    {{
      "from_sentence": "the sentence this limit came from, first 60 chars",
      "limit_type": one of {limit_types}, or null if unlimited,
      "amount": number, or null if no numeric cap is stated,
      "unit_definition": "what ONE of that thing is, in the text's own terms", or null,
      "period": one of {periods}, or null,
      "per_whom": one of {per_whom}, or null,
      "unlimited": true only if the text affirmatively says there is no numeric cap
    }}
  ],
  "not_limits": [
    {{"sentence": "first 60 chars", "reason": "why this states no usable limit"}}
  ]
}}

Rules, applied strictly:
- A number with no stated unit is INCOMPLETE. If the text says "1 unit" and never
  says what a unit is, put it in not_limits — do not infer that a unit is a
  month, a visit, or anything else.
- "as medically necessary" is a real answer of NO numeric cap: amount null,
  unlimited true, limit_type null. Nothing is being counted.
- period is the window the cap applies over. "per state fiscal year" is
  state_fiscal_year; "daily" is day; "per month" is month.
- per_whom is WHOSE allowance is capped, and only if the text says. "per
  recipient" is recipient. If the text does not say, use null — do not guess.
- USE THE SENTENCES AGAINST EACH OTHER. If one says a thing is capped "per
  provider" and another caps the same thing "per recipient", the first is a
  per-recipient-per-provider cap, not a cap on the provider's whole panel.
- limit_type: prefer the coarse category over inventing a word. A billable
  service occurrence is "encounters". A timed increment is "units". A
  diagnostic write-up is "evaluations". Never return a word outside the list.
"""



def ask(code: str, mod: str | None, sentences: list[str], tries: int = 3) -> dict:
    """One call per billable service, not per sentence.

    Grading the per-sentence version showed the unit of work was wrong: on H0032
    the model read "one treatment plan per provider" literally, because the
    paired sentence capping treatment plans "per recipient" was never in the
    prompt. Neither reading is available from one sentence alone.
    """
    numbered = "\n".join(f"  {i}. {t}" for i, t in enumerate(sentences, 1))
    prompt = PROMPT.format(code=code, mod=f" with modifier {mod}" if mod else " (no modifier)",
                           sentences=numbered, limit_types=LIMIT_TYPES,
                           periods=PERIODS, per_whom=PER_WHOM)
    for attempt in range(tries):
        try:
            raw, usage = generate_sync(prompt, stage="parser", max_tokens=1500, parser=True)
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
    """Compare what the unit IS, not how it was worded.

    "15 minutes", "quarter-hour unit" and "15-minute unit" name one thing. So do
    "one biopsychosocial evaluation" and "biopsychosocial evaluation" — a leading
    article is grammar, not a different unit, and scoring it as a disagreement
    flatters nothing and hides the real ones.
    """
    if not u:
        return None
    s = re.sub(r"[^a-z0-9]+", " ", u.lower()).strip()
    if ("15" in s and "min" in s) or ("quarter" in s and "hour" in s):
        return "15min"
    s = re.sub(r"^(one|a|an|the)\s+", "", s)
    return s


def canon(t):
    """A reading, comparable regardless of who produced it."""
    ltype, amount, unit, period, whom = t
    unlimited = amount == "UNLIMITED"
    return (None if unlimited else ltype,
            None if unlimited else float(amount),
            norm_unit(unit), period, whom, unlimited)


def canon_machine(d):
    unlimited = bool(d.get("unlimited"))
    amt = d.get("amount")
    return (None if unlimited else (d.get("limit_type") or None),
            None if unlimited else (float(amt) if amt is not None else None),
            norm_unit(d.get("unit_definition")),
            d.get("period") or None,
            d.get("per_whom") or None,
            unlimited)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    c = psycopg2.connect(DB)
    c.autocommit = True
    cur = c.cursor()
    cur.execute("""select code, qualifier, general_rule
                     from service_line.line_code
                    where general_rule is not null and general_rule <> '{}'
                    order by code, qualifier""")

    # Many bindings share an identical sentence set (H0032 and T1007 carry the
    # same pair). Group by the set so the grade counts distinct problems, not
    # duplicated rows.
    groups: dict[tuple, dict] = {}
    for code, qual, rules in cur.fetchall():
        key = (code, qual or None, tuple(rules))
        groups.setdefault(key, {"code": code, "mod": qual or None,
                                "sentences": list(rules)})
    work = list(groups.values())
    if a.limit:
        work = work[:a.limit]

    print(f"billable services: {len(work)}  "
          f"(hand table holds {len(READING)} accepted + {len(REFUSED)} refused sentences)\n")

    exact = partial = wrong = errors = 0
    refuse_right = refuse_seen = 0
    limits_expected = limits_matched = 0

    for i, g in enumerate(work, 1):
        got = ask(g["code"], g["mod"], g["sentences"])
        label = f"{g['code']} {g['mod'] or ''}".strip()
        if got.get("_error"):
            errors += 1
            print(f"[{i}/{len(work)}] ERROR  {label}: {got['_error']}")
            continue

        expected, hand_refused = [], []
        for sent in g["sentences"]:
            if sent in READING:
                expected.append(canon(READING[sent]))
            else:
                hand_refused.append(sent)

        machine = []
        for d in (got.get("limits") or []):
            ok, why = admissible({**d, "states_a_limit": True})
            if ok:
                machine.append(canon_machine(d))
        # A sentence the hand refused should land in not_limits, not in limits.
        refuse_seen += len(hand_refused)
        n_not = len(got.get("not_limits") or [])
        refuse_right += min(n_not, len(hand_refused))

        limits_expected += len(expected)
        rem = list(machine)
        hit = 0
        for e in expected:
            if e in rem:
                rem.remove(e)
                hit += 1
        limits_matched += hit

        if hit == len(expected) and not rem:
            exact += 1
            verdict = "MATCH "
        elif hit:
            partial += 1
            verdict = "PARTIAL"
        else:
            wrong += 1
            verdict = "MISS  "
        print(f"[{i}/{len(work)}] {verdict} {label:<10} "
              f"{hit}/{len(expected)} limits" + (f", {len(rem)} extra" if rem else ""))
        if a.verbose and (hit != len(expected) or rem):
            for e in expected:
                print(f"     hand:    {e}")
            for m_ in machine:
                print(f"     machine: {m_}")

    n = len(work) - errors
    print(f"\n{'='*66}")
    print(f"services graded          {n}" + (f"  ({errors} errored, excluded)" if errors else ""))
    print(f"  exact                  {exact}/{n}  ({exact/n:.0%})")
    print(f"  partial                {partial}/{n}")
    print(f"  missed entirely        {wrong}/{n}")
    print(f"individual limits        {limits_matched}/{limits_expected}  "
          f"({limits_matched/limits_expected:.0%})")
    if refuse_seen:
        print(f"hand-refused sentences   {refuse_right}/{refuse_seen} also refused by the machine")
    print("\nNOT a blind eval: the same author wrote the hand table and this prompt.")
    print("A fair grade needs a fee schedule nobody has hand-read.")


if __name__ == "__main__":
    main()
