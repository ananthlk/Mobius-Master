#!/usr/bin/env python3
"""Evidence for the chat pipeline's sub-modules, read out of the code.

Scope is the bar Ananth set: a module with a NAMED ROLE IN A DECLARED PIPELINE.
For mobius-chat that is app/stages (whose __init__ states the contract in
words), app/pipeline, and app/pipeline/react.

This collects evidence only. It does not decide what a module means — that is
written down once, by hand, against what the code shows, and re-checked by
re-running this. Guessing the meaning is how the last framework went wrong.
"""
import ast, os, re, json

REPO = "/Users/ananth/Mobius/mobius-chat"
DIRS = ["app/stages", "app/stages/agents", "app/pipeline", "app/pipeline/react"]

def public_defs(tree):
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_"):
            out.append(n.name + "()")
        elif isinstance(n, ast.ClassDef) and not n.name.startswith("_"):
            out.append(n.name)
    return out

def main():
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
            mods[name] = {
                "id": f[:-3],
                "module": name,
                "path": os.path.relpath(fp, REPO),
                "loc": src.count("\n") + 1,
                "doc": (ast.get_docstring(tree) or "").strip(),
                "public": public_defs(tree)[:12],
                "callers": [],
            }
    # who imports whom, across the whole app
    approot = os.path.join(REPO, "app")
    for d, dirs, fs in os.walk(approot):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", "node_modules")]
        for f in fs:
            if not f.endswith(".py"): continue
            fp = os.path.join(d, f)
            caller = os.path.relpath(fp, REPO)[:-3].replace("/", ".")
            try: src = open(fp, encoding="utf-8", errors="replace").read()
            except Exception: continue
            for name, m in mods.items():
                leaf = name.rsplit(".", 1)[1]
                pat = (rf"from\s+{re.escape(name)}\s+import|import\s+{re.escape(name)}\b"
                       rf"|from\s+[\w.]*\s+import\s+[^\n]*\b{leaf}\b")
                if caller != name and re.search(pat, src):
                    m["callers"].append(caller)
    for m in mods.values():
        m["callers"] = sorted(set(m["callers"]))
        m["fan_in"] = len(m["callers"])
    print(json.dumps(list(mods.values()), indent=1))

if __name__ == "__main__":
    main()
