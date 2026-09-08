#!/usr/bin/env python3
"""Find the sub-modules inside a service, from the code.

A module earns a place on the platform page when it has a life of its own —
the three marks Ananth named: usage, telemetry, UX.

  usage      other modules import it (fan-in), and/or it is reachable from a
             declared pipeline stage
  telemetry  it names a field or table that ends up in a persisted record
  ux         its output reaches a surface — a router, a template, a static page

Nothing here is hand-listed. Re-running it is how the catalogue stays true;
that is the whole point, since the last framework rotted because it was typed.
"""
import ast, os, re, json, sys
from collections import defaultdict

TELEM_HINTS = re.compile(
    r"INSERT\s+INTO\s+(\w+)|UPDATE\s+(\w+)\s+SET|record_\w+|emit_\w+|"
    r"log_event|telemetry|_decisions\b|chat_turns|prompt_blocks|metrics\b")
UX_HINTS = re.compile(r"APIRouter|@router\.|@app\.(get|post|put|delete)|"
                      r"TemplateResponse|HTMLResponse|FileResponse|static")

def modname(root, path):
    rel = os.path.relpath(path, root)
    return rel[:-3].replace(os.sep, ".").removesuffix(".__init__")

def scan(repo, approot):
    root = os.path.join(repo, approot)
    files = []
    for d, dirs, fs in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", "tests", ".venv", "node_modules")]
        for f in fs:
            if f.endswith(".py"):
                files.append(os.path.join(d, f))
    mods, imports = {}, defaultdict(set)
    pkg_root = os.path.dirname(root)
    for p in files:
        try: src = open(p, encoding="utf-8", errors="replace").read()
        except Exception: continue
        name = modname(pkg_root, p)
        telem = sorted({m for g in TELEM_HINTS.findall(src) for m in g if m} |
                       ({"<telemetry-call>"} if re.search(r"record_\w+|emit_\w+|log_event", src) else set()))
        mods[name] = {
            "module": name,
            "path": os.path.relpath(p, repo),
            "loc": src.count("\n") + 1,
            "doc": (ast.get_docstring(ast.parse(src)) or "").strip().split("\n")[0][:150]
                   if src.strip() else "",
            "telemetry": telem[:6],
            "ux": bool(UX_HINTS.search(src)),
            "fan_in": 0,
        }
        for m in re.finditer(r"^\s*from\s+([\w.]+)\s+import|^\s*import\s+([\w.]+)", src, re.M):
            imports[name].add((m.group(1) or m.group(2)))
    for src_mod, targets in imports.items():
        for t in targets:
            if t in mods and t != src_mod:
                mods[t]["fan_in"] += 1
    return mods

def parse_ast_safe(p):
    try: return ast.parse(open(p, encoding="utf-8", errors="replace").read())
    except Exception: return None

if __name__ == "__main__":
    out = {}
    for repo, approot in [(a.split(":")[0], a.split(":")[1]) for a in sys.argv[1:]]:
        out[repo] = scan(repo, approot)
    print(json.dumps(out, indent=1))
