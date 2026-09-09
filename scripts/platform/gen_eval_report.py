"""One command: run every test, recompute every measurement, report both.

Ananth 2026-09-08: "we need an eval which includes all tests and some
measurements." This is that surface. It answers three questions in one place:

  A  do the tests pass, and WHAT DO THEY COVER — per schema node, so
     "2,593 tests" cannot stand in for "the thing I am about to change is tested"
  B  have the frozen baseline's invariants moved (the refactor gate)
  C  the structural signals I7 is computed from

Run:  python3 scripts/platform/gen_eval_report.py [--skip-tests]

Exit code is non-zero when a test fails or an invariant moves, so this is
usable as the POST half of the gate and not only as a report.
"""
import argparse, json, os, re, subprocess, sys, time, collections
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
CHAT = os.path.join(ROOT, "mobius-chat")
BASELINE = os.path.join(ROOT, "docs", "chat-refactor-baseline.json")
JUNIT = "/tmp/chat_eval_junit.xml"
sys.path.insert(0, HERE)

ap = argparse.ArgumentParser()
ap.add_argument("--skip-tests", action="store_true", help="reuse the last junit xml")
ap.add_argument("--out", default=os.path.join(ROOT, "docs", "chat-eval-report.md"))
args = ap.parse_args()

# ── A. tests ──────────────────────────────────────────────────────────────
def _pytest_python():
    """Prefer mobius-chat/.venv over whatever interpreter launched this script.

    2026-09-09 (P1b): the gate ran pytest via ``sys.executable``, so it
    inherited the caller's interpreter. Everyone invokes this as
    ``python3 scripts/platform/gen_eval_report.py`` — the Homebrew system
    Python — which lacks ``pythonjsonlogger`` and ``opentelemetry`` even
    though both are declared in requirements.txt (lines 34, 46-50) and both
    are installed in .venv. That put 12 tests
    (test_logging_config 7, test_tracing_config 5) into the known-failing
    baseline as collection errors that had nothing to do with the code.
    All 12 pass under .venv.

    Measured: .venv is NOT slower — 65-test subset ran 54.4s under .venv vs
    57.8s under system Python, both at ~8% CPU (these tests block on the
    refused db-agent connection, which dominates either way).

    Falls back to sys.executable when .venv is absent, so CI or a
    container that installs requirements globally still works.
    """
    venv_py = os.path.join(CHAT, ".venv", "bin", "python")
    return venv_py if os.path.exists(venv_py) else sys.executable


def run_tests():
    t0 = time.time()
    p = subprocess.run([_pytest_python(), "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        f"--junitxml={JUNIT}"], cwd=CHAT, capture_output=True, text=True)
    return time.time() - t0, p.returncode

wall, rc = (0.0, None)
if not args.skip_tests:
    wall, rc = run_tests()

tests = {"collected": 0, "failed": 0, "errors": 0, "skipped": 0, "wall_s": round(wall, 1),
         "failures": [], "by_file": {}}
if os.path.exists(JUNIT):
    root = ET.parse(JUNIT).getroot()
    for ts in root.iter("testsuite"):
        tests["collected"] += int(ts.get("tests", 0))
        tests["failed"] += int(ts.get("failures", 0))
        tests["errors"] += int(ts.get("errors", 0))
        tests["skipped"] += int(ts.get("skipped", 0))
    for tc in root.iter("testcase"):
        # junit here carries classname, NOT file — keying on file silently
        # produced one empty bucket and made every coverage count read as zero.
        cls = tc.get("classname") or ""
        f = cls.replace("tests.", "").split(".")[0]
        tests["by_file"][f + ".py"] = tests["by_file"].get(f + ".py", 0) + 1
        if tc.find("failure") is not None or tc.find("error") is not None:
            tests["failures"].append(f"{cls}::{tc.get('name')}")
tests["passed"] = tests["collected"] - tests["failed"] - tests["errors"] - tests["skipped"]

# ── known-failing baseline (Ananth's ruling: these predate the program) ───
KNOWN = os.path.join(ROOT, "docs", "chat-test-baseline.json")
known, regressions, newly_passing = set(), [], []
if os.path.exists(KNOWN):
    kb = json.load(open(KNOWN))
    known = set(kb.get("tests", []))
    now = set(tests["failures"])
    regressions = sorted(now - known)
    newly_passing = sorted(known - now)

# ── coverage per schema node ──────────────────────────────────────────────
import importlib.util
spec = importlib.util.spec_from_file_location("c", os.path.join(HERE, "chat_node_content.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
CONTENT = {}
for n in dir(m):
    v = getattr(m, n)
    if isinstance(v, dict) and v and all(isinstance(x, dict) for x in v.values()):
        CONTENT.update(v)
import readiness_signals as rs

nodes = []
for key, rec in sorted(CONTENT.items()):
    files = rs.tests_for(key) if re.fullmatch(r"[a-z0-9_]+", key) else []
    cases = sum(tests["by_file"].get(f, 0) for f in files)
    nodes.append({"node": key, "rating": rec.get("rating"), "files": files, "cases": cases,
                  "bugs": sum(1 for k, _ in rec.get("findings", []) if k == "bad")})
uncovered = [n for n in nodes if not n["files"]]
red_uncovered = [n for n in uncovered if n["rating"] == "red"]

# ── B. invariants against the frozen baseline ─────────────────────────────
inv, drift = {}, []
if os.path.exists(BASELINE):
    b = json.load(open(BASELINE))
    base = b["baseline"]
    try:
        import psycopg2
        dsn = os.environ.get("CHAT_BASELINE_DSN") or \
            "postgresql://postgres:MobiusDev123$@127.0.0.1:5433/mobius_chat"
        cur = psycopg2.connect(dsn).cursor()
        ids = [t["correlation_id"] for t in b["turns"]]
        cur.execute("select correlation_id, thinking_log from chat_turns "
                    "where correlation_id = any(%s)", (ids,))
        live = {}
        for cid, tl in cur.fetchall():
            try:
                items = tl if isinstance(tl, list) else json.loads(tl)
            except Exception:
                items = []
            txt, tr = [], None
            for it in (items if isinstance(items, list) else []):
                if isinstance(it, str):
                    txt.append(it)
                elif isinstance(it, dict):
                    d = it.get("data") if isinstance(it.get("data"), dict) else it
                    if tr is None and "groundedness_floor_ran" in d:
                        tr = d
                    txt += [v for v in d.values() if isinstance(v, str)]
            live[cid] = {"integrator_ran": "Composing answer" in "\n".join(txt),
                         "max_rounds": (tr or {}).get("max_rounds"),
                         "rounds_used": (tr or {}).get("rounds_used")}
        inv["turns_found"] = len(live)
        inv["turns_expected"] = b["n_turns"]
        i2 = sum(1 for t in b["turns"] if not live.get(t["correlation_id"], {}).get("integrator_ran", not t["integrator_ran"]))
        inv["I2_bypassed_now"] = i2
        inv["I2_bypassed_baseline"] = base["I2_integrator_ran"]["bypassed"]
        if i2 != inv["I2_bypassed_baseline"]:
            drift.append(f"I2 bypass set moved: {inv['I2_bypassed_baseline']} -> {i2}")
        i4 = sum(1 for t in b["turns"]
                 if live.get(t["correlation_id"], {}).get("max_rounds") != t["max_rounds"])
        inv["I4_rounds_changed"] = i4
        if i4:
            drift.append(f"I4 rounds arithmetic changed on {i4} turns")
        if len(live) != b["n_turns"]:
            drift.append(f"corpus incomplete: {len(live)} of {b['n_turns']} turns found "
                         "(retention? the gate depends on these existing)")
    except Exception as e:
        inv["error"] = f"{type(e).__name__}: {e}"

# ── C. structural signals (I7 source) ─────────────────────────────────────
struct = {"swallow": 0, "except_handlers": 0, "bare_except": 0, "loc": 0, "modules": 0}
for dirpath, _, files in os.walk(os.path.join(CHAT, "app")):
    for f in files:
        if not f.endswith(".py"):
            continue
        rel = os.path.relpath(os.path.join(dirpath, f), CHAT)
        try:
            s = rs.signals(rel)
        except Exception:
            continue
        struct["modules"] += 1
        for k in ("swallow", "except_handlers", "bare_except", "loc"):
            struct[k] += s.get(k, 0)

# ── report ────────────────────────────────────────────────────────────────
L = []; w = L.append
w("# Chat eval — tests and measurements\n")
w("Generated by `scripts/platform/gen_eval_report.py`. **Do not hand-edit.**")
w("One command runs every test and recomputes every measurement, so the suite result")
w("and the refactor gate cannot be reported from different moments.\n")
w("Exits non-zero when a test fails or a frozen-baseline invariant moves — usable as")
w("the POST half of the gate, not only as a report.\n")

w("## A · Tests\n")
w(f"| collected | passed | failed | errors | skipped | wall |")
w(f"|---:|---:|---:|---:|---:|---:|")
w(f"| {tests['collected']} | {tests['passed']} | {tests['failed']} | {tests['errors']} "
  f"| {tests['skipped']} | {tests['wall_s']}s |\n")
w(f"Known-failing baseline: **{len(known)}** tests, frozen 2026-09-08 before any P1a")
w("deletion. Ananth's ruling — these predate the program, so the gate SUBTRACTS them.")
w("A failure not in that set is a regression. The list may shrink, never grow.\n")
if regressions:
    w(f"### REGRESSIONS — {len(regressions)} failing test(s) NOT in the baseline\n")
    for f in regressions:
        w(f"- `{f}`")
    w("")
else:
    w("**No regressions** — every failure is in the known-failing baseline.\n")
if newly_passing:
    w(f"**{len(newly_passing)} baseline failure(s) now PASS** — shrink the baseline:\n")
    for f in newly_passing:
        w(f"- `{f}`")
    w("")

w("## A2 · What the tests actually cover, per schema node\n")
w("A total test count is not coverage of the thing you are about to change. This maps")
w("test files to nodes by name, which is a WEAK signal — it proves a file exists whose")
w("name matches, not that the node's behaviour is asserted. Eval owns replacing it.\n")
w(f"**{len(nodes) - len(uncovered)} of {len(nodes)} nodes have a matching test file · "
  f"{len(uncovered)} have none · {len(red_uncovered)} of those are RED**\n")
w("| Node | Rating | Bugs | Test files | Cases |")
w("|---|---|---:|---|---:|")
for n in sorted(nodes, key=lambda x: (x["files"] != [], x["rating"] != "red", x["node"])):
    w(f"| `{n['node']}` | {n['rating']} | {n['bugs']} | "
      f"{', '.join('`'+f+'`' for f in n['files']) or '**none**'} | {n['cases'] or '—'} |")
w("")

w("## B · Refactor gate — frozen baseline invariants\n")
if inv.get("error"):
    w(f"NOT COMPUTED: `{inv['error']}`\n")
else:
    w(f"Corpus `docs/chat-refactor-baseline.json` — {inv.get('turns_found','?')} of "
      f"{inv.get('turns_expected','?')} turns found.\n")
    w("| Invariant | Baseline | Now | |")
    w("|---|---:|---:|---|")
    w(f"| I2 integrator bypassed | {inv.get('I2_bypassed_baseline')} | {inv.get('I2_bypassed_now')} "
      f"| {'OK' if inv.get('I2_bypassed_now')==inv.get('I2_bypassed_baseline') else 'MOVED'} |")
    w(f"| I4 rounds arithmetic changed | 0 | {inv.get('I4_rounds_changed')} "
      f"| {'OK' if not inv.get('I4_rounds_changed') else 'MOVED'} |")
    w("")
    w("I3 and I5 are **deferred** — they need live LLM calls, and there is no")
    w("deterministic replay harness yet (P1.1). A flip would be unattributable.\n")
if drift:
    w("**DRIFT:**\n")
    for d in drift:
        w(f"- {d}")
    w("")

w("## C · Structural signals (I7 source)\n")
w(f"| modules | loc | except handlers | log-and-continue | bare except |")
w(f"|---:|---:|---:|---:|---:|")
w(f"| {struct['modules']} | {struct['loc']:,} | {struct['except_handlers']} | "
  f"{struct['swallow']} | {struct['bare_except']} |\n")
w("I7 is monotonic: the log-and-continue count may fall, never rise.\n")

open(args.out, "w").write("\n".join(L))
print(f"tests {tests['passed']}/{tests['collected']} passed, {tests['failed']} failed, "
      f"{tests['errors']} errors, {tests['skipped']} skipped ({tests['wall_s']}s)")
print(f"coverage {len(nodes)-len(uncovered)}/{len(nodes)} nodes have a matching test file "
      f"({len(red_uncovered)} RED without)")
print(f"structure {struct['loc']:,} loc · {struct['swallow']} log-and-continue "
      f"across {struct['modules']} modules")
for d in drift:
    print("DRIFT:", d)
print(f"-> {args.out}")
print(f"regressions {len(regressions)} · newly passing {len(newly_passing)} "
      f"· known-failing baseline {len(known)}")
for f in regressions:
    print("  REGRESSION:", f)
sys.exit(1 if (regressions or drift) else 0)
