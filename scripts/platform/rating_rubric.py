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

# Thresholds. Stated as constants so they can be argued with rather than
# rediscovered by reading branches. Calibrated against the live corpus
# 2026-09-09 — not derived from a standard, and that is worth knowing.
RED_VOLUME  = 8       # open defects on one node: past this, coverage stops excusing it
LOC_AMBER   = 800     # a module one person can still hold in their head
LOC_RED     = 2500    # react_loop is 6,200 — not reviewable, not isolable
SWALLOW_RED = 10      # log-and-continue handlers: failures the caller cannot see

# DECLINED belongs here: a fix the owner considered and rejected on cost is a
# DECISION, not an outstanding defect. Leaving it open counted a made decision
# against a node's readiness forever, and would have made `state_load` un-greenable
# on an item Ananth had explicitly closed. The marker keeps it visible in the log —
# it is stamped, not deleted — while stopping it from scoring.
CLOSED_MARKERS = ("CLOSED", "FIXED", "RESOLVED", "WITHDRAWN", "RETIRED", "DECLINED")
_CALLED = ("PERIPHERAL", "TAGGED-UNVERIFIED", "GUARDED")
_UNCALLED = ("ABSENT", "IMPORTED-NOT-CALLED")


# A finding recorded on a node is not necessarily a DEFECT OF that node. During the
# refactor I appended everything to whichever node I was working in, so `tool_manifest`
# accumulated my own generator bugs, the payor seat's matcher, appeals' guard, the
# roster seat's display_name and a payor repo's test scripts — 32 "open" on a node
# whose real count was 18. That made it un-greenable for reasons that had nothing to do
# with it, and made the number meaningless. Ananth, 2026-09-10: "0 green after 1 days
# of work is embarassing" — part of that was this misfiling.
#
# The OWNER(...) prefix already carries the answer. A node's PRODUCTION READINESS is
# scored on defects owned by the module's own team, or unowned. Everything else is
# still TRACKED on the node — it is not deleted, hidden, or moved — but it is counted
# under `tracked_elsewhere` and named, so the distinction is visible rather than
# silently applied. Re-attributing to make a badge green would be metric-gaming; NOT
# re-attributing makes the badge measure the wrong thing.
_OWNER_RE = __import__("re").compile(r"^\s*OWNER\(([^)]*)\)")
_OWN_NODE = ("chat", "chat-master", "")          # the module's own team


def owner_of(text):
    m = _OWNER_RE.match(text or "")
    return (m.group(1).strip().lower() if m else "")


def is_own_defect(text):
    o = owner_of(text)
    return any(o.startswith(x) for x in _OWN_NODE if x) or o == ""


# A closure marker is recognised ANYWHERE in the text, but only as a STAMP — at the
# start of a sentence, in caps. The first version scanned only text[:400] to stop a
# passing mention of another node's fix from closing this one; but stamps are appended
# at the END, so two of my own rules contradicted and two genuinely-closed state_load
# findings kept counting as open. Anchoring on sentence-start caps satisfies both: a
# mid-sentence "fixed" in prose does not close anything, a stamp anywhere does.
_STAMP_RE = __import__("re").compile(
    r"(?:^|[.;—)]\s*|\s)(CLOSED|FIXED|RESOLVED|WITHDRAWN|RETIRED|DECLINED)\b(?=[ ,:.]|$)")


def is_closed(text):
    return bool(_STAMP_RE.search(text or ""))


def open_bugs(findings, own_only=True):
    """`bad` findings not stamped closed. Only the head of the text is scanned:
    a closure stamp is appended at the front of the tail, and a later mention of
    another node's fix must not silently close this one."""
    n = 0
    for kind, text in findings or []:
        if kind != "bad":
            continue
        if is_closed(text):
            continue
        if own_only and not is_own_defect(text):
            continue
        n += 1
    return n


def tracked_elsewhere(findings):
    """Open findings recorded here but owned by another seat. Named, not hidden."""
    out = []
    for kind, text in findings or []:
        if kind != "bad" or is_closed(text):
            continue
        if not is_own_defect(text):
            out.append(owner_of(text))
    return out


_ORDER = {"green": 0, "amber": 1, "red": 2}


def dimensions(*, findings, coverage, signals):
    """Score each readiness dimension independently. Returns [(dim, level, why)].

    THE OVERALL RATING IS THE WORST DIMENSION, never an average. A module that
    is well tested and well factored but swallows every failure is not
    two-thirds ready — it is unready, for a specific reason a reader can act on.
    Averaging would let a strong dimension hide a disqualifying one, which is
    the arithmetic version of the defect this program exists to find.
    """
    sg = signals or {}
    n = open_bugs(findings)
    others = tracked_elsewhere(findings)
    cov = coverage or "unknown"
    d = []

    # 1. FUNCTIONALITY — known open defects against this node.
    if n >= RED_VOLUME:
        d.append(("functionality", "red", f"{n} open defects"
                  + (f" (+{len(others)} tracked for other seats)" if others else "")))
    elif n:
        d.append(("functionality", "amber", f"{n} open"
                  + (f" (+{len(others)} tracked for other seats)" if others else "")))
    else:
        d.append(("functionality", "green",
                  "no open defects owned here"
                  + (f" ({len(others)} tracked for other seats)" if others else "")))

    # 2. TESTABILITY — Eval's Layer 1, plus the mutation ledger for GUARDED.
    if cov in ("ABSENT", "IMPORTED-NOT-CALLED"):
        d.append(("testability", "red", f"no test CALLS it ({cov})"))
    elif cov == "GUARDED":
        d.append(("testability", "green", "guarantee mutation-verified"))
    elif cov in _CALLED:
        d.append(("testability", "amber", f"called, guarantee unproven ({cov})"))
    else:
        d.append(("testability", "amber", "coverage unknown"))

    if sg.get("unmapped"):
        d.append(("modularity", "amber", "no single module — nothing to measure"))
        return d
    if sg.get("missing"):
        return d

    # 3. ERROR HANDLING — swallows are failures the caller cannot see.
    sw, bare, hand = sg.get("swallow", 0), sg.get("bare_except", 0), sg.get("except_handlers", 0)
    if bare:
        d.append(("error_handling", "red", f"{bare} bare except:"))
    elif sw >= SWALLOW_RED:
        d.append(("error_handling", "red", f"{sw} of {hand} handlers log-and-continue"))
    elif sw:
        d.append(("error_handling", "amber", f"{sw} of {hand} handlers swallow"))
    else:
        d.append(("error_handling", "green",
                  f"{hand} handlers, none swallow" if hand else "no failure paths"))

    # 4. MODULARITY — size is the one honest proxy available.
    loc = sg.get("loc", 0)
    if loc >= LOC_RED:
        d.append(("modularity", "red", f"{loc} lines — not reviewable in one pass"))
    elif loc >= LOC_AMBER:
        d.append(("modularity", "amber", f"{loc} lines"))
    else:
        d.append(("modularity", "green", f"{loc} lines"))

    # 5. OBSERVABILITY — log lines and structured telemetry are NOT the same
    # evidence and are never summed. Logs make a module diagnosable in hindsight
    # by a human with grep; a span/emit/record makes it OPERABLE — queryable,
    # alertable, joinable to a turn. A module with neither cannot be reasoned
    # about at all; one with only logs is the majority case here (24 of 31) and
    # is honestly amber, not red.
    tel, log = sg.get("telemetry_sites", 0), sg.get("log_sites", 0)
    if not tel and not log:
        d.append(("observability", "red", "no logs and no telemetry — cannot be operated"))
    elif not tel:
        d.append(("observability", "amber",
                  f"{log} log sites, NO structured telemetry — diagnosable, not operable"))
    elif tel < 3:
        d.append(("observability", "amber", f"{tel} telemetry sites, {log} logs"))
    else:
        d.append(("observability", "green", f"{tel} telemetry sites, {log} logs"))

    # 6. LATENCY — deliberately UNRATED. turn_spans carries per-node p50 but the
    # join is not built, and Eval's ruling is explicit: wall-time needs a >=5-run
    # noise floor, p50/p95 never mean. Guessing a level here would be exactly the
    # "counts without their target" error. Stated as a gap, not scored.
    if sg.get("async_no_timeout"):
        d.append(("latency", "red",
                  f"{sg['async_no_timeout']} outbound calls with no timeout — "
                  "an un-bounded external wait cannot be attributed"))
    return d


def rate(*, findings, coverage, deleted=False, signals=None):
    """Return (rating, why). `why` is rendered, so it must read as a reason."""
    if deleted:
        return "removed", "node deleted — a rating is a judgement about live code"
    dims = dimensions(findings=findings, coverage=coverage, signals=signals)
    if not dims:
        return "amber", "no evidence available — unrated rather than assumed"
    worst = max(_ORDER[l] for _, l, _ in dims)
    level = [k for k, v in _ORDER.items() if v == worst][0]
    drivers = [f"{d}: {w}" for d, l, w in dims if _ORDER[l] == worst]
    ok = [d for d, l, _ in dims if _ORDER[l] < worst]
    why = " · ".join(drivers)
    if ok:
        why += f"  (ok: {', '.join(ok)})"
    return level, why
