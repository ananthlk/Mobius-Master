#!/usr/bin/env python3
"""Mechanical production-readiness signals per module.

A red/amber/green with no evidence under it is a vibe. These are the things
that actually predict trouble, all countable from the source, so the rating
can be argued with:

  swallow      except blocks that log-and-continue or pass — the appeals
               outage shape: failure that leaves everything looking healthy
  bare_except  `except:` with no exception type at all
  loc          size; past a few thousand lines a module stops being reviewable
  tests        does a test file exist for it
  todos        TODO / FIXME / HACK / XXX
  fan_in       how many modules import it (blast radius)
  config       env vars it reads (operable without a redeploy?)
  emits        does it have telemetry of its own
"""
import ast, os, re, json, sys

REPO = "/Users/ananth/Mobius/mobius-chat"

SWALLOW = re.compile(r"except[^\n:]*:\s*(?:#[^\n]*\n\s*)*(?:pass\b|logger\.(?:warning|info|debug|exception))")
BARE = re.compile(r"except\s*:")
TODO = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
ENV = re.compile(r'os\.environ\.get\(\s*"([A-Z0-9_]+)"|os\.getenv\(\s*"([A-Z0-9_]+)"')

def tests_for(stem):
    td = os.path.join(REPO, "tests")
    if not os.path.isdir(td):
        return []
    return sorted(f for f in os.listdir(td)
                  if f.startswith("test_") and stem in f and f.endswith(".py"))

def signals(relpath):
    p = os.path.join(REPO, relpath)
    src = open(p, encoding="utf-8", errors="replace").read()
    stem = os.path.basename(relpath)[:-3]
    try:
        tree = ast.parse(src)
        handlers = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler))
    except SyntaxError:
        handlers = 0
    return {
        "loc": len(src.splitlines()),
        "except_handlers": handlers,
        "swallow": len(SWALLOW.findall(src)),
        "bare_except": len(BARE.findall(src)),
        "todos": len(TODO.findall(src)),
        "config": sorted({g for m in ENV.findall(src) for g in m if g}),
        "tests": tests_for(stem),
    }

if __name__ == "__main__":
    cat = json.load(open("/Users/ananth/Mobius/docs/chat-submodules.json"))
    out = {}
    paths = {m["module"].split(".")[-1]: m["path"] for m in cat["submodules"]}
    paths.update({
        "llm_manager": "app/services/llm_manager.py",
        "phi_gate": "app/skills/phi_gate.py",
        "chat_api": "app/api/chat.py",
        "worker": "app/worker/run.py",
        "queue": "app/queue/redis_queue.py",
        "retrieval_budget": "app/services/retrieval_budget.py",
    })
    fan = {m["module"].split(".")[-1]: m.get("fan_in", 0) for m in cat["submodules"]}
    emits = {m["module"].split(".")[-1]: len(m.get("telemetry") or []) for m in cat["submodules"]}
    for name, rel in sorted(paths.items()):
        s = signals(rel)
        s["path"] = rel
        s["fan_in"] = fan.get(name, 0)
        s["emits"] = emits.get(name, 0)
        out[name] = s
    json.dump(out, open(sys.argv[1], "w"), indent=1)
    print(f"{len(out)} modules profiled")
    hdr = f"{'module':<24}{'loc':>6}{'exc':>5}{'swal':>6}{'bare':>6}{'todo':>6}{'fan':>5}{'emit':>6}  tests"
    print(hdr); print("-"*len(hdr))
    for n, s in sorted(out.items(), key=lambda kv: -kv[1]["swallow"]):
        print(f"{n:<24}{s['loc']:>6}{s['except_handlers']:>5}{s['swallow']:>6}"
              f"{s['bare_except']:>6}{s['todos']:>6}{s['fan_in']:>5}{s['emits']:>6}  "
              f"{','.join(t.replace('test_','').replace('.py','') for t in s['tests'])[:34] or '—'}")
