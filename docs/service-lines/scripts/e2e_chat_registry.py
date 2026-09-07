"""Six real questions through live chat, graded against the registry.

WHY THIS EXISTS, and it is the whole lesson of 2026-09-06:

The endpoint suite (mobius-payor/tests/test_service_line_api.py, 31 checks) was
green the entire time the product was broken. It proved the API correct and could
not see any of this:

  * every tool raised NameError on a constant that was never imported, and the
    error was swallowed into "internal system error"
  * `sources` was empty on every call because the dispatch read `note`, a field
    the envelope no longer has
  * the model dropped a material caveat in final synthesis and asserted a limit
    the registry deliberately refuses to compute
  * the model dropped one of TWO caps and reported only the larger — a billing
    error, from an answer that reads perfectly
  * a caveat written as a model instruction was printed verbatim at a provider
  * "partial hospitalisation" returned "not a recognized service line" because
    one letter, s versus z, missed a bare ILIKE

None of those are visible at the API layer. All six were found by asking a
question the way a person asks it.

So this grades the ANSWER, not the endpoint. Each case states what must be true
of the prose, and — as importantly — what must NOT appear. A run takes a few
minutes because chat is slow; that is the price of testing the thing we ship.

    python3 e2e_chat_registry.py [--only 1,5] [--verbose]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
import uuid

CHAT = "https://mobius-chat-ortabkknqa-uc.a.run.app"


def norm(s):
    """Markdown bold used to survive as a double space, so "**4** different"
    never matched "4 different" and a correct answer graded as a failure."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())).strip()


# Each case: what the registry holds, what the answer must contain, and what it
# must not. `forbid` is the half that catches the dangerous failures — a wrong
# answer usually reads better than a right one.
CASES = [
    {
        "id": "1", "name": "multi-cap — both caps must appear",
        "q": "How many units of H2019 with modifier HR can we bill per year for Florida Medicaid?",
        "truth": "104 units of 15 min per state fiscal year per recipient, AND 4 units per day",
        "require": [["104"], ["4 unit", "four unit", "daily", "per day"], ["15 minute", "quarter"]],
        "forbid": ["208"],
        "why_forbid": "208 is the two service lines summed. A provider billing 104 units in a "
                      "day because the daily cap was dropped is the real-world failure.",
    },
    {
        "id": "2", "name": "bare code is not one service",
        "q": "What is HCPCS code H0031?",
        "truth": "four billable services at (none), HN, HO, TS",
        "require": [["four", "4 different", "4 billable"], ["modifier"]],
        "forbid": ["alcohol and", "drug services", "per 15 minutes"],
        "why_forbid": "Chat answered 'Alcohol and/or drug services; behavioral counseling, "
                      "individual, per 15 minutes' with a [1] citation. The official HCPCS "
                      "descriptor is 'Mental health assessment, by non-physician' and all "
                      "four registry definitions are mental-health assessments. Wrong "
                      "against every source we hold, and it flips MH to SUD.",
    },
    {
        "id": "3", "name": "coverage",
        "q": "Is H2017 covered by Florida Medicaid?",
        "truth": "covered under the Community Behavioral Health benefit",
        "require": [["covered"], ["community behavioral health", "behavioral health"]],
        "forbid": ["not covered", "is not covered"],
        "why_forbid": "H2017 is covered; a 'not covered' answer is the exact confusion "
                      "between 'we hold nothing' and 'the answer is no'.",
    },
    {
        "id": "4", "name": "decline well — the common path",
        "q": "Do you do partial hospitalisation?",
        "truth": "FL Medicaid covers PHP; Mobius does not serve it; we hold no documents",
        "require": [["covers", "covered"], ["not serve", "does not serve", "do not serve"]],
        "forbid": ["not found", "not a recognized", "not recognized", "does not exist"],
        "why_forbid": "This is 24 of 31 lines. Saying the service does not exist, when we "
                      "deliberately decline a service Medicaid covers, is the worst answer "
                      "we can give — and it is what shipped before the spelling fix.",
    },
    {
        "id": "5", "name": "unit undefined — must refuse to quantify",
        "q": "How many units of T2023 with modifier HA can be billed per month?",
        "truth": "the schedule says 'Maximum 1 unit per month' and never defines a unit",
        "require": [["not define", "does not define", "never define", "not specified",
             "not provided", "cannot be determined"]],
        "forbid": ["do not infer", "give the raw wording", "you must", "synthesis requirement"],
        "why_forbid": "A model-facing directive rendered at a provider. The caveat's "
                      "`directive` field is for the model; `text` is for the user.",
    },
    {
        "id": "6", "name": "sourced requirements only",
        "q": "For the Florida Medicaid Behavioral Health Assessment Services line (bh_assessment), what does the standard require in order to bill?",
        "truth": "5 of 7 sourced; place_of_service and prior_authorization are placeholders. The question names the line because an ambiguous one made chat ask which of bh_assessment/cbha was meant — correct behaviour, wrongly graded as a failure.",
        "require": [["documentation", "document"], ["medical", "necessity", "qualification"]],
        "forbid": ["never quote", "unsourced row as policy",
                   "stated in its coverage policy; not yet"],
        "why_forbid": "Two failures. Quoting a placeholder as policy launders a gap "
                      "into a requirement. And 'Never quote the statement of an unsourced "
                      "row as policy' is the caveat's `directive` — a model instruction "
                      "reproduced at a provider, the same leak as before in a new field.",
    },
]


def ask(q, tries=2):
    for _ in range(tries):
        cid = str(uuid.uuid4())
        body = json.dumps({"message": q, "correlation_id": cid,
                           "use_react": True, "chat_mode": "copilot"}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(
                CHAT + "/chat", data=body,
                headers={"Content-Type": "application/json"}), timeout=60)
        except Exception as e:
            return {"error": f"post failed: {e}"}
        for _ in range(70):
            time.sleep(8)
            try:
                d = json.load(urllib.request.urlopen(
                    f"{CHAT}/chat/response/{cid}", timeout=45))
            except Exception:
                continue
            if d.get("message") and d.get("status") not in ("processing", "pending"):
                return {"message": d.get("message") or ""}
    return {"error": "timed out"}


def direct_answer(raw):
    """The card is JSON; the graded surface is what the user actually reads."""
    m = re.search(r'"direct_answer":\s*"(.*?)(?<!\\)"', raw, re.S)
    return (m.group(1) if m else raw).replace("\\n", " ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated case ids")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    cases = [c for c in CASES if not a.only or c["id"] in a.only.split(",")]

    passed = failed = 0
    for c in cases:
        print(f"\n[{c['id']}] {c['name']}\n    Q: {c['q']}", flush=True)
        r = ask(c["q"])
        if r.get("error"):
            print(f"    FAIL — {r['error']}")
            failed += 1
            continue
        ans = direct_answer(r["message"])
        n = norm(ans)

        missing = [grp for grp in c["require"] if not any(norm(x) in n for x in grp)]
        present = [f for f in c["forbid"] if norm(f) in n]

        if a.verbose or missing or present:
            print(f"    A: {ans[:400]}")
        if missing:
            print(f"    FAIL — missing: {['/'.join(g) for g in missing]}")
            print(f"           registry holds: {c['truth']}")
        if present:
            print(f"    FAIL — contains forbidden: {present}")
            print(f"           {c['why_forbid']}")
        if not missing and not present:
            print("    PASS")
            passed += 1
        else:
            failed += 1

    print(f"\n{'=' * 66}\n{passed} passed, {failed} failed of {len(cases)}")
    print("A green endpoint suite does not mean the product answers correctly.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
