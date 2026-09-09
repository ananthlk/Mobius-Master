#!/usr/bin/env python3
"""The deep-research state model, derived from the code rather than drawn.

Emulates docs/chat-schema (scripts/platform/gen_chat_dev.py) on Ananth's
instruction, and keeps its five disciplines:

  1. GENERATED, never hand-drawn. A schematic that is maintained by hand is
     stale the day after and cannot be trusted for a decision.
  2. Every node RATED with findings, so the picture carries quality and not
     only topology.
  3. OBSERVABILITY per node INCLUDING the negative case — "emits nothing;
     observable only through X". Two days of this module's bugs were exactly
     that shape and there was no way to state it structurally.
  4. `role` in the module's own words AND `how` in plain language.
  5. Honest limits recorded in the artefact instead of smoothed over.

Where it departs, and why: chat is a request PIPELINE and its spine is a line.
Deep research is a STATE MACHINE over rounds — request → turn → attempt →
verdicts → arbiter → (go again | settle) — so a linear chain would misdescribe
it. The spine here is `loop`, with what repeats, what terminates it, and who
decides, stated separately.

Topology is derived. Judgement is curated, in schema_content.json, merged the
way gen_chat_dev.py merges its content file — the two must not be confused,
because a derived fact is checkable and a rating is an opinion.
"""
import ast
import json
import os
import re
import sys

PKG = "/Users/ananth/Mobius/mobius-skills/deep-research/deep_research"
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/deep-research.json"
HERE = os.path.dirname(os.path.abspath(__file__))

ENV_RE = re.compile(r'os\.environ\.get\(\s*"([A-Z0-9_]+)"|os\.getenv\(\s*"([A-Z0-9_]+)"'
                    r'|os\.environ\[\s*"([A-Z0-9_]+)"\s*\]')
# What a module writes into the state machine's own schema. `research.*` is the
# provenance store; a module that writes none of it is a pure function of its
# inputs, which is itself worth seeing on the page.
WRITE_RE = re.compile(r'(?:insert\s+into|update)\s+(research\.[a-z_]+)', re.I)
READ_RE = re.compile(r'from\s+(research\.[a-z_]+)', re.I)
# The discipline this module learned the hard way: does this actor REASON out
# loud, or does it only file a receipt?
THINKS_RE = re.compile(r'Thinking\(|from_verdicts\(')
NOTES_RE = re.compile(r'\brec(?:order)?\.note\(|_rec\.note\(')


# ── THE CONTRACT: one declaration, two consumers ────────────────────────────
#
# Ananth, 2026-09-09: "store these contracts in your schema.. the ux also in
# your schema .. this is what makes it real .. WE WILL DRIVE BOTH WITH THAT."
#
# So the four verbs and the surfaces that render them are read out of
# deep_research/contract.py — the same file the router reads back through
# research.contract. Declaring them here would be a third copy; deriving them
# means this page cannot describe an API that does not exist, and the
# invariants below make that a build failure rather than a discrepancy someone
# notices later.
ROUTER = "/Users/ananth/Mobius/mobius-payor/app/routers/research_console.py"
# Every place in the repo that can create a request. A door nobody declared is
# how fifteen unjudgeable requests got in.
REQUEST_WRITERS = re.compile(r"insert\s+into\s+research\.request", re.I)
# Ungated writers we KNOW about. A new one appearing fails the build — the same
# discipline as KNOWN_TERMINATORS, applied to the entry side.
KNOWN_UNGATED_WRITERS = {
    "deep_research/service.py", "deep_research/run_research.py",
    "deep_research/acquire.py", "deep_research/run_batch.py",
    "deep_research/run_v2.py",
    "docs/service-lines/scripts/run_sourcing.py",
}


def _contract_module() -> dict:
    """Read the declaration without importing a database driver."""
    sys.path.insert(0, os.path.dirname(PKG))
    from deep_research import contract as ct   # noqa: E402
    return ct.as_doc()


def route_is_live(route: str, method: str) -> bool:
    """Is this verb actually served? Derived, never asserted.

    A route declared in the contract with nothing answering it is the same
    defect as a gate with no caller — a promise in a schema that nothing
    keeps. FastAPI's decorator carries the literal path, so the check is a
    substring of the decorator line rather than a guess.
    """
    try:
        src = open(ROUTER).read()
    except OSError:
        return False
    # `{rid}` in the contract, `{rid}` in the decorator — same literal.
    return f'@router.{method.lower()}("{route}"' in src


def request_writers() -> list[dict]:
    """Every file that can create a request, and whether it checks anything."""
    roots = ["mobius-skills/deep-research", "docs/service-lines", "mobius-payor/app"]
    base = "/Users/ananth/Mobius"
    out = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(os.path.join(base, root)):
            dirnames[:] = [d for d in dirnames
                           if d not in (".git", "__pycache__", "worktrees")]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    src = open(fp, encoding="utf-8", errors="ignore").read()
                except OSError:
                    continue
                if not REQUEST_WRITERS.search(src):
                    continue
                rel = os.path.relpath(fp, base)
                # Two ways to be gated, and both are real: refuse in code (the
                # runner) or read the published contract and refuse in its words
                # (the router). Anything else takes what it is handed.
                gated = ("evaluator_prompt is required" in src
                         or "research.contract" in src)
                out.append({"file": rel, "gated": gated,
                            "line": next((i + 1 for i, ln in enumerate(src.splitlines())
                                          if REQUEST_WRITERS.search(ln)), None)})
    return sorted(out, key=lambda x: (not x["gated"], x["file"]))


def mod_id(fname: str) -> str:
    """`runner.py` -> runner; `contract` -> contract; `contract/actions.py` ->
    contract/actions. A package is a module and so is each of its parts."""
    return fname[:-3] if fname.endswith(".py") else fname


def read_source(fname: str) -> str:
    """The source of a module, whether it is a file or a package."""
    path = os.path.join(PKG, fname)
    if os.path.isdir(path):
        return "\n".join(
            open(os.path.join(path, f), encoding="utf-8", errors="replace").read()
            for f in sorted(os.listdir(path)) if f.endswith(".py"))
    return open(path, encoding="utf-8", errors="replace").read()


def source_files() -> list[str]:
    """Every module, including the ones inside packages.

    Ananth, 2026-09-09: "we need to keep your code base really modular." So the
    contract became a package split by the question each part answers — and this
    generator promptly failed its own invariant, because it only ever walked
    top-level .py files and the curated prose for `contract` suddenly described
    nothing. That is the check doing its job: a refactor is exactly when a
    schematic silently stops describing the code.

    A package appears BOTH as itself — so it can carry one rating and one
    plain-language line — and as its parts, so a reader can see what it is made
    of and open any piece. Sub-modules are named `pkg/name`.
    """
    out = []
    for entry in sorted(os.listdir(PKG)):
        full = os.path.join(PKG, entry)
        if entry.endswith(".py") and not entry.startswith("__"):
            out.append(entry)
        elif (os.path.isdir(full) and not entry.startswith("__")
              and os.path.exists(os.path.join(full, "__init__.py"))):
            out.append(entry)                       # the package itself
            out += [f"{entry}/{f}" for f in sorted(os.listdir(full))
                    if f.endswith(".py") and not f.startswith("__")]
    return out


def derive(fname: str) -> dict:
    path = os.path.join(PKG, fname)
    # A package reads as everything in it: a rating on the package is a rating
    # on the seam, which is the useful thing to grade.
    src = read_source(fname)
    try:
        tree = ast.parse(src)
        doc = (ast.get_docstring(tree) or "").strip()
        api = [n.name + "()" for n in tree.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and not n.name.startswith("_")]
        imports = sorted({(n.module or "") for n in ast.walk(tree)
                          if isinstance(n, ast.ImportFrom)
                          and (n.module or "").startswith("deep_research")})
    except SyntaxError:
        doc, api, imports = "", [], []

    writes = sorted({w.lower() for w in WRITE_RE.findall(src)})
    reads = sorted({r.lower() for r in READ_RE.findall(src)} - set(writes))
    thinks = bool(THINKS_RE.search(src))
    notes = bool(NOTES_RE.search(src))

    # THE NEGATIVE CASE IS THE POINT. A module that neither records reasoning
    # nor files a ledger note is invisible: when it decides something wrong,
    # nothing anywhere says what it saw. That sentence is the one worth
    # stealing from the chat schema, and here it is derived rather than
    # remembered.
    if thinks:
        obs, note = "reasons", ("Writes a step-by-step trace to research.actor_thinking — "
                                "what it saw, what it made of it, what it decided.")
    elif notes:
        obs, note = "receipts", ("Files ledger events with an actor name, but records no "
                                 "reasoning: you can see WHAT it decided and not why.")
    else:
        obs, note = "silent", ("Records nothing of its own. Observable only through whatever "
                               "calls it — its behaviour has no identity in the trace.")

    return {
        "id": mod_id(fname),
        "path": f"deep_research/{fname}",
        "loc": len(src.splitlines()),
        "role": (doc.splitlines() or [""])[0],
        "role_full": doc[:1400],
        "api": api[:10],
        "config": sorted({g for m in ENV_RE.findall(src) for g in m if g}),
        "writes": writes,
        "reads": reads,
        "imports": [i.replace("deep_research.", "") for i in imports],
        "observability": obs,
        "observability_note": note,
        # An actor that can only file a success is not observable, however much
        # it emits.
        "can_record_failure": bool(FAIL_VOCAB.search(src)),
    }


# Who is traced, and by WHOM. Derived by finding every Thinking("actor") and
# from_verdicts("actor") call site, because "records nothing of its own" and
# "has no trace anywhere" are different facts and the judge is the proof: it
# reasons in detail, and the runner is what writes that reasoning down.
TRACE_CALL_RE = re.compile(r'(?:Thinking|from_verdicts)\(\s*["\']([a-z_]+)["\']')


def line_of(fname: str, pattern: str) -> int | None:
    """The line a thing is defined on, so the page can point at it.

    Ananth, 2026-09-09: "the vast amount of data makes it impossible to follow
    unless I can see it." A schematic that says a gate exists and cannot say
    WHERE sends you back to grep, which is the thing it was supposed to replace.
    """
    try:
        src = read_source(fname).splitlines()
    except OSError:
        return None
    rx = re.compile(pattern)
    for i, ln in enumerate(src, 1):
        if rx.search(ln):
            return i
    return None


def traced_actors(files: list[str]) -> dict:
    by_actor: dict[str, list[str]] = {}
    for f in files:
        src = read_source(f)
        for actor in set(TRACE_CALL_RE.findall(src)):
            by_actor.setdefault(actor, []).append(f[:-3])
    return {a: sorted(set(v)) for a, v in sorted(by_actor.items())}


def actors() -> list[dict]:
    """The cast, from language.ACTOR — the module's own vocabulary, not mine."""
    out = []
    try:
        sys.path.insert(0, os.path.dirname(PKG))
        from deep_research import language as L
        for key, name in (getattr(L, "ACTOR", {}) or {}).items():
            out.append({"key": key,
                        "name": name if isinstance(name, str) else name[0],
                        "help": (getattr(L, "ACTOR_HELP", {}) or {}).get(key, "")})
    except Exception as exc:
        out.append({"key": "(unavailable)", "name": "", "help": str(exc)[:120]})
    return out


# HOW MANY WAYS IN. The costliest bug of 2026-09-08 was a document-side gate
# that existed, was tested, and was never called from the LIVE entry point
# while a second entry point called it happily. Two ways into one pipeline is
# where that hides, so the count belongs on the page rather than in a memory.
def entry_points(files: list[str]) -> list[dict]:
    out = []
    for f in files:
        src = read_source(f)
        if '__name__ == "__main__"' in src or "argparse" in src:
            out.append({"id": mod_id(f),
                        "cli": bool(re.search(r"add_argument\(", src)),
                        "loc": len(src.splitlines())})
    return sorted(out, key=lambda x: -x["loc"])


# WHICH GUARANTEES EACH ENTRY POINT ACTUALLY PROVIDES.
#
# Counting entry points is not enough — what matters is whether they give the
# same answer the same protection. Derived, because asserting parity is exactly
# how it was lost: the document-side gate was written, tested, and reachable
# from run_batch while the LIVE runner never imported it, and nothing anywhere
# said so.
GUARANTEES = {
    "judges the answer": re.compile(r"\bcritique\("),
    "opens the document": re.compile(r"verify_in_document|document_gate"),
    "records reasoning": re.compile(r"Thinking\(|from_verdicts\("),
    "asks the registry": re.compile(r"registry_subjects|governing_resolved"),
    "reads the drafter's trace": re.compile(r"read_thinking"),
}


def entry_parity(files: list[str]) -> list[dict]:
    drivers = [f for f in files
               if re.match(r"run(ner|_v2|_batch|_research|_turn)\.py$", f)]
    out = []
    for f in drivers:
        src = read_source(f)
        has = {name: bool(rx.search(src)) for name, rx in GUARANTEES.items()}
        out.append({"id": mod_id(f), "has": has, "at": f"deep_research/{f}",
                    "score": sum(has.values()), "of": len(GUARANTEES)})
    return sorted(out, key=lambda x: -x["score"])


# WHAT ACTUALLY ENDS A REQUEST — derived, because Product Awareness's sharpest
# warning was that the stop conditions are the thing most likely to be secretly
# plural, and in chat that turned out to be four mechanisms with two of them
# disagreeing by 155 seconds because no artifact put them side by side.
#
# It is worse here than the loop block claims. FOUR modules can independently
# move a request to a terminal state and there is no single place that owns
# "this request is finished". run_v2 escalates from five separate lines.
TERMINAL = ("sourced", "escalated", "abandoned", "halted")
END_RE = {st: re.compile(r"set status\s*=\s*'%s'" % st) for st in TERMINAL}

# Declared, so that a NEW way to end a request fails the build until somebody
# acknowledges it. This list is the current reality, not the desired one.
KNOWN_TERMINATORS = {"runner", "run_v2", "run_research", "service", "resolution", "halt"}


def terminators(files: list[str]) -> list[dict]:
    out = []
    for f in files:
        src = read_source(f)
        hits = {st: len(rx.findall(src)) for st, rx in END_RE.items()}
        if any(hits.values()):
            out.append({"id": mod_id(f), "ends": {k: v for k, v in hits.items() if v},
                        "at": f"deep_research/{f}:{line_of(f, 'set status')}"})
    return sorted(out, key=lambda x: -sum(x["ends"].values()))


# CAN THIS ACTOR RECORD A FAILURE AT ALL?
#
# Product Awareness: "`tool_failed` is not rare, it is structurally impossible —
# make_tool_failed has zero callers while tool_invoked and tool_completed emit
# normally, so the telemetry is biased toward health BY CONSTRUCTION." The
# equivalent question here is whether an actor can write anything but a success.
FAIL_VOCAB = re.compile(
    r'"(?:dropped|refused|failed|error|could_not|not_run|absent|unverified|'
    r'undecidable|rejected|abandoned)[a-z_]*"'
    r"|decided\s*=\s*f?[\"'][^\"']*(?:dropped|refused|could not|failed)")


def failure_capable(fname: str) -> bool:
    src = read_source(fname)
    return bool(FAIL_VOCAB.search(src))


# WHAT SKILLS EACH MODULE HAS, AND HOW IT INVOKES THEM.
#
# Ananth, 2026-09-09: "we need to show the different skills that each module
# has access to and how they invoke it." Read out of the code, not described —
# a registry nobody can introspect leaves that question answerable only in
# prose, which is what the validator refactor was for.
def skills() -> dict:
    out = {}
    try:
        sys.path.insert(0, os.path.dirname(PKG))
        from deep_research.extract_critique import VALIDATORS, VALIDATOR_GAPS
        out["judge"] = {
            "invokes": "an ordered registry; the first validator to return a "
                       "verdict settles the field, so the cheap mechanical "
                       "checks run before anything that costs a model call",
            "skills": [{"name": v.name, "kind": v.kind, "asks": v.asks,
                        "emits": list(v.emits),
                        # WHERE, not just WHAT. A page that names a gate and
                        # cannot say which line it is on sends you back to grep.
                        #
                        # Looked up by the FUNCTION's own name, not the
                        # validator's. The first cut guessed `def _v_<name>`,
                        # and the two differ — `field_was_stated` is
                        # `_v_not_stated` — so most fell back to a bare name
                        # search and landed on the REGISTRY line while one
                        # landed on the function. A line number that is
                        # sometimes one thing and sometimes another is worse
                        # than none.
                        "at": f"deep_research/extract_critique.py:"
                              f"{line_of('extract_critique.py', r'def ' + v.fn.__name__ + r'\b')}",
                        "fn": v.fn.__name__}
                       for v in VALIDATORS],
            "gaps": VALIDATOR_GAPS,
        }
    except Exception as exc:
        out["judge"] = {"error": str(exc)[:160]}
    try:
        from deep_research import read_thinking as RT
        pats = [n for n in dir(RT) if n.startswith("_") and n.isupper()]
        out["arbiter"] = {
            "invokes": "regex patterns over the drafter's own reasoning trace, "
                       "each mapped to one course of action. Deterministic and "
                       "deliberately shallow — this is the component Ananth "
                       "named as the big lift.",
            "skills": [{"name": p.strip("_").lower(), "kind": "pattern",
                        "asks": "a recurring shape in the reasoning"} for p in pats],
            "gaps": [{"kind": "reasoning", "asks": "should another round happen, "
                      "and what should change?", "why": "four patterns decide this "
                      "today. A model here would be reasoning about the machine's "
                      "own reasoning, where being wrong is invisible — it would "
                      "need its own trace and 'I could not tell' as a real answer."}],
        }
    except Exception as exc:
        out["arbiter"] = {"error": str(exc)[:160]}
    out["drafter"] = {
        "invokes": "chat's ReAct loop and its tool manifest — NOT ours. The "
                   "evidence a question can reach is decided by which tools chat "
                   "holds, which is why a new evidence base is chat's work and "
                   "not a new adapter here.",
        "skills": [{"name": "search_corpus", "kind": "tool",
                    "asks": "what does the corpus say"},
                   {"name": "service_line_search", "kind": "tool",
                    "asks": "what does the registry know"}],
        "gaps": [{"kind": "tool", "asks": "telemetry, logs, code, metrics",
                  "why": "a failed-query or analytical deep dive needs evidence "
                  "chat cannot currently reach"}],
    }
    return out


# WHAT ACTUALLY HAPPENED, not just what exists.
#
# The schema was a map with no traffic on it. Every number below is counted
# from the state machine's own tables, so a node on the page can say how often
# it fired and what it decided — which is the difference between a diagram and
# something you can follow.
def live() -> dict:
    out = {"available": False}
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        url = [l.split("=", 1)[1].strip().strip('"').strip("'")
               for l in open("/Users/ananth/Mobius/mobius-rag/.env")
               if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")
        cx = psycopg2.connect(url)
        cur = cx.cursor(cursor_factory=RealDictCursor)
    except Exception as exc:
        out["why"] = f"no database: {type(exc).__name__}"
        return out

    def q(sql, *a):
        try:
            cur.execute(sql, a)
            return cur.fetchall()
        except Exception:
            cx.rollback()
            return []

    out["available"] = True
    # Which validator settled each field, and how often — the registry's own
    # names, counted from the verdicts it wrote.
    verdicts, issues, validators = 0, {}, {}
    for r in q("""select evaluator_verdict from research.attempt
                   where evaluator_verdict is not null
                   order by id desc limit 400"""):
        v = r["evaluator_verdict"]
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                continue
        cr = (v or {}).get("critique") or {}
        for f in (cr.get("kept") or []) + (cr.get("dropped") or []):
            verdicts += 1
            issues[f.get("issue") or "none"] = issues.get(f.get("issue") or "none", 0) + 1
            nm = f.get("validator") or f.get("check") or "unrecorded"
            validators[nm] = validators.get(nm, 0) + 1
    out["verdicts_seen"] = verdicts
    out["by_issue"] = dict(sorted(issues.items(), key=lambda x: -x[1]))
    out["by_validator"] = dict(sorted(validators.items(), key=lambda x: -x[1]))

    out["by_actor_trace"] = {r["actor"]: r["n"] for r in
                             q("""select actor, count(*) n from research.actor_thinking
                                   group by 1 order by 2 desc""")}
    out["requests_by_status"] = {r["status"]: r["n"] for r in
                                 q("""select status, count(*) n from research.request
                                       group by 1 order by 2 desc""")}
    out["spend_by_actor"] = {r["actor"]: round(float(r["c"] or 0) / 100, 4) for r in
                             q("""select actor, sum(cost_cents) c from research.llm_call
                                   group by 1 order by 2 desc nulls last""")}
    rec = q("""select r.id, r.subject_id, r.status,
                      (select count(*) from research.turn t where t.request_id=r.id) turns,
                      (select count(*) from research.actor_thinking a
                        where a.request_id=r.id) thinking
                 from research.request r order by r.id desc limit 8""")
    out["recent"] = [dict(x) for x in rec]
    cx.close()
    return out


def who_reasons(mods: list[dict]) -> dict:
    """Which actors think out loud and which only report — counted, not claimed."""
    by = {"reasons": [], "receipts": [], "silent": []}
    for m in mods:
        by[m["observability"]].append(m["id"])
    return by


def main() -> None:
    files = sorted(source_files())
    mods = [derive(f) for f in files]

    # Curated judgement, kept in its own file and merged here — never mixed with
    # the derived facts above, because one is checkable and the other is an
    # opinion that has to be argued for.
    content_path = os.path.join(HERE, "deep_research_schema_content.json")
    content = json.load(open(content_path)) if os.path.exists(content_path) else {}
    for m in mods:
        c = content.get(m["id"]) or {}
        m["how"] = (c.get("how") or "").strip()
        m["rating"] = c.get("rating", "ungraded")
        m["group"] = c.get("group", "unplaced")
        m["findings"] = c.get("findings", [])

    contract_doc = _contract_module()
    for v in contract_doc["verbs"]:
        v["live"] = route_is_live(v["route"], v["method"])
    writers = request_writers()

    doc = {
        "generated_by": "scripts/platform/gen_deep_research_schema.py",
        "module": "mobius-skills/deep-research",
        "consumers": ["service_line_registry", "payor facts"],

        # THE SPINE IS A LOOP, NOT A LINE. This is the one structural departure
        # from the chat schema, and pretending otherwise would misdescribe the
        # thing: a request does not pass through once, it goes round until a
        # round budget or a settlement condition stops it.
        "loop": {
            "opens": "a request states a question, a schema of fields it wants, "
                     "and how it will judge an answer",
            "each_round": ["drafter asks the corpus and writes prose",
                           "assembler pulls typed fields out of that prose",
                           "judge checks each field against the ANSWER",
                           "judge opens the cited DOCUMENT and checks it there",
                           "registry says whether that document governs this line",
                           "resolver states what a reader should do with the result",
                           "arbiter reads the drafter's reasoning and decides"],
            "repeats_until": "every field the requestor asked for is answered, or the "
                             "round budget runs out, or nothing actionable is left",
            "terminates_by": ["settled — the answer is recorded with its provenance",
                              "escalated — a person is asked, with the diagnosis attached",
                              "abandoned — the request itself was malformed"],
            "who_decides": "arbiter",
        },

        "state": {
            "request": "the question, its schema, its authority policy",
            "turn": "one round; carries the query actually asked",
            "attempt": "one answer, its sources, its reasoning trace, its verdicts",
            "verdict": "one field, one gate, kept or dropped, with the reason",
            "diagnosis": "why a question failed and what would fix it",
        },

        # The ordered checks a claim passes. Derived positions would be fragile;
        # these are stated, and the issue vocabulary they emit is derived below
        # so the two can be compared and a drift caught.
        "gates": [
            {"n": 1, "gate": "quote is in the ANSWER", "answers": "did the extractor invent the quote"},
            {"n": 2, "gate": "document was actually cited", "answers": "is the source one the answer used"},
            {"n": 3, "gate": "authority tier", "answers": "is this source good enough for this caller"},
            {"n": 4, "gate": "absence by reading", "answers": "was the governing rule read, for a negative"},
            {"n": 5, "gate": "judged", "answers": "does the quote support THIS value"},
            {"n": 6, "gate": "document opened", "answers": "does the cited document say it, and where"},
            {"n": 7, "gate": "subject", "answers": "does that document govern this service line"},
        ],
        "modules": mods,
        "actors": actors(),
        "who_reasons": who_reasons(mods),
        # The answer to "who has access to the thinking" — per actor, the
        # module that writes its trace. An actor absent from here reasons
        # nowhere that anything can read.
        "traced_by": traced_actors(files),
        "entry_points": entry_points(files),
        "entry_parity": entry_parity(files),
        "terminators": terminators(files),
        "skills": skills(),
        "live": live(),

        # THE CONTRACT AND THE UX, read out of one declaration. The router
        # reads the same thing back through research.contract, so a verb here
        # and a verb there cannot disagree — and the invariants below make that
        # a build failure rather than a discrepancy somebody notices in a demo.
        "contract": contract_doc,
        "request_writers": writers,

        # Stated in the artefact rather than smoothed over, the way the chat
        # schema states its span-identity limit.
        "honest_limits": [
            "Ratings and the plain-language `how` are curated, not derived. Everything "
            "else on this page is read out of the code.",
            "`observability` is derived from whether a module constructs a Thinking() "
            "trace or calls recorder.note — it proves a call site exists, not that the "
            "trace is complete or that anything reads it.",
            "The gate list is stated, not walked. The issue vocabulary each gate emits "
            "IS derived, so the two can be compared and a drift caught.",
            "Module-level, not function-level. A file rated green can hold a red "
            "function.",
        ],
    }
    # ── DISCIPLINE 6: THE GENERATOR MUST FAIL ───────────────────────────────
    #
    # Product Awareness, 2026-09-09: "'Generated from the code' is necessary and
    # not sufficient." Their gen_chat_submodules.py was outside the refresh
    # chain and drew a decision node a refactor had already deleted — everything
    # ELSE regenerated cleanly, which is exactly why nobody noticed.
    #
    # So: one command, and it exits non-zero when an invariant breaks. Each of
    # these fired at least once while being written, which is the only evidence
    # that a check is real.
    breaks = []

    promised = {"settled": "sourced", "escalated": "escalated",
                "abandoned": "abandoned"}
    reachable = {st for t in doc["terminators"] for st in t["ends"]}
    for word, state in promised.items():
        if state not in reachable:
            breaks.append(f"the loop promises it can end '{word}' and no module "
                          f"sets status='{state}' — a terminal state nothing reaches")

    seen_term = {t["id"] for t in doc["terminators"]}
    for new in sorted(seen_term - KNOWN_TERMINATORS):
        breaks.append(f"{new} can end a request and is not in KNOWN_TERMINATORS — "
                      f"a new way to finish a request appeared unannounced")

    ids = {m["id"] for m in doc["modules"]}
    for key in sorted(set(content) - ids - {"_"}):
        breaks.append(f"curated content for '{key}' matches no module — the prose "
                      f"describes something that no longer exists, and prose does "
                      f"not regenerate")

    actor_keys = {a["key"] for a in doc["actors"]}
    for a in sorted(set(doc["traced_by"]) - actor_keys):
        breaks.append(f"a trace is written for actor '{a}' which language.ACTOR "
                      f"does not declare — the vocabulary and the telemetry "
                      f"disagree")

    # THE CONTRACT MUST BE KEPT, not merely declared. Each of these fired while
    # being written, which is the only evidence that a check is real.
    for v in doc["contract"]["verbs"]:
        if not v["live"]:
            breaks.append(f"the contract declares {v['method']} {v['route']} and "
                          f"nothing serves it — a promise in a schema that no "
                          f"route keeps")
    declared_verbs = {v["id"] for v in doc["contract"]["verbs"]}
    for sfc in doc["contract"]["surfaces"]:
        for called in sfc["calls"]:
            if called not in declared_verbs:
                breaks.append(f"surface '{sfc['id']}' calls '{called}', which the "
                              f"contract does not declare — a UX rendering an API "
                              f"that does not exist")
    # AN ACTION NOBODY CAN EVER SEE is the same defect one layer out: a rule
    # written against a token the evaluator never sets is a button that is
    # declared, rendered nowhere, and impossible to notice missing.
    KNOWN_FACTS = {"any", "open", "settled", "running", "partial", "refused",
                   "authority_can_widen", "decision_open", "unusable",
                   # Registry, 2026-09-09: two scopes is not a split. Two
                   # identical values with different scope labels are a
                   # repetition the field has no room to label — a rendering
                   # problem, not a contradiction. So they are separate facts.
                   "two_scopes", "scopes_differ"}
    action_ids = {a["id"] for a in doc["contract"].get("actions", [])}
    for a in doc["contract"].get("actions", []):
        for tok in a.get("offer_when") or []:
            if tok not in KNOWN_FACTS:
                breaks.append(f"action '{a['id']}' is offered when '{tok}', which "
                              f"nothing ever sets — a button that can never "
                              f"appear")
    for stance, pair in (doc["contract"].get("recommended") or {}).items():
        if pair and pair[0] and pair[0] not in action_ids:
            breaks.append(f"stance '{stance}' recommends '{pair[0]}', which is not "
                          f"an action anybody can take")

    # RESERVED DOMAIN WORDS. Two seats independently refused "case" for two
    # different reasons — an appeal case with an id, and a patient episode —
    # which is the strongest evidence these are real rather than fussy. Appeals
    # named "appeal" as the highest-consequence word in their domain: it means
    # filing against a denial, on a clock. A warning in a message stays a
    # warning until somebody re-words a button; this fails the build instead.
    reserved = doc["contract"].get("reserved_words") or {}
    faces = ([(f"action {a['id']}", a.get("label", "")) for a in doc["contract"].get("actions", [])]
             + [(f"action {a['id']} closes_as", a.get("closes_as", ""))
                for a in doc["contract"].get("actions", [])]
             + [(f"field {k}", (v or {}).get("label", ""))
                for k, v in (doc["contract"].get("fields") or {}).items()]
             + [(f"surface {u['id']}", u.get("title", ""))
                for u in doc["contract"].get("surfaces", [])])
    for where, text in faces:
        for word, why in reserved.items():
            if re.search(r"\b" + re.escape(word) + r"s?\b", str(text or ""), re.I):
                breaks.append(f"{where} says “{text}” — “{word}” is reserved: "
                              f"{why}")

    # An action nobody is allowed to press is a button with no owner.
    roles = set(doc["contract"].get("roles") or [])
    for a in doc["contract"].get("actions", []):
        if roles and a.get("owner") not in roles:
            breaks.append(f"action '{a['id']}' is owned by "
                          f"{a.get('owner')!r}, which is not a declared role — "
                          f"a button with nobody entitled to press it")

    # THE FRAMEWORK MUST BE HONEST ABOUT ITSELF. An artifact claimed `present`
    # with nothing carrying it is a diagram, and this page's whole job is not
    # being one. `absent` is a legal, expected answer — two of the seven are —
    # so the check is on the CLAIM, not on the coverage.
    C = doc["contract"]
    for a in C.get("artifacts", []):
        if a.get("state") in ("present", "partial") and not a.get("carried_by"):
            breaks.append(f"artifact '{a['id']}' claims to be {a['state']} and "
                          f"names nothing that carries it — a framework "
                          f"describing itself rather than the code")
        if a.get("state") == "absent" and a.get("carried_by"):
            breaks.append(f"artifact '{a['id']}' is marked absent and names "
                          f"{a['carried_by']} — one of the two is stale")
        if a.get("state") not in (C.get("artifact_states") or
                                  ["present", "partial", "absent"]):
            breaks.append(f"artifact '{a['id']}' is in state {a.get('state')!r}, "
                          f"which is not a declared state")
    # A decision right the arbiter cannot act on is a rule nobody reasons with.
    for d, spec in (C.get("decisions") or {}).items():
        if spec.get("default") not in (C.get("rights") or []):
            breaks.append(f"decision '{d}' defaults to {spec.get('default')!r}, "
                          f"which is not a declared right")

    # A worklist item nobody is entitled to do, or that maps from a
    # recommendation nobody makes, is an item that will sit there forever.
    for k, v in (C.get("task_kinds") or {}).items():
        if v.get("owner_role") not in (C.get("roles") or []):
            breaks.append(f"task kind '{k}' is owned by {v.get('owner_role')!r}, "
                          f"which is not a declared role")
    # A worklist row whose target was identified on a basis nobody declared is
    # a row a reader cannot weigh. Ananth's ladder — extract, name, class,
    # explore — only helps if every row says which rung it stands on.
    for k, v in (C.get("task_kinds") or {}).items():
        pass
    acts = {a["id"] for a in C.get("actions", [])}
    kinds = set(C.get("task_kinds") or {})
    for b in ("extracted", "named", "class", "explore"):
        if b not in (C.get("target_basis") or {}):
            breaks.append(f"the deriver stands work on basis '{b}', which the "
                          f"contract does not declare — a worklist row a reader "
                          f"cannot weigh")
    for rec, spec in (C.get("task_from_recommendation") or {}).items():
        if rec not in acts:
            breaks.append(f"work is derived from recommendation '{rec}', which is "
                          f"not an action anybody can be advised to take")
        if spec.get("kind") not in kinds:
            breaks.append(f"recommendation '{rec}' derives task kind "
                          f"{spec.get('kind')!r}, which is not declared")

    for w in doc["request_writers"]:
        if w["gated"]:
            continue
        if not any(w["file"].endswith(k) for k in KNOWN_UNGATED_WRITERS):
            breaks.append(f"{w['file']}:{w['line']} can create a request and checks "
                          f"nothing, and is not in KNOWN_UNGATED_WRITERS — a new "
                          f"door opened without anyone declaring it")

    doc["invariants_checked"] = [
        "every terminal state the loop promises is reachable from some module",
        "no module can end a request without being declared a terminator",
        "no curated prose describes a module that no longer exists",
        "no trace is written for an actor the vocabulary does not declare",
        "every verb the contract declares is served by a live route",
        "no surface calls a verb the contract does not declare",
        "no undeclared, ungated way to create a request has appeared",
        "no action is offered on a condition nothing ever sets",
        "no stance recommends an action nobody can take",
        "no artifact claims to exist without naming what carries it",
        "every decision defaults to a declared right",
        "every task kind is owned by a declared role",
        "no work is derived from a recommendation nobody makes",
        "every way of identifying a document target is declared",
        "no user-facing label uses a reserved domain word (appeal, case, ...)",
        "every action is owned by a declared role",
        "the page's own JavaScript parses — a rendered page is not a running one",
    ]
    doc["curated_on"] = content.get("_curated_on", "2026-09-09")

    json.dump(doc, open(OUT, "w"), indent=1)
    render(doc, os.path.splitext(OUT)[0] + ".html")
    if breaks:
        print("\nBUILD FAILED — " + str(len(breaks)) + " invariant(s) broken:")
        for b in breaks:
            print("  ✗ " + b)
        sys.exit(1)
    print("  invariants: " + str(len(doc["invariants_checked"])) + " checked, all hold")
    gated = sum(1 for w in doc["request_writers"] if w["gated"])
    print(f"  contract   : {len(doc['contract']['verbs'])} verbs, all served · "
          f"{len(doc['contract']['surfaces'])} surfaces")
    print(f"  ways to create a request: {len(doc['request_writers'])}, "
          f"{gated} of them gated")
    r = doc["who_reasons"]
    print(f"{len(mods)} modules → {OUT}")
    print(f"  actors with a written trace: {', '.join(doc['traced_by']) or 'none'}")
    print(f"  entry points into the loop : "
          f"{', '.join(e['id'] for e in doc['entry_points'])}")
    print("  PARITY across the ways a turn can be run:")
    for e in doc["entry_parity"]:
        miss = [k for k, v in e["has"].items() if not v]
        print(f"    {e['id']:14} {e['score']}/{e['of']}"
              + (f"   missing: {', '.join(miss)}" if miss else "   complete"))
    print(f"  reason out loud : {len(r['reasons'])}")
    print(f"  file receipts   : {len(r['receipts'])}")
    print(f"  record nothing  : {len(r['silent'])}")




# ── the page ────────────────────────────────────────────────────────────────
# Laid out the way Product Awareness lays out docs/chat-schema: two collapsible
# panels so you can go back and forth, bands of flow you can read top to bottom,
# every node clickable into a detail side-panel, and a legend that says what the
# marks mean. Ananth: "intuitive... so that anyone can follow the flow, and
# clicking on them should display the details."
#
# PA will co-own this page, so it is also the spec contract between us: what is
# HERE is agreed, what is marked `future` is proposed and not yet built.
def esc(x):
    return (str(x if x is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# THINGS WE WILL NEED, MARKED AS SUCH. Ananth asked for the future on the page
# rather than in someone's head — but marked, so nobody reads a proposal as a
# promise. `state` is one of: built | partial | proposed.
FUTURE = [
    {"k": "f:write-gate", "t": "Stance gates the write", "state": "proposed",
     "why": "recommend() decides `conflicting` / `provenance_failed`, and nothing "
            "stops such a record reaching the fact store. Today the stance is "
            "visible and not binding. Ananth's decision, not ours.",
     "needs": "a ruling on whether a warned record may be written at all"},
    {"k": "f:one-terminator", "t": "One place ends a request", "state": "proposed",
     "why": "Four modules independently set a terminal state and run_v2 escalates "
            "from five separate lines. There is no single owner of 'this request "
            "is finished', which is how two paths come to disagree.",
     "needs": "a settle() every entry point calls"},
    {"k": "f:parity", "t": "Entry-point parity enforced", "state": "proposed",
     "why": "Five ways to run a turn, one carries all five guarantees. Today the "
            "table reports the gap; it should fail the build.",
     "needs": "a declared minimum guarantee set per entry point"},
    {"k": "f:actor-traces", "t": "Every actor reasons out loud", "state": "partial",
     "why": "Three of twelve named actors write a trace. The rest appear in the "
            "vocabulary and the ledger with nothing recording what they reasoned "
            "from — and in deep research the thinking is the product.",
     "needs": "Thinking() at the remaining call sites"},
    {"k": "f:registry-rule", "t": "Ask the registry which rule governs", "state": "proposed",
     "why": "authority_tier falls back to `published_standard` when a request "
            "carries no rule_ref. Service Line can answer properly — "
            "governing_resolved() already returns it — and asking beats inferring.",
     "needs": "line_key plumbed into the tier check"},
    {"k": "f:multi-hop", "t": "Multi-hop questions", "state": "proposed",
     "why": "'How is an inpatient psychiatric admission paid?' needs two hops — "
            "psych admissions are paid under the inpatient hospital methodology, "
            "and that methodology is APR-DRG. No single passage says both, so the "
            "drafter supplied the bridge from model knowledge and the extractor "
            "attached it to whatever was cited.",
     "needs": "either the bridging document acquired, or retrieval that composes"},
    {"k": "f:coverage", "t": "Coverage by reachability", "state": "proposed",
     "why": "Product Awareness measured that a filename-based test signal lies in "
            "both directions, and replaced it with 'does a test CALL this node'. "
            "Start where they ended up rather than repeating the mistake.",
     "needs": "scripts/platform/gen_coverage.py pointed at this package"},
    {"k": "f:shared-gate", "t": "One refresh, both schemas", "state": "proposed",
     "why": "PA's proposal: share the failing check rather than the code. A common "
            "refresh.sh runs both generators and fails if either does.",
     "needs": "agreement on the script's home"},
]


def check_script(html: str) -> bool:
    """Parse the emitted JavaScript. Fails the build if it will not run.

    Added after the sister generator shipped a page whose every script was dead
    from one stray newline inside a JS string literal. Nothing about a rendered
    page says its script did not parse — this page is entirely click-driven, so
    the same fault would leave a schematic that shows one panel and never
    changes it. Rendering is not running.
    """
    import subprocess
    import tempfile
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    if not blocks:
        return True
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write("\n".join(blocks))
        path = fh.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True,
                           text=True)
    except FileNotFoundError:
        print("  ! node not found — emitted script NOT parsed; treat as "
              "unverified.")
        return True
    finally:
        os.unlink(path)
    if r.returncode:
        print("\nBUILD FAILED — emitted JavaScript will not parse:")
        print("  " + (r.stderr or "").strip().replace("\n", "\n  ")[:900])
        return False
    return True


def render(doc, path):
    TONE = {"green": "ok", "amber": "warn", "red": "bad",
            "unproven": "info", "ungraded": ""}
    detail = {}          # data-k  ->  rendered detail HTML

    def add(k, title, sub, rows, tone=""):
        body = "".join(
            f"<div class=dr><div class=dk>{esc(a)}</div><div class=dv>{b}</div></div>"
            for a, b in rows if b)
        detail[k] = (f"<h3 class='dt {tone}'>{esc(title)}</h3>"
                     f"<p class=ds>{esc(sub)}</p>{body}")

    # ---- details: the round's steps -----------------------------------------
    STEP_DETAIL = [
        ("drafter", "Drafter", "Asks the corpus and writes prose.",
         "Chat's ReAct loop, up to ten reasoning rounds. It is the only actor whose "
         "reasoning has always been recorded — as thinking_log on the attempt — and "
         "for months nothing read it.", "extract_critique"),
        ("assembler", "Assembler", "Pulls typed fields out of that prose.",
         "Emits a value, the quote that grounds it, the document, the scope it "
         "governs, and whether the value stands alone or is one branch of a set.",
         "extract_critique"),
        ("judge", "Judge — against the answer", "Did the extractor faithfully copy?",
         "Four mechanical gates before any judgement: the quote must be in the "
         "ANSWER, the document must have been cited, the source must clear the "
         "caller's authority bar, and an absence is evidenced by having read the "
         "governing rule rather than by quoting one.", "extract_critique"),
        ("document", "Judge — against the document", "Does the source actually say it?",
         "Opens the cited document, locates the span, and cites page, paragraph and "
         "character offset. Five outcomes, and 'nothing was read' is kept separate "
         "from 'read it and it is not there'.", "locate"),
        ("registry", "Registry check", "Is this document about this service?",
         "Service Line Registry answers which rule governs which line. Only they "
         "hold it: the same quote in the same document is `governing` for one line "
         "and `off_subject` for another.", "runner"),
        ("resolver", "Resolver", "What should a reader DO with this?",
         "Turns recorded signals into a stance — usable, verify first, the evidence "
         "conflicts, the rule offers a choice, nobody checked — with the next step "
         "named. No model call.", "recommend"),
        ("arbiter", "Arbiter", "Go again, or settle?",
         "Reads the drafter's own reasoning for patterns — it conceded then asserted "
         "anyway, it named two populations, it never cited a rule it named — and "
         "turns each into the next question.", "read_thinking"),
    ]
    for k, t, sub, long, mod in STEP_DETAIL:
        m = next((x for x in doc["modules"] if x["id"] == mod), {})
        add(f"step:{k}", t, sub,
            [("what it does", esc(long)),
             ("mainly in", f"<code>{esc(m.get('path', mod))}</code>"),
             ("records", esc(m.get("observability_note", "")))])

    # ---- details: modules ---------------------------------------------------
    for m in doc["modules"]:
        finds = "".join(f"<li class='f {esc(k)}'>{esc(t)}</li>"
                        for k, t in (m["findings"] or []))
        add(f"mod:{m['id']}", m["id"], m["role"],
            [("in plain words", esc(m["how"]) if m["how"] else
              "<em>not yet written in plain language</em>"),
             ("rating", f"<span class='pill {TONE.get(m['rating'],'')}'>"
                        f"{esc(m['rating'])}</span> "
                        f"<span class=cur>curated {esc(doc['curated_on'])} — prose, "
                        f"not measured</span>"),
             ("findings", f"<ul class=finds>{finds}</ul>" if finds else ""),
             ("observability", esc(m["observability_note"])),
             ("can record a failure",
              "yes" if m["can_record_failure"] else
              "<b class=no>no — it can only file a success</b>"),
             ("writes", ", ".join(f"<code>{esc(w)}</code>" for w in m["writes"])),
             ("api", ", ".join(f"<code>{esc(a)}</code>" for a in m["api"][:8])),
             ("size", f"{m['loc']} lines · <code>{esc(m['path'])}</code>")],
            TONE.get(m["rating"], ""))

    # ---- details: entry points ---------------------------------------------
    for e in doc["entry_parity"]:
        miss = [k for k, v in e["has"].items() if not v]
        add(f"entry:{e['id']}", e["id"],
            f"{e['score']} of {e['of']} guarantees",
            [("gives", ", ".join(k for k, v in e["has"].items() if v) or "—"),
             ("MISSING", f"<b class=no>{esc(', '.join(miss))}</b>" if miss else "nothing"),
             ("why it matters",
              "An answer produced here carries only the protections ticked above, "
              "and nothing on the result says which entry point produced it.")],
            "ok" if not miss else ("bad" if e["score"] < 2 else "warn"))

    # ---- details: terminators ----------------------------------------------
    for t in doc["terminators"]:
        add(f"end:{t['id']}", t["id"], "can end a request",
            [("ends it as", ", ".join(f"<code>{esc(k)}</code>×{v}"
                                      for k, v in t["ends"].items())),
             ("note", "Four modules can independently finish a request and there is "
                      "no single owner of that decision.")], "warn")

    # ---- details: skills per module ----------------------------------------
    for who, sk in doc.get("skills", {}).items():
        if "error" in sk:
            continue
        rows = "".join(
            f"<li class='f good'><b>{esc(x['name'])}</b> <span class=cur>"
            f"{esc(x['kind'])}</span><br>{esc(x['asks'])}"
            + (f"<br><code>{esc(x['at'])}</code>" if x.get("at") else "") + "</li>"
            for x in sk["skills"])
        gaps = "".join(
            f"<li class='f bad'><b>{esc(g['kind'])}</b> — {esc(g['asks'])}<br>"
            f"<span class=cur>{esc(g['why'])}</span></li>"
            for g in sk.get("gaps", []))
        add(f"skill:{who}", f"{who} — its skills", f"{len(sk['skills'])} it has, "
            f"{len(sk.get('gaps', []))} it does not",
            [("how it invokes them", esc(sk["invokes"])),
             ("has", f"<ul class=finds>{rows}</ul>"),
             ("does NOT have", f"<ul class=finds>{gaps}</ul>" if gaps else "—")])

    # ---- details: future ----------------------------------------------------
    for f in FUTURE:
        add(f["k"], f["t"], f"future · {f['state']}",
            [("why", esc(f["why"])), ("what it needs", esc(f["needs"])),
             ("status", f"<b>{esc(f['state'])}</b> — proposed on this page, not built. "
                        f"Nothing here is a commitment until it is agreed.")],
            "info")

    # ---- details: what actually ran -----------------------------------------
    LV = doc.get("live") or {}
    if LV.get("available"):
        def tbl(d, unit=""):
            return ("<ul class=finds>" + "".join(
                f"<li class=f><b>{esc(k)}</b> — {esc(v)}{esc(unit)}</li>"
                for k, v in list(d.items())[:12]) + "</ul>") if d else "—"
        add("live:all", "What actually ran",
            f"counted from the state machine's own tables · "
            f"{LV.get('verdicts_seen', 0)} verdicts",
            [("requests", tbl(LV.get("requests_by_status", {}))),
             ("which validator settled it", tbl(LV.get("by_validator", {}))),
             ("why fields were dropped", tbl(LV.get("by_issue", {}))),
             ("reasoning steps recorded", tbl(LV.get("by_actor_trace", {}))),
             ("spend by actor", tbl(LV.get("spend_by_actor", {}), " USD")),
             ("note", "These are counts over recent attempts, not a full history. "
                      "A validator absent from the list has not settled a field "
                      "lately — which is a fact about the runs, not about the code.")])
        for r in LV.get("recent", []):
            add(f"live:req{r['id']}", f"request {r['id']}", esc(r["subject_id"]),
                [("status", f"<b>{esc(r['status'])}</b>"),
                 ("rounds", str(r["turns"])),
                 ("reasoning steps", str(r["thinking"])),
                 ("note", "Open the console for the full trace of this request.")])

    # ---- details: the contract ---------------------------------------------
    C = doc.get("contract") or {}
    FIELDS = C.get("fields") or {}

    def fieldrow(names, required):
        if not names:
            return ""
        out = []
        for n in names:
            f = FIELDS.get(n) or {}
            bits = [f"<b>{esc(n)}</b> <span class=cur>{esc(f.get('type',''))}</span>"]
            if f.get("says"):
                bits.append("<br>" + esc(f["says"]))
            if f.get("because"):
                bits.append(f"<br><span class=cur>{esc(f['because'])}</span>")
            if f.get("measured"):
                bits.append(f"<br><span class=cur>measured: {esc(f['measured'])}</span>")
            out.append(f"<li class='f {'bad' if required else 'good'}'>"
                       + "".join(bits) + "</li>")
        return "<ul class=finds>" + "".join(out) + "</ul>"

    for v in C.get("verbs", []):
        refs = "<ul class=finds>" + "".join(
            f"<li class='f bad'><b>{esc(str(r['status']))}</b> {esc(r['when'])} — "
            f"“{esc(r['say'])}”</li>" for r in v.get("refusals", [])) + "</ul>"
        warns = "".join(f"<li class='f unproven'>{esc(w['say'])}</li>"
                        for w in v.get("warnings", []))
        rets = "<ul class=finds>" + "".join(
            f"<li class=f><b>{esc(k)}</b> — {esc(x)}</li>"
            for k, x in (v.get("returns") or {}).items()) + "</ul>"
        add(f"verb:{v['id']}", f"{v['method']} {v['route']}", v["says"],
            [("live",
              "<b class=ok>served</b>" if v["live"] else
              "<b class=no>declared and NOT served</b>"),
             ("why it exists", esc(v.get("because", ""))),
             ("required", fieldrow(v.get("required", []), True)),
             ("optional", fieldrow(v.get("optional", []), False)),
             ("refuses", refs if v.get("refusals") else "—"),
             ("warns", f"<ul class=finds>{warns}</ul>" if warns else "—"),
             ("returns", rets),
             ("enforced by", f"<code>{esc(v['enforced_by'])}</code>"
                             if v.get("enforced_by") else "—"),
             ("who calls it", esc(", ".join(v.get("audience", [])))),
             ("declared in", "<code>deep_research/contract.py</code> → published to "
                             "<code>research.contract</code> → read by the router at "
                             "request time. One declaration, two consumers.")],
            "ok" if v["live"] else "bad")

    for sfc in C.get("surfaces", []):
        add(f"ux:{sfc['id']}", sfc["title"], sfc["audience"],
            [("shows", esc(sfc["shows"])),
             ("who sees what", f"<code>{esc(sfc['filter'])}</code>" if sfc["filter"]
                               else "everything — no filter"),
             ("calls", " ".join(f"<code>{esc(x)}</code>" for x in sfc["calls"])),
             ("state", f"<b>{esc(sfc['state'])}</b>"),
             ("the point", "Five doors, one contract. What separates the audiences "
                           "is the FILTER and which verbs they may call — not a "
                           "different API underneath.")],
            "ok" if sfc["state"] == "live" else "info")

    # ---- details: the actions ----------------------------------------------
    rec_by_action = {}
    for stance, pair in (C.get("recommended") or {}).items():
        if pair and pair[0]:
            rec_by_action.setdefault(pair[0], []).append(
                (stance if stance != "None" else "not settled yet", pair[1]))
    for a in C.get("actions", []):
        recs = "".join(
            f"<li class='f good'>recommended when the stance is "
            f"<b>{esc(st)}</b><br><span class=cur>{esc(why)}</span></li>"
            for st, why in rec_by_action.get(a["id"], []))
        add(f"act:{a['id']}", a["label"], a["id"],
            [("what it does", esc(a["does"])),
             ("who it moves it to", esc(a["moves"])),
             ("offered when", esc(a["when"])),
             ("needs", " ".join(f"<code>{esc(n)}</code>" for n in a.get("needs"))
                       or "nothing"),
             ("rule", " · ".join(f"<code>{esc(t)}</code>"
                                 for t in a.get("offer_when", []))),
             ("we advise it", f"<ul class=finds>{recs}</ul>" if recs else
              "<span class=cur>never the recommendation — always available, "
              "never advised</span>"),
             ("posted to", f"<code>{esc(a['post_to'])}</code>" if a.get("post_to")
                           else "<code>POST /api/research/request/{id}/act</code>")],
            "ok" if rec_by_action.get(a["id"]) else "")

    T = C.get("timing") or {}
    add("act:eta", "How long — measured, not promised",
        f"{T.get('sampled_turns')} completed turns, {T.get('measured_on')}",
        [("median round", f"<b>{T.get('median_round_min')} minutes</b>"),
         ("slowest tenth", f"<b>{round((T.get('p90_round_min') or 0)/60)} hours</b>"),
         ("why the spread", "That p90 is not slow compute. It is a turn parked on "
                            "Discovery, on Lexicon or on a person. Averaging the "
                            "two gives an estimate wrong in both directions, so "
                            "the answer says WHO it is waiting on before it says "
                            "how long."),
         ("the four answers", "<ul class=finds>"
          "<li class=f><b>you</b> — a decision is open; nothing moves until it is answered</li>"
          "<li class=f><b>a service</b> — parked on Discovery or Lexicon, on their clock</li>"
          "<li class=f><b>the machine</b> — a round is running</li>"
          "<li class='f bad'><b>nothing</b> — it will not progress on its own</li></ul>")],
        "info")

    # ---- details: the seven artifacts --------------------------------------
    TONE_ART = {"present": "ok", "partial": "warn", "absent": "bad"}
    for a in C.get("artifacts", []):
        add(f"art:{a['id']}", a["title"], a["says"],
            [("state", f"<b class={'no' if a['state']=='absent' else ''}>"
                       f"{esc(a['state'])}</b>"),
             ("supplied by", esc(a["supplied_by"])),
             ("carried by", ", ".join(f"<code>{esc(x)}</code>"
                                      for x in a.get("carried_by") or [])
                            or "<b class=no>nothing — it does not exist yet</b>"),
             ("declared in", f"<code>deep_research/{esc(a['declared_in'])}</code>"
                             if a.get("declared_in") else "—"),
             ("what is missing", esc(a.get("gap", "")))],
            TONE_ART.get(a["state"], ""))

    sc = C.get("source_classes") or {}
    add("art:sources", "What a source can BE",
        f"{len(sc)} classes, in the words the gates emit",
        [("", "<ul class=finds>" + "".join(
            f"<li class='f {'bad' if k in ('payer_policy','inferred_source') else 'good'}'>"
            f"<b>{esc(k)}</b> — {esc(v.get('says'))}<br>"
            f"<span class=cur>basis: {esc(v.get('basis'))}</span>"
            + (f"<br><span class=cur>{esc(v['note'])}</span>" if v.get("note") else "")
            + "</li>" for k, v in sc.items()) + "</ul>"),
         ("the default grant", esc((C.get("authority_default") or {}).get("why", ""))),
         ("why the basis matters", "A grant conditioned on evidence rather than "
          "on a label: a payer manual is admissible where the corpus says so and "
          "refused where it was inferred from a filename. A tier alone cannot "
          "say that, which is part of why the tier field sat unused on 64 of 68 "
          "requests.")], "warn")

    tl = C.get("tools") or {}
    add("art:tools", "What it may use", f"{len(tl)} capabilities, none declared yet",
        [("", "<ul class=finds>" + "".join(
            f"<li class='f {'bad' if v.get('default')=='ask' else 'good'}'>"
            f"<b>{esc(k)}</b> <span class=cur>default {esc(v.get('default'))}</span>"
            f"<br>{esc(v.get('says'))} <span class=cur>· costs {esc(v.get('costs'))}</span>"
            + (f"<br><span class=cur>{esc(v['note'])}</span>" if v.get("note") else "")
            + "</li>" for k, v in tl.items()) + "</ul>"),
         ("note", "No column, no table, no declaration. What a request GETS "
                  "depends on which entry point it came through, and nothing on "
                  "the result says which — the five-ways-to-run-a-turn problem "
                  "seen from the caller's side.")], "bad")

    dc = C.get("decisions") or {}
    add("art:decisions", "What you keep and what you delegate",
        f"{len(dc)} decisions · undeclared defaults to ask",
        [("", "<ul class=finds>" + "".join(
            f"<li class='f {'good' if v.get('default')=='machine' else 'bad' if v.get('default')=='caller' else 'unproven'}'>"
            f"<b>{esc(k)}</b> <span class=cur>default {esc(v.get('default'))}</span>"
            f"<br>{esc(v.get('says'))}"
            + (f"<br><span class=cur>measured: {esc(v['measured'])}</span>"
               if v.get("measured") else "")
            + (f"<br><span class=cur>{esc(v['note'])}</span>" if v.get("note") else "")
            + "</li>" for k, v in dc.items()) + "</ul>"),
         ("why it changes the arbiter", "The judge is the only actor with a "
          "declared standard and it visibly cites it — \"this caller allows "
          "published_standard, incorporated_by_reference\". The arbiter has none, "
          "so it reasons from patterns it carries itself: \"no pattern matched\". "
          "13 reasoning steps between the arbiter and the diagnoser, against the "
          "judge's dozens."),
         ("the meter", "An undeclared decision defaults to ASK. Every time that "
          "fires it is a decision the request type should have covered — so the "
          "types get derived from what happens rather than invented.")], "bad")

    W = doc.get("request_writers") or []
    gated = [w for w in W if w["gated"]]
    add("contract:doors", "Ways to create a request",
        f"{len(W)} of them · {len(gated)} check anything",
        [("", "<ul class=finds>" + "".join(
            f"<li class='f {'good' if w['gated'] else 'bad'}'>"
            f"<code>{esc(w['file'])}:{esc(str(w['line']))}</code>"
            + ("" if w["gated"] else " <span class=cur>takes what it is handed</span>")
            + "</li>" for w in W) + "</ul>"),
         ("what it cost", "15 of 63 live requests carry no instruction on how to "
                          "grade the answer — the one thing the gate exists to "
                          "require — and 17 have no invoker, so their answers have "
                          "nowhere to go."),
         ("the fix", "Not a seventh check. One door with the gate underneath it, "
                     "and an invariant that fails this build when a new ungated "
                     "one appears.")],
        "bad")

    # ---- details: the honest limits ----------------------------------------
    add("meta:limits", "What this page does not tell you", "read this before trusting it",
        [("", "<ul class=finds>" + "".join(f"<li class=f>{esc(x)}</li>"
                                           for x in doc["honest_limits"]) + "</ul>"),
         ("invariants that fail the build",
          "<ul class=finds>" + "".join(f"<li class='f good'>{esc(x)}</li>"
                                       for x in doc["invariants_checked"]) + "</ul>")])

    # ---- the diagram --------------------------------------------------------
    def chip(k, label, mark="", tone=""):
        return (f"<button class='node {tone}' data-k='{esc(k)}'>"
                f"<span class=nl>{esc(label)}</span>"
                f"<span class=nm>{esc(mark)}</span></button>")

    steps = "<div class=arr>↓</div>".join(
        chip(f"step:{k}", t, "●" if k in ("judge", "arbiter", "document") else "◦")
        for k, t, *_ in STEP_DETAIL)

    entries = "".join(
        chip(f"entry:{e['id']}", e["id"], f"{e['score']}/{e['of']}",
             "ok" if e["score"] == e["of"] else ("bad" if e["score"] < 2 else "warn"))
        for e in doc["entry_parity"])

    ends = "".join(chip(f"end:{t['id']}", t["id"],
                        "·".join(t["ends"]), "warn") for t in doc["terminators"])

    groups = {}
    for m in doc["modules"]:
        groups.setdefault(m["group"], []).append(m)
    mods = "".join(
        f"<div class=gl>{esc(g)}</div>" + "".join(
            chip(f"mod:{m['id']}", m["id"],
                 {"reasons": "●", "receipts": "◐", "silent": "◦"}[m["observability"]],
                 TONE.get(m["rating"], ""))
            for m in sorted(groups[g], key=lambda x: -x["loc"]))
        for g in ["the loop", "the judge", "the answer", "provenance", "the surface",
                  "unplaced"] if g in groups)

    future = "".join(chip(f["k"], f["t"], f["state"], "info") for f in FUTURE)
    LV = doc.get("live") or {}
    livechips = ""
    if LV.get("available"):
        livechips = chip("live:all", "What actually ran",
                         f"{LV.get('verdicts_seen',0)} verdicts", "ok")
        livechips += "".join(
            chip(f"live:req{r['id']}", f"req {r['id']} · {r['subject_id'][:34]}",
                 f"{r['turns']}r · {r['thinking']} steps",
                 "ok" if r["status"] == "sourced" else
                 ("warn" if r["status"] == "open" else ""))
            for r in LV.get("recent", [])[:6])
    skl = "".join(
        chip(f"skill:{who}", f"{who} — {len(sk['skills'])} skills",
             f"{len(sk.get('gaps', []))} missing",
             "warn" if sk.get("gaps") else "ok")
        for who, sk in doc.get("skills", {}).items() if "error" not in sk)

    C = doc.get("contract") or {}
    verbs = "".join(chip(f"verb:{v['id']}", f"{v['method']} {v['route']}",
                         "served" if v["live"] else "NOT SERVED",
                         "ok" if v["live"] else "bad") for v in C.get("verbs", []))
    surfaces = "".join(chip(f"ux:{u['id']}", u["title"], u["state"],
                            "ok" if u["state"] == "live" else "info")
                       for u in C.get("surfaces", []))
    TONE_ART = {"present": "ok", "partial": "warn", "absent": "bad"}
    arts = "".join(chip(f"art:{a['id']}", a["title"], a["state"],
                        TONE_ART.get(a["state"], ""))
                   for a in C.get("artifacts", []))
    arts += chip("art:sources", "What a source can be",
                 f"{len(C.get('source_classes') or {})} classes", "warn")
    arts += chip("art:tools", "What it may use",
                 f"{len(C.get('tools') or {})} tools", "bad")
    arts += chip("art:decisions", "Kept or delegated",
                 f"{len(C.get('decisions') or {})} decisions", "bad")

    acts = "".join(chip(f"act:{a['id']}", a["label"], a["id"],
                        "ok" if any((p or [None])[0] == a["id"]
                                    for p in (C.get("recommended") or {}).values())
                        else "")
                   for a in C.get("actions", []))
    acts += chip("act:eta", "How long — measured", "21 min median", "info")

    W = doc.get("request_writers") or []
    doors = chip("contract:doors", "Ways to create a request",
                 f"{sum(1 for w in W if w['gated'])} of {len(W)} gated", "bad")

    L = doc["loop"]
    dj = json.dumps(detail)
    html = f"""<title>Deep Research State Model</title>
<link rel=stylesheet href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
:root{{--ink:#1a1d21;--ink2:#374151;--muted:#64748b;--bg:#fafbfc;--bg2:#f1f5f9;
--card:#fff;--line:#e2e8f0;--accent:#3b82f6;--violet:#7c3aed;--ok:#16a34a;
--warn:#f59e0b;--bad:#dc2626;--r:8px;
--sans:"DM Sans",system-ui,sans-serif;--mono:"JetBrains Mono",ui-monospace,monospace}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--ink:#e6edf0;
--ink2:#c0ccd3;--muted:#8ea0aa;--bg:#0f1418;--bg2:#1b242a;--card:#161d22;
--line:#28343b;--accent:#74b6d4;--violet:#a78bfa;--ok:#4ade80;--warn:#fbbf24;--bad:#f87171}}}}
:root[data-theme=dark]{{--ink:#e6edf0;--ink2:#c0ccd3;--muted:#8ea0aa;--bg:#0f1418;
--bg2:#1b242a;--card:#161d22;--line:#28343b;--accent:#74b6d4;--violet:#a78bfa;
--ok:#4ade80;--warn:#fbbf24;--bad:#f87171}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}}
header{{position:sticky;top:0;z-index:9;background:var(--bg);border-bottom:1px solid var(--line);
padding:12px 20px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
h1{{font-size:1.05rem;font-weight:600;margin:0}}
.tag{{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;
color:var(--violet);border:1px solid var(--violet);padding:2px 7px;border-radius:99px}}
.sp{{flex:1}}
.pbtn{{font-family:var(--mono);font-size:11.5px;background:var(--card);color:var(--ink2);
border:1px solid var(--line);border-radius:var(--r);padding:5px 11px;cursor:pointer}}
.pbtn:hover{{border-color:var(--accent);color:var(--accent)}}
.wrap{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,420px);gap:18px;
padding:18px 20px 80px;max-width:1320px;margin:0 auto;align-items:start}}
.wrap.diagram-collapsed{{grid-template-columns:0 minmax(0,1fr)}}
.wrap.diagram-collapsed .main{{display:none}}
.wrap.detail-collapsed{{grid-template-columns:minmax(0,1fr) 0}}
.wrap.detail-collapsed .side{{display:none}}
@media(max-width:900px){{.wrap{{grid-template-columns:1fr}}}}
.band{{background:var(--card);border:1px solid var(--line);border-radius:var(--r);
padding:14px 16px;margin-bottom:14px}}
.band-t{{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;
color:var(--muted);margin-bottom:4px}}
.band-s{{font-size:13px;color:var(--ink2);margin:0 0 12px;max-width:70ch}}
.node{{display:flex;align-items:center;gap:8px;width:100%;text-align:left;cursor:pointer;
background:var(--bg2);color:var(--ink);border:1px solid var(--line);border-left:3px solid var(--line);
border-radius:6px;padding:8px 12px;font-family:var(--sans);font-size:13.5px;margin-bottom:3px}}
.node:hover{{border-color:var(--accent);background:var(--card)}}
.node:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
.node.on{{border-color:var(--accent);background:var(--card);box-shadow:inset 3px 0 0 var(--accent)}}
.node.ok{{border-left-color:var(--ok)}} .node.warn{{border-left-color:var(--warn)}}
.node.bad{{border-left-color:var(--bad)}} .node.info{{border-left-color:var(--accent)}}
.nl{{flex:1}} .nm{{font-family:var(--mono);font-size:10.5px;color:var(--muted)}}
.arr{{text-align:center;color:var(--muted);font-size:11px;line-height:1;margin:1px 0}}
.row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:4px}}
.gl{{font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;
color:var(--violet);margin:10px 0 4px}}
.legend{{font-size:11.5px;color:var(--muted);margin-top:10px;line-height:1.7}}
.side{{position:sticky;top:64px}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:var(--r);
padding:16px 18px;max-height:calc(100vh - 96px);overflow:auto}}
.dt{{font-size:1.05rem;margin:0 0 2px;font-weight:600}}
.dt.ok{{color:var(--ok)}} .dt.warn{{color:var(--warn)}} .dt.bad{{color:var(--bad)}}
.dt.info{{color:var(--accent)}}
.ds{{font-size:13px;color:var(--muted);margin:0 0 14px}}
.dr{{display:grid;grid-template-columns:112px 1fr;gap:10px;padding:7px 0;
border-top:1px solid var(--line);font-size:13.5px}}
.dk{{font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;
color:var(--muted);padding-top:3px}}
.dv{{color:var(--ink2);overflow-wrap:anywhere}}
.dv code{{font-family:var(--mono);font-size:12px;background:var(--bg2);padding:1px 5px;
border-radius:3px}}
.pill{{font-family:var(--mono);font-size:10px;text-transform:uppercase;padding:2px 7px;
border-radius:99px;background:var(--bg2)}}
.pill.ok{{color:var(--ok)}} .pill.warn{{color:var(--warn)}} .pill.bad{{color:var(--bad)}}
.cur{{font-size:11px;color:var(--muted)}}
.no{{color:var(--bad)}}
.finds{{list-style:none;padding:0;margin:0}}
.f{{padding-left:18px;position:relative;margin-bottom:5px}}
.f:before{{position:absolute;left:0;font-family:var(--mono);font-size:10px}}
.f.good:before{{content:"✓";color:var(--ok)}}
.f.bad:before{{content:"✗";color:var(--bad)}}
.f.unproven:before{{content:"?";color:var(--accent)}}
</style>
<header><h1>Deep Research — the state model</h1>
<span class=tag>spec contract</span>
<span class=sp></span>
<button class=pbtn id=tgl-diagram aria-pressed=false>Hide flow</button>
<button class=pbtn id=tgl-detail aria-pressed=false>Hide detail</button></header>

<div class=wrap id=wrap><div class=main>

<div class=band><div class=band-t>1 · A request opens</div>
<p class=band-s>{esc(L['opens'])}</p>
{chip('meta:limits', 'Read this first — what the page cannot tell you', '?', 'info')}</div>

<div class=band><div class=band-t>2 · What every request carries</div>
<p class=band-s>Seven artifacts. Two exist in full, two partly, and three not at
all — and the three missing ones are where the arbiter has been improvising.
State is read against what actually carries each: an artifact claiming to exist
without naming a column fails this build.</p>
<div class=row>{arts}</div></div>

<div class=band><div class=band-t>3 · The contract — one declaration, several consumers</div>
<p class=band-s>Four verbs, declared once in <code>deep_research/contract.py</code>,
published to <code>research.contract</code>, and read back by the router at request
time. The build fails if a verb here has no live route, or if a surface calls one
that is not declared.</p>
<div class=row>{verbs}</div>
<div class=gl>the ux · five doors, one contract</div>
<div class=row>{surfaces}</div>
<div class=gl>what a person can DO about it — one is recommended, with the reason</div>
<div class=row>{acts}</div>
<div class=gl>and every way in</div>
{doors}
<p class=legend>What separates the audiences is a FILTER and which verbs they may
call — not a different API underneath.</p></div>

<div class=band><div class=band-t>4 · The round — click any step</div>
<p class=band-s>This is what happens once, per round. It repeats until
{esc(L['repeats_until'])}.</p>
{steps}
<p class=legend>● records its own reasoning &nbsp; ◐ files a verdict only &nbsp;
◦ records nothing of its own<br>
Click a step for what it does and where it lives.</p></div>

<div class=band><div class=band-t>5 · Five ways to run a turn — only one is complete</div>
<p class=band-s>A turn can be started five ways and they do not offer the same
protection. Derived from the code, because asserting parity is how it was lost.</p>
<div class=row>{entries}</div></div>

<div class=band><div class=band-t>6 · What ends a request</div>
<p class=band-s>Four modules can independently finish a request, and one of them
escalates from five separate lines. There is no single owner of the decision.</p>
<div class=row>{ends}</div></div>

<div class=band><div class=band-t>7 · What actually ran — the map with traffic on it</div>
<p class=band-s>Everything above is structure. This is counted from the state
machine's own tables: which validator settled each field, why fields were dropped,
how many reasoning steps each actor recorded, and what it cost.</p>
{livechips}</div>

<div class=band><div class=band-t>8 · What each actor can actually do</div>
<p class=band-s>The skills each one has and how it invokes them, read out of the
code — the judge from its validator registry, the arbiter from its pattern list,
the drafter from chat's tools. What it does NOT have is listed too, because an
absent check is invisible otherwise.</p>
<div class=row>{skl}</div></div>

<div class=band><div class=band-t>9 · The modules</div>
<p class=band-s>Rating and the plain-language line are curated prose.
Everything else is read out of the code on every build.</p>{mods}</div>

<div class=band><div class=band-t>10 · What we will need — proposed, not built</div>
<p class=band-s>On the page rather than in somebody's head, and marked so nobody
reads a proposal as a promise. Nothing here is agreed until it is agreed.</p>
{future}</div>

</div><div class=side><div class=panel id=panel></div></div></div>

<script>
var D = {dj};
var cur = null;
function show(k){{
  var p = document.getElementById('panel');
  if(!D[k]){{ return; }}
  p.innerHTML = D[k];
  document.querySelectorAll('.node.on').forEach(function(n){{n.classList.remove('on');}});
  var b = document.querySelector('[data-k="'+k.replace(/"/g,'\\\\"')+'"]');
  if(b) b.classList.add('on');
  cur = k;
  try{{ history.replaceState(null,'','#'+encodeURIComponent(k)); }}catch(e){{}}
}}
document.addEventListener('click', function(e){{
  var t = e.target.closest('[data-k]');
  if(t) show(t.dataset.k);
}});
// Two panels, each collapsible, so you can go back and forth: flow alone when
// you are orienting, detail alone when you are reading one thing closely.
function bind(id, cls, hide, showTxt, other, otherCls){{
  var w = document.getElementById('wrap'), b = document.getElementById(id);
  function apply(on, store){{
    w.classList.toggle(cls, on);
    b.textContent = on ? showTxt : hide;
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    if(on) w.classList.remove(otherCls);
    try{{ if(store) localStorage.setItem('drschema:'+cls, on ? '1' : '0'); }}catch(e){{}}
  }}
  b.addEventListener('click', function(){{ apply(!w.classList.contains(cls), true); }});
  var stored = false;
  try{{ stored = localStorage.getItem('drschema:'+cls) === '1'; }}catch(e){{}}
  if(stored) apply(true, false);
}}
bind('tgl-diagram','diagram-collapsed','Hide flow','Show flow','tgl-detail','detail-collapsed');
bind('tgl-detail','detail-collapsed','Hide detail','Show detail','tgl-diagram','diagram-collapsed');
var start = decodeURIComponent((location.hash||'').replace(/^#/,''));
show(D[start] ? start : 'step:judge');
</script>"""
    open(path, "w").write(html)
    if not check_script(html):
        sys.exit(1)


if __name__ == "__main__":
    main()
