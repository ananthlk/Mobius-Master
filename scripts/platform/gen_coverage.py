"""Layer 1 of Eval's coverage signal: REACHABILITY, not filename matching.

Eval's ruling, docs/p2b-latency-telemetry-eval.md Q5:

  Replace filename match with two layers. Layer 1 (mechanical, ship now):
  AST-walk each collected test's import/call graph and mark whether it
  actually CALLS the node's entrypoint -> reached / not-reached. This kills
  both filename lies at once — a file named for a node that never calls it,
  and a node exercised only by a differently-named file.

  Layer 2 (Eval audits): a per-test marker naming the contract it guards,
  @pytest.mark.guards("queue:no_silent_loss"). Reachability proves EXECUTED,
  not that the test would FAIL if the contract regressed.

  Render as an enum, fail-loud, only the top state shows a tick:
    ABSENT          not reached
    PERIPHERAL      reached, no tag
    GUARDED         reached + verified tag
    ASSERTS-NOTHING reached + tag but the assertion cannot catch the defect

This file implements Layer 1 and the `guards` marker collection. GUARDED
requires Eval's verification of the tag, so a tag alone renders as
TAGGED-UNVERIFIED until they sign it — a tag nobody audited is exactly the
"reports connected while nothing flows" shape this program keeps finding.

FIRST IMPLEMENTATION WAS WRONG AND IS RECORDED HERE. I built reachability as
a TRANSITIVE import closure — a test importing the orchestrator "reaches"
every module the orchestrator imports. That returned 24 of 24 nodes reached,
0 ABSENT, which is not a coverage signal at all: it says "some test somewhere
imports something that eventually imports this", which is true of nearly every
module in a connected codebase. A metric that cannot come out negative is the
"filter that makes an answer look complete" failure, and I shipped one.

Eval's wording was precise and I widened it: "does it actually CALL the node's
entrypoint". So reachability here is DIRECT: a test reaches a node when it
imports that node's module directly, and CALLS a public name defined in it.
Import-without-call is recorded separately — it is the weaker signal, and it
is the same distinction as "an import edge is not a consumption edge".
"""
import ast, json, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
CHAT = os.path.join(ROOT, "mobius-chat")
sys.path.insert(0, HERE)


def app_imports(path):
    """The app.* modules a file imports directly."""
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except (SyntaxError, FileNotFoundError):
        return set(), set()
    mods, guards = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("app"):
            mods.add(n.module)
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith("app"):
                    mods.add(a.name)
        # @pytest.mark.guards("node:contract")
        elif isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == "guards":
                for arg in n.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        guards.add(arg.value)
    return mods, guards


def public_names(path):
    """Public top-level defs in a module — its entrypoints."""
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except (SyntaxError, FileNotFoundError):
        return set()
    return {n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and not n.name.startswith("_")}


def called_names(path):
    """Every name this file calls, plus attribute calls (mod.fn())."""
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except (SyntaxError, FileNotFoundError):
        return set()
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
        # patch("app.x.y.fn") / monkeypatch targets name the entrypoint too
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and "." in n.value:
            out.add(n.value.rsplit(".", 1)[-1])
    return out



def module_of(path):
    return os.path.relpath(path, CHAT)[:-3].replace("/", ".")


# ── the app-side import graph ────────────────────────────────────────────
graph, PUBLIC = {}, {}
for dirpath, _, files in os.walk(os.path.join(CHAT, "app")):
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(dirpath, f)
            m = module_of(p)
            graph[m], _ = app_imports(p)
            PUBLIC[m] = public_names(p)

# ── walk the tests ───────────────────────────────────────────────────────
reached = collections.defaultdict(set)   # app module -> {test files}
direct  = collections.defaultdict(set)   # app module -> {test files importing it directly}
tags    = collections.defaultdict(set)   # contract id -> {test files}
tdir = os.path.join(CHAT, "tests")
n_tests = 0
for dirpath, _, files in os.walk(tdir):
    for f in files:
        if not (f.startswith("test_") and f.endswith(".py")):
            continue
        n_tests += 1
        p = os.path.join(dirpath, f)
        mods, guards = app_imports(p)
        for g in guards:
            tags[g].add(f)
        calls = called_names(p)
        for m in mods:
            direct[m].add(f)
            # CALLS the node's entrypoint — Eval's actual bar
            if calls & PUBLIC.get(m, set()):
                reached[m].add(f)

# ── map nodes to modules ─────────────────────────────────────────────────
DATA = os.path.join(ROOT, "docs", "chat-schema", "chat-dev.json")
d = json.load(open(DATA))
nodes = []
for s in d["submodules"] + d["cross_cutting"]:
    key = s.get("key") or s.get("id")
    path = s.get("path") or ""
    if not path.endswith(".py"):
        continue
    mod = path[:-3].replace("/", ".")
    if s.get("deleted"):
        nodes.append({"node": key, "state": "REMOVED", "module": mod,
                      "direct": 0, "reached": 0, "tags": []})
        continue
    dt, rt = direct.get(mod, set()), reached.get(mod, set())
    ntags = sorted(t for t in tags if t.split(":")[0] == key)
    if not rt:
        state = "IMPORTED-NOT-CALLED" if dt else "ABSENT"
    elif not ntags:
        state = "PERIPHERAL"
    else:
        state = "TAGGED-UNVERIFIED"   # GUARDED only after Eval audits the tag
    nodes.append({"node": key, "state": state, "module": mod,
                  "direct": len(dt), "reached": len(rt), "tags": ntags,
                  "rating": s.get("rating")})

order = {"ABSENT": 0, "IMPORTED-NOT-CALLED": 1, "PERIPHERAL": 2, "TAGGED-UNVERIFIED": 2, "GUARDED": 3, "REMOVED": 9}
nodes.sort(key=lambda x: (order.get(x["state"], 5), x["node"]))
counts = collections.Counter(n["state"] for n in nodes)

out = {"generated_by": "scripts/platform/gen_coverage.py",
       "layer": "1 — reachability (Eval's Q5 ruling); Layer 2 tags are collected, "
                "and GUARDED requires Eval's audit of the tag",
       "tests_scanned": n_tests, "counts": dict(counts), "nodes": nodes,
       "tags_found": {k: sorted(v) for k, v in tags.items()}}
json.dump(out, open(os.path.join(ROOT, "docs", "chat-coverage.json"), "w"), indent=1)

print(f"scanned {n_tests} test files · {len(nodes)} nodes")
for st in ("ABSENT", "IMPORTED-NOT-CALLED", "PERIPHERAL", "TAGGED-UNVERIFIED", "GUARDED", "REMOVED"):
    if counts.get(st):
        print(f"  {st:18} {counts[st]}")
print(f"\ncontract tags found: {len(tags)}"
      + ("" if tags else "  (none yet — Layer 2 not started)"))
reds = [n for n in nodes if n.get("rating") == "red"
        and n["state"] in ("ABSENT", "IMPORTED-NOT-CALLED")]
if reds:
    print(f"\nRED nodes no test CALLS ({len(reds)}):")
    for n in reds:
        print(f"  {n['node']:22} {n['module']}")
print("\n-> docs/chat-coverage.json")
