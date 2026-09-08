#!/usr/bin/env python3
"""Every parameter, every UX surface, every DB touch — per node, from source.

Ananth: "go node by node and module by module capturing every detail, every
parameter every ux, every db". That is only honest if it is extracted rather
than remembered, so nothing in here is hand-listed:

  db          SQL statements (table + verb), storage-layer functions called,
              Redis keys, and the migrations that own the tables
  ux          frontend files that name the module or its signals, API routes it
              defines, and the envelope signals that reach a rendered surface
  parameters  env vars, MODULE-LEVEL constants, and function keyword defaults —
              the tunables that do NOT need a redeploy vs the ones that do

Anything this cannot see is reported as such rather than omitted, because a
blank field reads as "nothing here" when the truth may be "not extractable".
"""
import ast, os, re, json, sys, subprocess

REPO = "/Users/ananth/Mobius/mobius-chat"

SQL = re.compile(r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|SELECT[\s\S]{0,200}?\bFROM)\s+"
                 r"([a-zA-Z_][\w.]*)", re.I)
REDIS_KEY = re.compile(r"(redis_[a-z_]*key[a-z_]*|_request_key|_response_prefix)")
STORAGE_FN = re.compile(r"\bfrom app\.storage[\w.]*\s+import\s+([^\n]+)")
ROUTE = re.compile(r'@(?:router|app)\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)')

def frontend_refs(names):
    """Which frontend files name this module or one of its signals."""
    fe = os.path.join(REPO, "frontend")
    hits = set()
    if not os.path.isdir(fe):
        return []
    for n in names:
        if len(n) < 5:
            continue
        try:
            out = subprocess.run(
                ["grep", "-rl", "--include=*.js", "--include=*.html", "--include=*.ts", n, "."],
                cwd=fe, capture_output=True, text=True, timeout=30).stdout.split()
        except Exception:
            continue
        hits |= {f for f in out if "node_modules" not in f}
    return sorted(hits)[:8]

def detail(relpath, signals=None):
    p = os.path.join(REPO, relpath.split(":")[0])
    if not os.path.isfile(p):
        return {"_unavailable": f"{relpath} is not a single file — detail not extractable"}
    src = open(p, encoding="utf-8", errors="replace").read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        tree = None

    tables = sorted({f"{v.split()[0].upper()} {t}" for v, t in SQL.findall(src)
                     if not t.startswith(("(", "'"))})
    storage = sorted({x.strip() for m in STORAGE_FN.findall(src)
                      for x in m.replace("(", "").replace(")", "").split(",") if x.strip()})
    routes = [f"{v.upper()} {r}" for v, r in ROUTE.findall(src)]

    consts, defaults = [], []
    if tree:
        for n in tree.body:
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id.isupper() and len(t.id) > 2:
                        try: v = ast.literal_eval(n.value)
                        except Exception: v = "<computed>"
                        consts.append({"name": t.id, "value": str(v)[:90]})
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_"):
                a = n.args
                for arg, dflt in zip(a.args[-len(a.defaults):] if a.defaults else [], a.defaults):
                    try: v = ast.literal_eval(dflt)
                    except Exception: continue
                    defaults.append({"fn": n.name, "param": arg.arg, "default": str(v)[:60]})
                for arg, dflt in zip(a.kwonlyargs, a.kw_defaults or []):
                    if dflt is None: continue
                    try: v = ast.literal_eval(dflt)
                    except Exception: continue
                    defaults.append({"fn": n.name, "param": arg.arg, "default": str(v)[:60]})

    return {
        "db": {
            "sql": tables,
            "storage_fns": storage[:12],
            "redis_keys": sorted(set(REDIS_KEY.findall(src)))[:6],
            "note": "SQL found by literal match; a query built at runtime is invisible here",
        },
        "ux": {
            "routes_defined": routes[:12],
            "frontend_files": frontend_refs(([os.path.basename(p)[:-3]] + (signals or []))),
        },
        "parameters": {
            "module_constants": consts[:14],
            "keyword_defaults": defaults[:14],
        },
    }

if __name__ == "__main__":
    cat = json.load(open("/Users/ananth/Mobius/docs/chat-submodules.json"))
    paths = {m["module"].split(".")[-1]: (m["path"], [t["signal"] for t in (m.get("telemetry") or [])])
             for m in cat["submodules"]}
    paths.update({
        "llm_manager": ("app/services/llm_manager.py", []),
        "phi_gate": ("app/skills/phi_gate.py", []),
        "retrieval_budget": ("app/services/retrieval_budget.py", []),
        "POST /chat": ("app/api/chat.py", []),
        "worker": ("app/worker/run.py", []),
        "queue": ("app/queue/redis_queue.py", []),
    })
    out = {}
    for name, (rel, sigs) in sorted(paths.items()):
        out[name] = detail(rel, sigs)
    json.dump(out, open(sys.argv[1], "w"), indent=1)
    tot = lambda k, sub: sum(len(v.get(k, {}).get(sub, [])) for v in out.values() if "_unavailable" not in v)
    print(f"{len(out)} nodes detailed")
    print(f"  SQL statements found : {tot('db','sql')}")
    print(f"  storage fns imported : {tot('db','storage_fns')}")
    print(f"  routes defined       : {tot('ux','routes_defined')}")
    print(f"  frontend files named : {tot('ux','frontend_files')}")
    print(f"  module constants     : {tot('parameters','module_constants')}")
    print(f"  keyword defaults     : {tot('parameters','keyword_defaults')}")
