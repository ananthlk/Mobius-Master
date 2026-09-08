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

def main():
    cat = json.load(open("/Users/ananth/Mobius/docs/chat-submodules.json"))
    by = {m["module"].split(".")[-1]: m for m in cat["submodules"]}

    # Enrich the 25 with config + storage writes, both read from the file.
    for name, m in by.items():
        p = os.path.join(REPO, m["path"])
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
             module_record("app/services/retrieval_budget.py", "cross-cutting")]
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

    def attach(key, obj):
        c = content.get(key)
        if c:
            obj["how"] = c["how"].strip()
            obj["rating"] = c["rating"]
            obj["depth"] = c["depth"]
            obj["findings"] = c["findings"]
        obj["signals"] = sigs.get(sig_alias.get(key, key), {})

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

    missing = [k for k in list(by) + [c["id"] for c in cross] + [s["step"] for s in chain]
               if k not in content]
    if missing:
        print("NO CONTENT WRITTEN FOR:", missing, file=sys.stderr)

    print(json.dumps({
        "generated_by": "scripts/platform/gen_chat_dev.py",
        "missing_content": missing,
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
