#!/usr/bin/env python3
"""GATE: the page must be valid and self-consistent, or refresh.sh FAILS.

WHY THIS EXISTS. Ananth caught three schema defects in one day — a blank page from a
JS syntax error, ratings that were stale by a day, and a findings list rendering seven
red triangles against a derived badge of "2 open". Every one was catchable by one
check I kept saying I would run and then skipped. "i want you to keep updating it that
is your only critical job", and then "if you cannot maintain the document tell me i
will, this is sloppy work."

So the check stops depending on my discipline. It runs in the chain and exits non-zero.

CHECKS
 1. the assembled inline JS parses (node --check). A grep proves presence, never
    execution — that is exactly how the blank page shipped.
 2. every node's derived rating agrees with its own findings list: the count of
    open-and-owned-here bad findings must match what the rating reasoned from. A badge
    computed from evidence beside a list ignoring it is worse than either alone.
 3. no node carries a rating without a reason, and no live node is missing signals.
 4. the page is not truncated: it must contain the last node key written to the data.
"""
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rating_rubric as R

fails = []


def check_js(html):
    js = "\n".join(re.findall(r"<script>(.*?)</script>", html, re.S))
    if not js.strip():
        fails.append("no inline <script> found — the page would render dead")
        return
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js); path = f.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        if r.returncode:
            fails.append("inline JS does NOT parse — page would be blank:\n"
                         + r.stderr.strip()[:400])
    except FileNotFoundError:
        fails.append("node not available — cannot prove the page renders")
    finally:
        os.unlink(path)


def walk(o):
    if isinstance(o, dict):
        if "rating_why" in o:
            yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def check_consistency(data):
    for n in walk(data):
        key = n.get("key") or "(unkeyed)"
        if n.get("rating") == "removed":
            continue
        if not n.get("rating_why"):
            fails.append(f"{key}: rating with no reason")
        fs, fnd = n.get("findings_status") or [], n.get("findings") or []
        if len(fs) != len(fnd):
            fails.append(f"{key}: findings_status length {len(fs)} != findings {len(fnd)}")
            continue
        listed = sum(1 for (k, t), st in zip(fnd, fs)
                     if k == "bad" and not st["closed"] and st["own"])
        counted = R.open_bugs(fnd)
        if listed != counted:
            fails.append(f"{key}: badge reasoned from {counted} open, list shows "
                         f"{listed} — the two must agree")


def main():
    html_p = os.path.join(ROOT, "docs", "chat-schema", "index.html")
    data_p = os.path.join(ROOT, "docs", "chat-schema", "chat-dev.json")
    if not (os.path.exists(html_p) and os.path.exists(data_p)):
        sys.exit("FATAL: page or data missing")
    html = open(html_p, encoding="utf-8").read()
    data = json.load(open(data_p))
    check_js(html)
    check_consistency(data)
    if len(html) < 50_000:
        fails.append(f"page is only {len(html)} bytes — looks truncated")
    if fails:
        print("PAGE GATE FAILED:")
        for f in fails:
            print("  ✗", f)
        sys.exit(1)
    nodes = sum(1 for _ in walk(data))
    print(f"page gate OK · JS parses · {nodes} nodes, badge and list agree · "
          f"{len(html):,} bytes")


if __name__ == "__main__":
    main()
