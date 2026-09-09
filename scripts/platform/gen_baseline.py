"""Freeze the refactor baseline.

Technical Review's open question: "confirm the 2,741-turn set is a frozen
snapshot and not the live table read at two different times." It was not —
every measurement in the findings log used `now() - interval '60 days'`, a
MOVING window. The DB seat independently measured 2,744 against my 2,741,
which is that drift showing up.

This writes the corpus to a committed file: the exact correlation_ids, plus
the per-turn invariant values computed from the persisted thinking_log. From
here on, PRE is this file — not a query — so the population cannot move
between PRE and POST.

Stratified per the DB seat's ruling: context_summary is present on only ~67%
of turns, so a pooled comparison silently over-weights the turns that carry
context.
"""
import json, os, re, sys, hashlib, datetime, psycopg2

OUT = sys.argv[1] if len(sys.argv) > 1 else "docs/chat-refactor-baseline.json"
DSN = os.environ.get("CHAT_BASELINE_DSN") or "postgresql://postgres:MobiusDev123$@127.0.0.1:5433/mobius_chat"
WINDOW_END = sys.argv[2] if len(sys.argv) > 2 else "2026-09-08"

c = psycopg2.connect(DSN); cur = c.cursor()
cur.execute("""
    select correlation_id, thread_id, created_at, thinking_log, context_summary
      from chat_turns
     where created_at >= (%s::date - interval '60 days') and created_at < (%s::date + interval '1 day')
       and thinking_log is not null
     order by created_at, correlation_id
""", (WINDOW_END, WINDOW_END))
rows = cur.fetchall()

turns, strata = [], {"with_context": 0, "no_context": 0}
for cid, tid, ts, tl, ctxsum in rows:
    try:
        items = tl if isinstance(tl, list) else json.loads(tl)
    except Exception:
        items = []
    text, trace = [], None
    for it in (items if isinstance(items, list) else []):
        if isinstance(it, str):
            text.append(it)
        elif isinstance(it, dict):
            d = it.get("data") if isinstance(it.get("data"), dict) else it
            if trace is None and "groundedness_floor_ran" in d:
                trace = d
            for v in d.values():
                if isinstance(v, str):
                    text.append(v)
    blob = "\n".join(text)
    has_ctx = bool((ctxsum or "").strip())
    strata["with_context" if has_ctx else "no_context"] += 1
    turns.append({
        "correlation_id": cid,
        "thread_id": tid,
        "stratum": "with_context" if has_ctx else "no_context",
        "mode": (trace or {}).get("mode"),
        # I2 — did this turn reach the integrator
        "integrator_ran": "Composing answer" in blob,
        # I4 — the governor's arithmetic
        "rounds_used": (trace or {}).get("rounds_used"),
        "max_rounds": (trace or {}).get("max_rounds"),
        # I5 — the mandatory groundedness floor
        "floor_ran": bool((trace or {}).get("groundedness_floor_ran")),
        "floor_passed": (trace or {}).get("groundedness_passed"),
        "final_directive": (trace or {}).get("final_directive"),
        "unfinished_reason": (trace or {}).get("unfinished_reason"),
    })

def tally(key, pred=None):
    out = {}
    for t in turns:
        v = pred(t) if pred else t.get(key)
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items(), key=lambda x: -x[1]))

def by_stratum(pred):
    return {s: sum(1 for t in turns if t["stratum"] == s and pred(t)) for s in strata}

ids = "\n".join(t["correlation_id"] for t in turns)
doc = {
    "frozen_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "window": {"end": WINDOW_END, "days": 60},
    "corpus_fingerprint": hashlib.sha256(ids.encode()).hexdigest()[:16],
    "n_turns": len(turns),
    "what_this_is": (
        "A DIFFERENTIAL gate, not a replay of production. Per the DB seat's ruling: "
        "chat_state holds one row per thread, mutated in place with no history, so the "
        "state a turn actually ran with is NOT recoverable. Both PRE and POST get the "
        "same reconstructed input, so any delta is attributable to the code change — "
        "which is what a refactor gate needs. It does NOT reproduce historical behaviour "
        "and must not be described as doing so."
    ),
    "strata": strata,
    "baseline": {
        "I2_integrator_ran": {
            "total": sum(1 for t in turns if t["integrator_ran"]),
            "bypassed": sum(1 for t in turns if not t["integrator_ran"]),
            "by_stratum_bypassed": by_stratum(lambda t: not t["integrator_ran"]),
        },
        "I4_rounds": {
            "by_mode_max_rounds": tally(None, lambda t: f"{t['mode']}:{t['max_rounds']}"),
            "extensions_granted": sum(
                1 for t in turns
                if isinstance(t["max_rounds"], int)
                and t["max_rounds"] > {"quick": 2, "copilot": 3, "agentic": 10, "task": 3}.get(t["mode"], 99)
            ),
        },
        "I5_floor": {
            "ran": sum(1 for t in turns if t["floor_ran"]),
            "skipped": sum(1 for t in turns if not t["floor_ran"]),
            "by_mode_ran": tally(None, lambda t: f"{t['mode']}:{'ran' if t['floor_ran'] else 'skip'}"),
            "by_stratum_ran": by_stratum(lambda t: t["floor_ran"]),
            "passed": tally("floor_passed"),
        },
        "final_directive": tally("final_directive"),
        "unfinished_reason": tally("unfinished_reason"),
        "modes": tally("mode"),
    },
    "turns": turns,
}
open(OUT, "w").write(json.dumps(doc, indent=1, default=str))
print(f"frozen {len(turns)} turns · fingerprint {doc['corpus_fingerprint']} -> {OUT}")
print(f"  strata           {strata}")
print(f"  I2 bypassed      {doc['baseline']['I2_integrator_ran']['bypassed']}"
      f"  by stratum {doc['baseline']['I2_integrator_ran']['by_stratum_bypassed']}")
print(f"  I5 ran/skipped   {doc['baseline']['I5_floor']['ran']}/{doc['baseline']['I5_floor']['skipped']}"
      f"  by stratum ran {doc['baseline']['I5_floor']['by_stratum_ran']}")
print(f"  I4 extensions    {doc['baseline']['I4_rounds']['extensions_granted']}")
