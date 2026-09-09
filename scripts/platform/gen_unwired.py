"""Detect the codebase's signature defect: things that were BUILT but never WIRED.

Ananth 2026-09-08: "that call manager pattern — log it as a systemic finding."

The class, stated once: a capability is implemented, often carefully and with tests,
and nothing in the live path ever calls it, reads it back, or persists what it
produced. Every instance looks healthy in isolation — the code is present, the tests
pass, the docstring describes real intent — and the capability is simply absent at
runtime. Health stays green.

This finds the mechanical half: public classes and functions defined in app/ whose
ONLY references are their own module and the tests that cover them. That is not proof
of deadness (a name reached only via getattr, a registry, or an entrypoint will
false-positive) so the output is a CANDIDATE LIST to be read, not a verdict.

The instances already confirmed by hand are listed separately below, because the
detector cannot see most of them — a column nobody writes and a JSON key nobody
emits leave no symbol to grep.
"""
import ast, os, re, subprocess, sys, json, collections

CHAT = "/Users/ananth/Mobius/mobius-chat"
SKIP_PREFIX = ("test_", "_")

def _framework_called(node):
    """Things the framework invokes by reference, not by name — a name-grep can
    never see these called, so counting them would inflate the finding.
    Excluded: FastAPI/router route handlers, event hooks, validators, fixtures,
    and Pydantic request/response models (instantiated by FastAPI from the
    annotation, never by name)."""
    for d in getattr(node, "decorator_list", []):
        src = ast.dump(d)
        if any(k in src for k in ("router", "app'", "'app'", "get", "post", "put",
                                  "delete", "patch", "on_event", "validator",
                                  "fixture", "property", "staticmethod",
                                  "classmethod", "lru_cache", "dataclass")):
            return True
    if isinstance(node, ast.ClassDef):
        for b in node.bases:
            bn = b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", "")
            if bn in ("BaseModel", "Enum", "StrEnum", "IntEnum", "Exception",
                      "TypedDict", "Protocol", "NamedTuple"):
                return True
    return False


def public_defs(path):
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except SyntaxError:
        return []
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if n.name.startswith(SKIP_PREFIX) or len(n.name) <= 4:
                continue
            if _framework_called(n):
                continue
            out.append((n.name, type(n).__name__, n.lineno))
    return out

# one grep over the tree, then attribute hits per symbol — far faster than N greps
def refs_for(names):
    hits = collections.defaultdict(set)
    pat = r"\b(" + "|".join(re.escape(n) for n in names) + r")\b"
    p = subprocess.run(["grep", "-rnoE", pat, "app/", "tests/", "--include=*.py"],
                       cwd=CHAT, capture_output=True, text=True)
    for line in p.stdout.splitlines():
        try:
            f, _, sym = line.split(":", 2)
        except ValueError:
            continue
        hits[sym].add(f)
    return hits

cands = []
for dirpath, _, files in os.walk(os.path.join(CHAT, "app")):
    for f in files:
        if not f.endswith(".py") or f == "__init__.py":
            continue
        rel = os.path.relpath(os.path.join(dirpath, f), CHAT)
        for name, kind, line in public_defs(os.path.join(dirpath, f)):
            cands.append({"name": name, "kind": kind, "path": rel, "line": line})

allhits = refs_for(sorted({c["name"] for c in cands}))
unwired = []
for c in cands:
    files = allhits.get(c["name"], set())
    outside = {f for f in files
               if f != c["path"] and not os.path.basename(f).startswith("test_")}
    tested = any(os.path.basename(f).startswith("test_") for f in files)
    if not outside and "app/api/" not in c["path"]:
        c["tested"] = tested
        unwired.append(c)

by_mod = collections.Counter(u["path"] for u in unwired)
tested_n = sum(1 for u in unwired if u["tested"])

print(f"scanned {len(cands)} public defs across app/")
print(f"UNWIRED CANDIDATES: {len(unwired)}  ({tested_n} of them have tests — "
      f"built, tested, never called)")
print("\ntop modules by unwired count:")
for m, n in by_mod.most_common(12):
    print(f"  {n:3d}  {m}")
print("\nthe ones WITH tests (strongest signal — someone verified it works, "
      "nothing uses it):")
for u in sorted([x for x in unwired if x["tested"]], key=lambda x: x["path"])[:25]:
    print(f"  {u['path']}:{u['line']:<5} {u['kind']:9} {u['name']}")
json.dump(unwired, open("/Users/ananth/Mobius/docs/chat-unwired-candidates.json", "w"), indent=1)
print(f"\n-> docs/chat-unwired-candidates.json")
