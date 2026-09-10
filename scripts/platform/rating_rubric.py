"""The production-readiness rubric — DERIVED, not typed.

WHY THIS FILE EXISTS. All 37 ratings were hand-typed once (d7075fe, 2026-09-08)
and never re-derived. `state_load` read `red` a day later, after its correctness
defect was fixed, a contract tag was written, and Eval had independently audited
it GUARDED. Ananth found it by asking "why is state_load still red", then asked
the better question: "isnt that what the signoff were for".

It wasn't. The six seats ratified the PLAN — attribution, phase order, gate
invariants, corpus design. Nobody was ever asked to sign "state_load is red".
A SIGN-OFF IS A ONE-TIME RATIFICATION OF A PLAN; A RATING IS A RECURRING
JUDGEMENT ABOUT CURRENT STATE, and a one-time gate cannot keep a recurring
judgement fresh. So the rating is now computed from evidence on every refresh.
A stale rating is no longer possible; only a wrong RUBRIC is, and the rubric is
in one place where it can be argued with.

THE INPUTS, all already generated:
  open_bugs — `bad` findings whose text is not stamped CLOSED/FIXED/RESOLVED/
              WITHDRAWN/RETIRED. Counted from the log, never asserted.
  coverage  — Eval's Layer-1 enum, plus GUARDED from the mutation ledger.
  deleted   — the tombstone set.

THE RULES, in order. First match wins.

  removed  the node is deleted. A rating is a judgement about live code; leaving
           green/amber/red on a module that no longer exists is worse than
           leaving its description, because a badge is scanned and prose is
           weighed. (Chat Master caught exactly this on credentialing_envelope.)

  red      EITHER open bugs AND no test CALLS the module (ABSENT /
           IMPORTED-NOT-CALLED) — known defects whose regression would be
           SILENT, which is this program's entire subject matter —
           OR open_bugs >= RED_VOLUME. A module carrying that many open
           defects is not "known issues, under control" whatever its coverage.

  amber    open bugs, and the module is at least exercised by a test that calls
           it. Known, sequenced, observable.
           ALSO: zero open bugs but coverage is ABSENT or unknown. "No known
           defects and nothing tests it" is NOT evidence of health — it is
           green-by-construction, the shape that hid tool_failed and the
           appeals outage. Absence of evidence does not earn a green badge.

  green    zero open bugs AND a test calls the module (PERIPHERAL or better).

WHAT THIS RUBRIC DELIBERATELY DOES NOT DO. It does not weigh severity: a
data-integrity defect and a naming nit both count 1. That is a real limitation,
stated rather than hidden — severity is not machine-readable in the log today.
The honest consequence is that `red` means "many open defects, or silent ones",
NOT "the worst module". If severity is ever encoded, this is the place to use it.

OVERRIDES exist and cost something: set `rating_override=` plus
`rating_override_reason=` in the catalogue. The reason is rendered next to the
badge, so an override is a visible judgement rather than a quiet correction.
"""

RED_VOLUME = 8
CLOSED_MARKERS = ("CLOSED", "FIXED", "RESOLVED", "WITHDRAWN", "RETIRED")
_CALLED = ("PERIPHERAL", "TAGGED-UNVERIFIED", "GUARDED")
_UNCALLED = ("ABSENT", "IMPORTED-NOT-CALLED")


def open_bugs(findings):
    """`bad` findings not stamped closed. Only the head of the text is scanned:
    a closure stamp is appended at the front of the tail, and a later mention of
    another node's fix must not silently close this one."""
    n = 0
    for kind, text in findings or []:
        if kind != "bad":
            continue
        if not any(c in text[:400] for c in CLOSED_MARKERS):
            n += 1
    return n


def rate(*, findings, coverage, deleted=False):
    """Return (rating, why). `why` is rendered, so it must read as a reason."""
    if deleted:
        return "removed", "node deleted — a rating is a judgement about live code"
    n = open_bugs(findings)
    cov = coverage or "unknown"
    if n and cov in _UNCALLED:
        return "red", f"{n} open · no test CALLS it ({cov}) — a regression here is silent"
    if n >= RED_VOLUME:
        return "red", f"{n} open defects — volume, not coverage"
    if n:
        return "amber", f"{n} open · exercised ({cov})"
    if cov in _CALLED:
        return "green", f"0 open · exercised ({cov})"
    return "amber", f"0 open but no test CALLS it ({cov}) — absence of evidence is not health"
