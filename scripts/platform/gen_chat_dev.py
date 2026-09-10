#!/usr/bin/env python3
"""Dev build of the chat pipeline schema — richer than what /platform ships.

Written because Ananth pressure-tested the deployed diagram and found three
holes, all of them boundary errors rather than missing detail:

  1. state_load's entry said nothing. "Is this where PHI is checked?" No — and
     the description could not tell you that, because it only restated a thin
     docstring.
  2. The PHI gate is not in the diagram at all. It runs at the API boundary,
     BEFORE the pipeline, and it is fail-closed. So is the queue/worker hop.
  3. LLM Manager is not in the diagram, and every generating step calls it.

Root cause: the inclusion bar ("named role in a declared pipeline", scoped to
app/stages and app/pipeline) structurally excluded the two things that gate and
power every turn. Defensible for enumerating the loop; wrong for explaining a
turn.

So this build adds three dimensions, each derived rather than asserted:
  config   — env vars the module reads (os.environ.get / os.getenv)
  output   — where you can see what it produced (signals, storage writes)
  chain    — the hops before run_pipeline, and the cross-cutting participants

Runs standalone against the working tree. Nothing here deploys.
"""
import ast, os, re, json, subprocess, sys

REPO = "/Users/ananth/Mobius/mobius-chat"
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/chat-dev.json"

ENV_RE = re.compile(r'os\.environ\.get\(\s*"([A-Z0-9_]+)"|os\.getenv\(\s*"([A-Z0-9_]+)"'
                    r'|os\.environ\[\s*"([A-Z0-9_]+)"\s*\]')
STORE_RE = re.compile(r'\b(save_state_full|get_state|save_[a-z_]+|insert_[a-z_]+|'
                      r'record_[a-z_]+|append_message_chunk|publish_[a-z_]+)\s*\(')

def env_of(src):
    return sorted({g for m in ENV_RE.findall(src) for g in m if g})

def stores_of(src):
    return sorted(set(STORE_RE.findall(src)))[:8]

def module_record(relpath, kind, role_hint=""):
    p = os.path.join(REPO, relpath)
    if not os.path.exists(p):
        return {"id": os.path.basename(relpath)[:-3], "path": relpath, "kind": kind,
                "loc": 0, "role": "(deleted)", "role_full": "", "api": [],
                "config": [], "writes": [], "deleted": True}
    src = open(p, encoding="utf-8", errors="replace").read()
    try:
        tree = ast.parse(src); doc = (ast.get_docstring(tree) or "").strip()
        api = [n.name + "()" for n in tree.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and not n.name.startswith("_")][:8]
    except SyntaxError:
        doc, api = "", []
    return {
        "id": os.path.basename(relpath)[:-3],
        "path": relpath,
        "kind": kind,
        "loc": len(src.splitlines()),
        "role": doc.split("\n")[0] if doc else (role_hint or "(no docstring)"),
        "role_full": doc[:700],
        "api": api,
        "config": env_of(src),
        "writes": stores_of(src),
    }

# Module paths for nodes whose file the refactor deleted. Kept explicitly
# rather than inferred: a node that disappears because someone RENAMED a file
# must fail loudly, not be quietly tombstoned.
_TOMBSTONE_PATHS = {
    "clarify": "app/stages/clarify.py",
    "classify": "app/stages/classify.py",
    "plan": "app/stages/plan.py",
    "resolve": "app/stages/resolve.py",
    "continuity": "app/stages/continuity.py",
    "credentialing_envelope": "app/pipeline/credentialing_envelope.py",
}


_COVERAGE = {}
try:
    import json as _j, pathlib as _pl
    _cp = _pl.Path(__file__).resolve().parents[2] / "docs" / "chat-coverage.json"
    if _cp.exists():
        _COVERAGE = {n["node"]: n for n in _j.loads(_cp.read_text()).get("nodes", [])}
except Exception:
    _COVERAGE = {}


def main():
    deleted: list[str] = []
    cat = json.load(open("/Users/ananth/Mobius/docs/chat-submodules.json"))
    by = {m["module"].split(".")[-1]: m for m in cat["submodules"]}

    # Enrich the 25 with config + storage writes, both read from the file.
    for name, m in by.items():
        p = os.path.join(REPO, m["path"])
        if not os.path.exists(p):
            # A module the refactor has already deleted. The schema must keep
            # working DURING a deletion phase, not only before and after it —
            # otherwise the diagram goes dark exactly when the code is moving.
            # The module is gone, so every measured figure the catalogue
            # carries for it is now a HISTORICAL number, not a current one.
            # Leaving loc=86 and tests=[test_clarify.py] on a node whose file
            # and test file were both deleted is the same stale-artifact bug
            # this page exists to catch — so zero them and keep the old values
            # under `was_` where the record is still useful.
            m["deleted"] = True
            m["was_loc"] = m.get("loc")
            m["was_tests"] = list(m.get("tests") or [])
            m["loc"] = 0
            m["tests"] = []
            m["telemetry"] = []
            m["callers"] = []
            m["fan_in"] = 0
            m.setdefault("config", []); m.setdefault("writes", [])
            deleted.append(m["path"])
            continue
        src = open(p, encoding="utf-8", errors="replace").read()
        m["config"] = env_of(src)
        m["writes"] = stores_of(src)

    # The hops the diagram never showed. Verified by reading the call sites:
    # api/chat.py:232 runs the PHI check before enqueue; worker/run.py:47
    # consumes and calls run_pipeline; orchestrator takes phi_gate_verdict.
    chain = [
        {"step": "POST /chat", "path": "app/api/chat.py", "line": 305,
         "what": "Accepts the turn and returns a correlation_id to poll. Nothing is answered here.",
         "config": [], "kind": "entry"},
        {"step": "PHI gate", "path": "app/skills/phi_gate.py", "line": 232,
         "what": "POSTs the message to the classifier's /message-check BEFORE anything is queued. "
                 "FAIL-CLOSED: any timeout, network error or non-200 returns block=True, so taking "
                 "the classifier offline cannot bypass the gate. The frontend pre-check fails OPEN "
                 "and is UX only; this is the authoritative layer.",
         "config": ["PHI_GATE_URL", "PHI_CLASSIFIER_URL", "PHI_GATE_TIMEOUT_SEC"],
         "kind": "gate"},
        {"step": "queue", "path": "app/queue.py", "line": None,
         "what": "The turn is enqueued; the API returns immediately. Everything after this runs in "
                 "the worker, not the request.",
         "config": [], "kind": "hop"},
        {"step": "worker", "path": "app/worker/run.py", "line": 47,
         "what": "Consumes the queue, arms the turn deadline, and calls run_pipeline. The PHI "
                 "verdict rides along in the payload and is handed to the pipeline.",
         "config": ["MOBIUS_TURN_DEADLINE_S"], "kind": "hop"},
        {"step": "run_pipeline", "path": "app/pipeline/orchestrator.py", "line": 434,
         "what": "Everything the schema below draws happens inside this call.",
         "config": [], "kind": "pipeline"},
    ]

    # The integrator is three LLM calls, not one step. The names are the
    # module's own (integrator_a, Call B, Call C), so the split is read from
    # the code rather than imposed on it.
    integrate_passes = [
        {"id": "Call A", "label": "integrator_a", "what": "First answer — core synthesis into the answer card.",
         "skippable": "Skipped when dynamic enrichment fires and the answer is already sufficient."},
        {"id": "Call B", "label": "critic pass", "what": "Critique and citations.", "skippable": None},
        {"id": "Call C", "label": "enricher", "what": "Produces display_summary — the fuller prose behind the card.",
         "skippable": None},
    ]
    integrate_modes = {
        "mode": "MOBIUS_INTEGRATOR_MODE forces parallel|sequential; "
                "MOBIUS_INTEGRATOR_PARALLEL_PCT samples when unset. Default sequential, 0%.",
        "dynamic_enrichment": "MOBIUS_DYNAMIC_ENRICHMENT_PCT samples per turn; parallel path only. "
                              "When react_loop's sufficiency check passes, Call A is skipped.",
    }

    # Cross-cutting: not steps, but under every step that generates.
    cross = [module_record("app/services/llm_manager.py", "cross-cutting"),
             module_record("app/skills/phi_gate.py", "cross-cutting"),
             module_record("app/services/retrieval_budget.py", "cross-cutting"),
             # Two decision modules Ananth called out (2026-09-08) as "definitely
             # off". Neither is a step in the drawn flow — that is exactly the
             # finding — so they are attached here to get their own node rather
             # than staying invisible because the flow parser cannot see them.
             module_record("app/state/jurisdiction.py", "cross-cutting"),
             module_record("app/state/clarification.py", "cross-cutting"),
             # The epicentre of the built-but-never-wired class (Ananth 2026-09-08:
             # "log it as a systemic finding"). Given its own node because the
             # pattern is most measurable here.
             module_record("app/communication/emit_envelope.py", "cross-cutting"),
             # The model bandit. Ananth 2026-09-09: "it is one of the silent yet
             # effective instruments we have" — and silent is the problem, which
             # is why it gets a node rather than staying a paragraph inside
             # llm_manager.
             module_record("app/services/model_registry.py", "cross-cutting")]
    for c in cross:
        out = subprocess.run(
            ["grep", "-rl", c["id"], "--include=*.py", "app/"],
            cwd=REPO, capture_output=True, text=True).stdout.split()
        c["callers"] = sorted({f[:-3].replace("/", ".") for f in out
                               if not f.endswith(c["path"].split("/")[-1])})[:14]
        c["fan_in"] = len(c["callers"])

    # Human content (how it works + readiness call) and mechanical readiness
    # signals are merged in here. They live apart on purpose: the signals are
    # regenerated from source and must never be hand-edited; the judgement is
    # hand-written and must never be inferred from the signals alone.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "content", "/Users/ananth/Mobius/scripts/platform/chat_node_content.py")
    C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
    content = {**C.CHAIN, **C.CROSS, **C.SUB}
    # phi_gate appears twice — as a hop in the chain and as a cross-cutting
    # module. Alias rather than duplicate the prose, so a correction lands once.
    content["phi_gate"] = content["PHI gate"]
    sig_path = "/private/tmp/claude-502/-Users-ananth-Mobius/7bd378b9-3a8f-4998-a9b3-06f2d630c20f/scratchpad/readiness.json"
    sigs = json.load(open(sig_path)) if os.path.exists(sig_path) else {}
    sig_alias = {"POST /chat": "chat_api", "PHI gate": "phi_gate", "queue": "queue",
                 "worker": "worker", "run_pipeline": "orchestrator"}

    # What the DEPLOYED service actually sets. Without this the page describes
    # code defaults and calls them behaviour — which is how both the Chat seat
    # and I said "the governor is off by default, so it never fires", when
    # deploy/dev.env sets MOBIUS_PRODUCT_PROMISE_ENABLED=true and the running
    # service has it on. A readiness review that reads defaults is fiction.
    live_path = ("/private/tmp/claude-502/-Users-ananth-Mobius/"
                 "7bd378b9-3a8f-4998-a9b3-06f2d630c20f/scratchpad/live_env.json")
    live = json.load(open(live_path))["env"] if os.path.exists(live_path) else {}

    det_path = ("/private/tmp/claude-502/-Users-ananth-Mobius/"
                "7bd378b9-3a8f-4998-a9b3-06f2d630c20f/scratchpad/node_detail.json")
    detail = json.load(open(det_path)) if os.path.exists(det_path) else {}

    def attach(key, obj):
        c = content.get(key)
        if c:
            obj["how"] = c["how"].strip()
            obj["rating"] = c["rating"]
            obj["depth"] = c["depth"]
            obj["findings"] = c["findings"]
            # `ux` is optional per node — carry it when present. It was being
            # written in the content file and silently dropped here, so every
            # "where do I manage this" answer was invisible on the page.
            if c.get("ux"):
                obj["ux"] = c["ux"]
        obj["signals"] = sigs.get(sig_alias.get(key, key), {})
            # Eval's Layer-1 coverage state, merged so the PAGE can show it. The enum
        # existed in docs/chat-coverage.json for a day with no reader — the page
        # never rendered it, so "is this node guarded?" was answerable only by
        # opening a JSON file by hand. Producer without a consumer, in the tool
        # built to find producers without consumers.
        _cov = _COVERAGE.get(key)
        if _cov:
            obj["coverage"] = _cov["state"]
            obj["coverage_tags"] = _cov.get("tags") or []
        if obj.get("deleted"):
            # A RATING IS A JUDGEMENT ABOUT LIVE CODE. Leaving green/amber/red on a
            # module that no longer exists is worse than leaving the description:
            # the description is prose a reader weighs, the rating is a badge they
            # scan. Chat Master read `credentialing_envelope` as "rated green,
            # depth=code" and correctly called it stale — the stamp I added covers
            # the how-text and never touched the badge.
            obj["rating_was"] = obj.get("rating")
            obj["rating"] = "removed"
            obj["depth"] = "removed"
            # Same rule as the catalogue fields above: a deleted module's
            # signals are history. readiness_signals already returns zeros for
            # a missing file, but the pre-computed `sigs` map may predate the
            # deletion, so force it rather than trusting whichever ran first.
            obj["signals"] = {**obj["signals"], "loc": 0, "tests": [], "emits": 0,
                              "fan_in": 0, "except_handlers": 0, "swallow": 0,
                              "bare_except": 0, "todos": 0, "deleted": True}
        obj["live_config"] = [{"name": v, "live": live.get(v, "(not set — code default)")}
                              for v in (obj.get("config") or [])]
        obj["detail"] = detail.get(key, {})

    # No module of its own — it is an if-block inline in react_loop. Synthesise
    # a record so it can be a node, and be explicit that its "file" is its host.
    by["completion_extension_gate"] = {
        "id": "completion_extension_gate",
        "module": "app.pipeline.react_loop (inline, L5077-5133)",
        "path": "app/pipeline/react_loop.py:5077-5133",
        "loc": 57, "group": "pipeline/react",
        "role": "Inline completion-critic extension gate — raises max_it for this turn.",
        "role_full": "No docstring: it is an if-block, not a module.",
        "api": [], "callers": ["app.pipeline.react_loop"], "fan_in": 1,
        "telemetry": [], "surfaces": [],
        "config": ["MOBIUS_PRODUCT_PROMISE_ENABLED", "MOBIUS_TURN_DEADLINE_S"],
        "writes": [], "observability": "mediated",
        "observability_note": ("Sets ctx.completion_critic_ran / _satisfied / _gaps, but "
                               "emits no signal and nothing renders them."),
    }

    # Key explicitly. The page used to derive it as module.split(".").pop(),
    # which produced garbage for the inline gate whose "module" is
    # "app.pipeline.react_loop (inline, L5077-5133)" — its chip then pointed at
    # nothing and clicking it silently did nothing.
    for name, m in by.items():
        m["key"] = name
        attach(name, m)
    for c in cross:
        attach(c["id"], c)
    for st in chain:
        attach(st["step"], st)

    # ── Tombstones ────────────────────────────────────────────────────────
    # A node whose MODULE is gone must not vanish from the page. The findings
    # that justified deleting it are the record of why the deletion was safe,
    # and a diff of this page is how anyone sees what a phase removed.
    #
    # This exists because I broke it: adding gen_chat_submodules.py to the
    # refresh chain (correctly — the flow was stale) meant the catalogue is now
    # rebuilt from files on disk, so five deleted modules silently dropped out
    # of the page while I was claiming they were deliberately kept. The
    # findings survived in the log; the nodes did not.
    known = set(by) | {c["id"] for c in cross} | {s["step"] for s in chain}
    for key, rec in content.items():
        if key in known:
            continue
        path = _TOMBSTONE_PATHS.get(key)
        if path is None or os.path.exists(os.path.join(REPO, path)):
            continue  # not a deleted module — a naming mismatch, leave it loud
        tomb = {
            "id": key, "key": key, "module": key, "group": "deleted",
            "path": path, "loc": 0, "role": "(deleted by the refactor)",
            "role_full": "", "api": [], "config": [], "writes": [],
            "telemetry": [], "callers": [], "fan_in": 0, "surfaces": [],
            "observability": "n/a", "deleted": True,
            "signals": {"loc": 0, "except_handlers": 0, "swallow": 0,
                        "bare_except": 0, "todos": 0, "config": [], "tests": [],
                        "path": path, "fan_in": 0, "emits": 0, "deleted": True},
        }
        attach(key, tomb)
        by[key] = tomb
        deleted.append(path)

    missing = [k for k in list(by) + [c["id"] for c in cross] + [s["step"] for s in chain]
               if k not in content]
    if missing:
        print("NO CONTENT WRITTEN FOR:", missing, file=sys.stderr)

    # Roadmap rollup — imported from the same mapping gen_roadmap.py uses, so the
    # page and the tracker cannot disagree about how many bugs a phase holds.
    roadmap = None
    try:
        from refactor_roadmap import PHASES as _RM_PHASES, RULES as _RM_RULES, OUT_OF_PROGRAM as _RM_OUT
        _counts = {p["id"]: 0 for p in _RM_PHASES}
        _outside = 0
        for _node, _rec in content.items():
            for _kind, _txt in _rec.get("findings", []):
                if _kind != "bad":
                    continue
                _t = re.sub(r"^OWNER\([a-z-]+\):\s*", "", _txt)
                _hit = next((ph for ph, nd, sub in _RM_RULES
                             if (nd is None or nd == _node) and sub in _t), None)
                if _hit:
                    _counts[_hit] += 1
                elif any(nd == _node and sub in _t for nd, sub, _b, _r in _RM_OUT):
                    _outside += 1
        roadmap = {"phases": [{**{k: p.get(k) for k in ("id", "name", "owner", "gate", "blocks")},
                               "n": _counts[p["id"]]} for p in _RM_PHASES],
                   "outside": _outside}
    except Exception as _rm_exc:
        print(f"roadmap rollup skipped: {_rm_exc}", file=sys.stderr)

    print(json.dumps({
        "generated_by": "scripts/platform/gen_chat_dev.py",
        "deleted_modules": deleted,
        "roadmap": roadmap,
        "missing_content": missing,
        "live_env_service": "mobius-chat (us-central1)",
        "integrate_passes": integrate_passes,
        "integrate_modes": integrate_modes,
        "flow": cat["flow"],
        "chain": chain,
        "cross_cutting": cross,
        "submodules": sorted(by.values(), key=lambda x: x["module"]),
        "telemetry_sink": cat["telemetry_sink"],
    }, indent=1), file=open(OUT, "w"))
    n_cfg = sum(1 for m in by.values() if m["config"])
    print(f"{len(by)} sub-modules ({n_cfg} configurable) · {len(chain)} chain steps "
          f"· {len(cross)} cross-cutting -> {OUT}")

if __name__ == "__main__":
    main()
