#!/usr/bin/env python3
"""Generate the chat pipeline's sub-module catalogue, from the code.

The bar (Ananth, 2026-09-08): a module with a NAMED ROLE IN A DECLARED
PIPELINE. For mobius-chat that is app/stages — whose __init__ states the
contract in words — plus app/pipeline and app/pipeline/react.

Each entry carries the three marks Ananth asked for, and every one is read
out of the source rather than typed here:

  usage      which modules import it, and which declared stage it belongs to
  telemetry  which Signal values it emits; envelopes persist to
             chat_turns.thinking_log
  ux         the tier the signal taxonomy assigns that signal — promoted to
             task-manager, diagnostic panel, user-visible progress, or none

Re-running this is how the catalogue stays true. Nothing is hand-listed, so
nothing can silently rot the way the agent-seat framework did.
"""
import ast, os, re, json

REPO = "/Users/ananth/Mobius/mobius-chat"
DIRS = ["app/stages", "app/stages/agents", "app/pipeline", "app/pipeline/react"]
ENV = "app/communication/emit_envelope.py"

def signal_taxonomy():
    """Parse the Signal Literal with its trailing comments — the comments are
    the tier, and they are the only place that distinction is written down."""
    src = open(os.path.join(REPO, ENV), encoding="utf-8").read()
    blk = re.search(r"Signal\s*=\s*Literal\[(.*?)\n\]", src, re.S).group(1)
    tier = "chat-side"
    out = {}
    for line in blk.split("\n"):
        h = re.search(r"──\s*(.+?)\s*──", line)
        if h:
            t = h.group(1).lower()
            if "promoted" in t: tier = "promoted"
            elif "chat-side" in t: tier = "chat-side"
            elif "thinking" in t: tier = "thinking-chain"
            elif "personal" in t: tier = "thinking-chain"
            continue
        m = re.match(r'\s*"([a-z_]+)",\s*(?:#\s*(.*))?', line)
        if m:
            out[m.group(1)] = {"tier": tier, "note": (m.group(2) or "").strip()}
    return out

def makers():
    """make_* constructor -> the signal it stamps. Read from the constructor
    bodies, so a renamed helper cannot drift from this map."""
    src = open(os.path.join(REPO, ENV), encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"^def (make_\w+)\((.*?)^(?=def |\Z)", src, re.S | re.M):
        sig = re.search(r'signal\s*=\s*"([a-z_]+)"', m.group(0))
        if sig: out[m.group(1)] = sig.group(1)
    return out

MAKERS = {}
EMITTERS = set()

def ux_for(sig, meta):
    n = meta["note"].lower()
    if meta["tier"] == "promoted":      return "task-manager dashboard"
    if "diagnostic ui panel" in n:      return "diagnostic panel"
    if meta["tier"] == "thinking-chain":return "thinking chain (user-visible)"
    if "ui decoration" in n:            return "thinking chain (user-visible)"
    return "trace only"


def flow():
    """The loop's shape, walked with ast rather than guessed from indentation.

    An earlier version read the source line by line and decided which block a
    call sat in by comparing indent widths. It got run_integrate wrong twice:
    the call is indented 12, but inside a `try:` that sits AFTER the
    if/else — not inside the else. The Chat seat caught it. Indentation does
    not tell you the enclosing block; the parse tree does.

    So: find run_pipeline, find the `if use_react:` node, and collect the
    run_*() calls that appear before it, in its body, in its orelse, and in
    the statements that follow it at the same level. That last bucket is the
    one the heuristic could not see, and it is where run_integrate lives —
    it runs on BOTH paths, unless react_loop set ctx.react_bypass_integrate.
    """
    path = os.path.join(REPO, "app/pipeline/orchestrator.py")
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    STAGE_CALLS = {"run_state_load", "run_classify", "run_plan", "run_clarify",
                   "run_resolve", "run_integrate", "run_react"}

    def calls_in(nodes):
        out = []
        for n in nodes:
            for c in ast.walk(n):
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) \
                   and c.func.id in STAGE_CALLS:
                    out.append({"fn": c.func.id, "line": c.lineno})
        seen, uniq = set(), []
        for c in sorted(out, key=lambda x: x["line"]):
            if c["fn"] not in seen:
                seen.add(c["fn"]); uniq.append(c)
        return uniq

    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == "run_pipeline"), None)
    if fn is None:
        raise SystemExit("run_pipeline not found — the parse assumption is stale")

    # The branch is NOT at the top level of run_pipeline: it is nested inside a
    # try. And a different `if use_react_override is not None:` sits above it,
    # which a substring match on the dumped test happily picks first. So: match
    # the test exactly (a bare Name `use_react`), search the whole function, and
    # find the enclosing block by parent map — the siblings after the branch are
    # what matters, and that list is only knowable from the parent.
    parent, container = {}, {}
    for node in ast.walk(fn):
        for field, val in ast.iter_fields(node):
            if isinstance(val, list):
                for child in val:
                    if isinstance(child, ast.AST):
                        parent[child] = node
                        container[child] = val

    branch = next((n for n in ast.walk(fn)
                   if isinstance(n, ast.If) and isinstance(n.test, ast.Name)
                   and n.test.id == "use_react"), None)
    if branch is None:
        raise SystemExit("`if use_react:` not found — the parse assumption is stale")

    body = container[branch]
    idx = body.index(branch)

    pre   = calls_in(body[:idx])
    react = calls_in(branch.body)
    classic = calls_in(branch.orelse)
    post  = calls_in(body[idx + 1:])

    # Accessed as getattr(ctx, "react_bypass_integrate", False) — a string
    # constant, not an Attribute node, so an ast attribute walk finds nothing.
    guard = [i for i, l in enumerate(src.split("\n"), 1)
             if "react_bypass_integrate" in l and fn.lineno <= i]

    rl = os.path.join(REPO, "app/pipeline/react_loop.py")
    rsrc = open(rl, encoding="utf-8").read().split("\n")
    def cite(pat):
        for i, l in enumerate(rsrc, 1):
            if re.search(pat, l, re.I): return i
        return None

    return {
        "entry": "POST /chat",
        "shared_pre": [c["fn"] for c in pre],
        "branch_on": "use_react",
        "branch_line": branch.lineno,
        "react_path": [c["fn"] for c in react],
        "classic_path": [c["fn"] for c in classic],
        "shared_post": [c["fn"] for c in post],
        "shared_post_guard": ("ctx.react_bypass_integrate — set in react_loop, skips the "
                              "integrator and publishes the ReAct answer directly"
                              if guard else None),
        "shared_post_guard_lines": guard,
        "exit": "publish",
        "react_phases": [
            {"phase": "Round 0", "modules": ["round0"],
             "cite": cite(r"Round 0: system_context short-circuit"),
             "note": "Short-circuits the loop when the caller already did the work."},
            {"phase": "Reason", "modules": ["prompts", "tool_manifest", "capabilities", "parsing"],
             "cite": cite(r"ReAct loop: Reason .* Act .* Observe"),
             "note": "Builds the planner prompt and parses the decision back out."},
            {"phase": "Act", "modules": ["react_retry_guard", "curator_tools"],
             "cite": cite(r"block repeat call if"),
             "note": "Dispatches tools, and refuses a repeat of a call that already failed."},
            {"phase": "Observe", "modules": ["critic", "governor", "feedback_signal", "completion_extension_gate"],
             "cite": cite(r"Critic gate"),
             "note": "Audits the draft against sources and decides whether to go round again."},
        ],
        "note": ("Walked with ast. run_integrate is NOT classic-only: it sits after the "
                 "if/else and runs on both paths unless react_loop set "
                 "ctx.react_bypass_integrate. Corrected 2026-09-08 after the Chat seat "
                 "caught the earlier indentation-based reading."),
    }


def main():
    global MAKERS
    MAKERS = makers()
    tax = signal_taxonomy()
    # A maker may stamp a signal the Literal block does not list; keep it
    # rather than dropping it, and say so in the record.
    for sig in MAKERS.values():
        tax.setdefault(sig, {"tier": "chat-side", "note": "(not in Signal literal)"})
    stages = {}
    sm = os.path.join(REPO, "app/pipeline/stages.py")
    for k, v in re.findall(r'^([A-Z_]+)\s*=\s*"([a-z_]+)"', open(sm).read(), re.M):
        stages[v] = k

    mods = {}
    for d in DIRS:
        p = os.path.join(REPO, d)
        if not os.path.isdir(p): continue
        for f in sorted(os.listdir(p)):
            if not f.endswith(".py") or f == "__init__.py": continue
            fp = os.path.join(p, f)
            src = open(fp, encoding="utf-8", errors="replace").read()
            try: tree = ast.parse(src)
            except SyntaxError: continue
            name = os.path.relpath(fp, REPO)[:-3].replace("/", ".")
            doc = (ast.get_docstring(tree) or "").strip()
            # Two ways a module emits: the signal string literally, or a
            # make_* constructor. Matching only the string under-counted
            # badly — critic.py emits via make_critic_flagged and named no
            # signal at all.
            emitted = {s for s in tax if re.search(rf'"{s}"', src)}
            emitted |= {sig for mk, sig in MAKERS.items()
                        if re.search(rf"\b{mk}\s*\(", src)}
            emitted = sorted(emitted)
            api = [n.name + "()" for n in tree.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and not n.name.startswith("_")]
            api += [n.name for n in tree.body
                    if isinstance(n, ast.ClassDef) and not n.name.startswith("_")]
            mods[name] = {
                "id": name.replace(".", "-"),
                "module": name,
                "group": d.replace("app/", ""),
                "path": os.path.relpath(fp, REPO),
                "loc": len(src.splitlines()),
                "role": doc.split("\n")[0].strip() or "(no docstring)",
                "role_full": doc[:600],
                "stage": next((s for s in stages if f[:-3] == s), None),
                "api": api[:10],
                "telemetry": [{"signal": s, "tier": tax[s]["tier"],
                               "surface": ux_for(s, tax[s])} for s in emitted],
                "callers": [],
            }

    approot = os.path.join(REPO, "app")
    for d, dirs, fs in os.walk(approot):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", "node_modules")]
        for f in fs:
            if not f.endswith(".py"): continue
            fp = os.path.join(d, f)
            caller = os.path.relpath(fp, REPO)[:-3].replace("/", ".")
            src = open(fp, encoding="utf-8", errors="replace").read()
            for name, m in mods.items():
                leaf = name.rsplit(".", 1)[1]
                if caller == name: continue
                if re.search(rf"from\s+{re.escape(name)}\s+import|import\s+{re.escape(name)}\b"
                             rf"|from\s+[\w.]*(?:pipeline|stages)[\w.]*\s+import[^\n]*\b{leaf}\b", src):
                    m["callers"].append(caller)
    global EMITTERS
    EMITTERS = {n for n, m in mods.items() if m["telemetry"]}
    for m in mods.values():
        m["callers"] = sorted(set(m["callers"]))
        m["fan_in"] = len(m["callers"])
        m["surfaces"] = sorted({t["surface"] for t in m["telemetry"]})
        # The finding this generator surfaced: most pipeline sub-modules do
        # not emit. react_loop and orchestrator emit on their behalf, so the
        # sub-module has no telemetry identity of its own — you cannot ask
        # "how often did round0 short-circuit?" of the trace. Recorded per
        # module rather than left blank, because blank reads as "nothing to
        # see" when the truth is "not independently observable".
        if m["telemetry"]:
            m["observability"] = "self-emitting"
            m["observability_note"] = (
                "Emits its own signals; visible in chat_turns.thinking_log "
                "under its own name.")
        else:
            emitters = [c for c in m["callers"] if c in EMITTERS]
            m["observability"] = "mediated"
            m["observability_note"] = (
                "Emits nothing. Observable only through "
                + (", ".join(emitters) if emitters else "its callers")
                + " — its behaviour has no telemetry identity of its own.")

    print(json.dumps({
        "generated_by": "scripts/platform/gen_chat_submodules.py",
        "service": "mobius-chat",
        "bar": "named role in a declared pipeline",
        "declared_stages": list(stages),
        "flow": flow(),
        "telemetry_sink": "chat_turns.thinking_log (EmitEnvelope, discriminated by `signal`)",
        "signal_taxonomy_size": len(tax),
        "submodules": sorted(mods.values(), key=lambda x: (x["group"], x["module"])),
    }, indent=1))

if __name__ == "__main__":
    main()
