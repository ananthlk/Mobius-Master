#!/usr/bin/env python3
"""Per-node production-readiness SIGNALS, measured from source on every refresh.

WHY THIS FILE EXISTS. gen_chat_dev.py read its signals from a hardcoded path
inside a *session scratchpad*:

    sig_path = "/private/tmp/claude-502/.../scratchpad/readiness.json"
    sigs = json.load(open(sig_path)) if os.path.exists(sig_path) else {}

That directory belonged to a session that ended. The `if os.path.exists` made
the absence silent, so every node got `{}` — and the page rendered
"0 except · 0 log-and-continue · 0 emits" for all 38 nodes AS THOUGH MEASURED.
A swallowed absence presented as data, in the tool built to find swallowed
absences. Signals are now derived from the real files, and a node whose file is
missing is reported as `missing`, never as zero.

WHAT IS COUNTED, and what each one is evidence OF:

  loc              modularity. A 6,200-line module cannot be reasoned about,
                   tested in isolation, or changed safely by one person.
  except_handlers  how much of the module is failure paths at all.
  swallow          `except: ... log/pass/continue` — a failure the caller
                   cannot see. THE central defect class of this program.
  bare_except      `except:` with no type. Catches SystemExit/KeyboardInterrupt
                   and hides real bugs.
  reraise          handlers that `raise` — the opposite of a swallow, counted so
                   a module is not punished for having many handlers that are
                   honest about failing.
  log_sites        logger.<level>( — greppable after the fact by a human.
  telemetry_sites  span/emit/record/track — a STRUCTURED signal something can
                   query, alert on, or join to a turn. Counted separately from
                   log_sites and never summed: a module with only log lines is
                   diagnosable in hindsight, not operable. This program's whole
                   subject is the difference between the two.
  todos            TODO/FIXME/XXX/HACK — declared incompleteness.
  async_no_timeout outbound calls (httpx/urlopen/requests) with no timeout=.
                   An un-bounded external wait is indistinguishable from our own
                   work and cannot be attributed. Eval's ruling, mechanised.

Deliberately NOT counted, because it would be guessed rather than measured:
functional completeness (no machine-readable spec to compare against) and
per-node latency (turn_spans has it, but the join is not built yet — stated as
a gap rather than approximated).
"""
import ast, json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CHAT = os.path.join(ROOT, "mobius-chat")

_SWALLOW = re.compile(r"^\s*(logger\.|log\.|print\(|pass\b|continue\b|return\b)")
# TWO KINDS, counted separately and NOT summed — the distinction is the point.
# `logger.<level>(` is a line a human greps after the fact. A span/emit/record is
# a structured signal something can query, alert on, or join to a turn.
# WHY THIS IS SPLIT: my first version matched only `logger.info(` and nothing
# else, so a module full of `logger.warning` read as emits=0 and the rubric said
# "emits nothing — cannot be operated" for NINETEEN nodes, POST /chat and
# state_load among them. A wrong instrument producing confident wrong verdicts,
# caught by spot-checking one node against grep before shipping. Same class as
# the reachability transitive-closure error and the _APPEALS_BLOCK gate key.
_LOG  = re.compile(r"\blogger?\.(debug|info|warning|warn|error|exception|critical)\s*\(")
_TELE = re.compile(r"\b(emit|emit_\w+|record|_rec\w*|span|start_span|track|counter|"
                   r"observe|histogram)\s*\(")
_TODO = re.compile(r"#\s*(TODO|FIXME|XXX|HACK)\b")
_OUTBOUND = re.compile(r"\b(httpx\.(Client|AsyncClient)|urlopen|requests\.(get|post))\s*\(")


def measure(relpath: str) -> dict:
    p = os.path.join(CHAT, relpath)
    if not os.path.exists(p):
        # DELETED is not the same as UNMAPPED is not the same as ZERO. Collapsing
        # them is the defect this whole program keeps finding, so the caller gets
        # the distinction and the rubric refuses to rate on a guess.
        return {"missing": True, "path": relpath}
    src = open(p, encoding="utf-8", errors="replace").read()
    lines = src.splitlines()
    out = {"loc": len(lines), "except_handlers": 0, "swallow": 0, "bare_except": 0,
           "reraise": 0, "log_sites": len(_LOG.findall(src)),
           "telemetry_sites": len(_TELE.findall(src)),
           "todos": len(_TODO.findall(src)), "async_no_timeout": 0, "missing": False}
    for m in _OUTBOUND.finditer(src):
        seg = src[m.end(): m.end() + 220]
        if "timeout" not in seg:
            out["async_no_timeout"] += 1
    try:
        tree = ast.parse(src)
    except SyntaxError:
        out["unparseable"] = True
        return out
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        out["except_handlers"] += 1
        if node.type is None:
            out["bare_except"] += 1
        body_src = "\n".join(lines[node.body[0].lineno - 1: node.body[-1].end_lineno])
        if any(isinstance(n, ast.Raise) for n in ast.walk(node)):
            out["reraise"] += 1
        elif all(_SWALLOW.match(l) or not l.strip()
                 for l in body_src.splitlines() if l.strip()):
            out["swallow"] += 1
    return out


def main(out_path: str) -> None:
    paths = json.load(open(os.path.join(ROOT, "docs", "chat-node-paths.json")))
    sigs = {k: measure(v) for k, v in paths.items()}
    # A node with no single module is UNMAPPED, not measured-as-zero. `clarification`
    # is the live example: the behaviour exists, spread across other modules, so
    # there is nothing to measure and saying "0 swallows" would be a lie.
    sigs["clarification"] = {"unmapped": True}
    json.dump(sigs, open(out_path, "w"), indent=1, sort_keys=True)
    miss = [k for k, v in sigs.items() if v.get("missing")]
    print(f"measured {len(sigs) - len(miss)} nodes"
          + (f" · MISSING FILE: {miss}" if miss else ""))
    tot = lambda f: sum(v.get(f, 0) for v in sigs.values())
    print(f"  swallow {tot('swallow')} · bare_except {tot('bare_except')} · "
          f"reraise {tot('reraise')} · un-timed outbound {tot('async_no_timeout')}")
    print(f"  log sites {tot('log_sites')} · telemetry sites {tot('telemetry_sites')}")
    blind = [k for k, v in sigs.items()
             if not v.get("missing") and not v.get("unmapped")
             and not v.get("telemetry_sites")]
    print(f"  nodes with NO structured telemetry: {len(blind)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         os.path.join(ROOT, "docs", "chat-readiness.json"))
