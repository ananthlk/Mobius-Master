#!/usr/bin/env python3
"""Repeatable chat capture harness for the payor fact-store rollout.

Built by the Interact Agent for the EVAL Agent (Ananth-directed). Drives
mobius-chat through its own API — no browser needed: POST /chat starts a NEW
thread per query; /chat/response/{cid} carries the answer AND the full RAG
diagnostics (strategy_picked, routing.method, fact_predicate, strategy_used)
that the DIAGNOSTICS tab renders.

Usage:
    python3 scripts/chat_fact_store_eval.py                  # run the acceptance suite
    python3 scripts/chat_fact_store_eval.py --json out.json  # also dump raw envelopes
    python3 scripts/chat_fact_store_eval.py --suite my.json  # custom suite file

Suite entries: {"q": "...", "expect_answer": "substring", "expect_route": "s|a|b|d",
                "expect_not": "substring"}  (all expect_* optional)
Re-run after each fix lands; the table diffs by eye or by --json artifacts.
"""
import argparse
import json
import re
import sys
import time
import urllib.request

CHAT = "https://mobius-chat-ortabkknqa-uc.a.run.app"
POLL_S = 5
TIMEOUT_S = 150

ACCEPTANCE_SUITE = [
    {"q": "What is Sunshine Health's EDI payer ID?",
     "expect_answer": "68069", "expect_route": "s"},
    {"q": "What is Sunshine Health's provider services phone number?",
     "expect_answer": "1-844-477-8313", "expect_route": "s"},
    {"q": "What provider portal does Sunshine Health use?",
     "expect_answer": "Secure Provider Portal", "expect_route": "s"},
    {"q": "What is Aetna Better Health of Florida's timely filing deadline for claims?",
     "expect_answer": "180 days", "expect_route": "s"},
    {"q": "what is pre-authorization philosophy of sunshine health",
     "expect_route": "a|b", "expect_not": "http"},
    {"q": "What is the AHCA provider login URL?",
     "expect_answer": "portal.flmmis.com", "expect_route": "s"},
    {"q": "What is a CMHC?", "expect_route": "a|b"},
]

ERROR_MARKERS = ["every attempt hit an error", "not found", "could not be found",
                 "couldn't find", "unable to find", "no information"]


def _http(method, url, body=None):
    req = urllib.request.Request(url, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode()
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode(), strict=False)


def _last(pattern, raw):
    hits = re.findall(pattern, raw)
    return hits[-1] if hits else None


def run_query(q):
    t0 = time.time()
    cid = _http("POST", f"{CHAT}/chat", {"message": q})["correlation_id"]
    envelope, status = None, "?"
    while time.time() - t0 < TIMEOUT_S:
        time.sleep(POLL_S)
        envelope = _http("GET", f"{CHAT}/chat/response/{cid}")
        status = envelope.get("status", "?")
        if status == "completed":
            break
    wall_s = round(time.time() - t0, 1)
    raw = json.dumps(envelope)

    # answer text: message may itself be a JSON blob with direct_answer
    msg = envelope.get("message") or ""
    answer = msg
    try:
        parsed = json.loads(msg, strict=False)
        answer = parsed.get("direct_answer") or msg
    except (json.JSONDecodeError, AttributeError):
        pass

    # diagnostics (same data the DIAGNOSTICS tab renders)
    picked = _last(r'"strategy_picked"\s*:\s*"([a-z])"', raw)
    used = _last(r'"strategy_used"\s*:\s*"([a-z])"', raw)
    method = _last(r'"method"\s*:\s*"([a-z_]+)"', raw)
    predicate = _last(r'"fact_predicate"\s*:\s*"([a-z_0-9]+)"', raw)
    route = used or picked or "?"
    route_full = route + (f" via {method}" if method else "")
    if predicate:
        route_full += f" ({predicate})"

    lower = answer.lower()
    errored = bool(envelope.get("llm_error")) or any(m in lower for m in ERROR_MARKERS)
    latency_ms = (envelope.get("llm_performance") or {}).get("total_latency_ms")

    return {"cid": cid, "status": status, "answer": answer.strip(), "route": route,
            "route_full": route_full, "predicate": predicate, "errored": errored,
            "latency_ms": latency_ms, "wall_s": wall_s, "envelope": envelope}


def verdict(case, r):
    if r["status"] != "completed":
        return "TIMEOUT"
    checks = []
    if case.get("expect_answer"):
        checks.append(case["expect_answer"].lower() in r["answer"].lower())
    if case.get("expect_route"):
        checks.append(r["route"] in case["expect_route"].split("|"))
    if case.get("expect_not"):
        checks.append(case["expect_not"].lower() not in r["answer"].lower())
    if r["errored"]:
        checks.append(False)
    return "PASS" if checks and all(checks) else "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", help="JSON file of suite entries")
    ap.add_argument("--json", help="write raw results (incl. envelopes) here")
    args = ap.parse_args()
    suite = ACCEPTANCE_SUITE
    if args.suite:
        suite = json.load(open(args.suite))

    results = []
    for i, case in enumerate(suite, 1):
        print(f"[{i}/{len(suite)}] {case['q'][:60]}…", file=sys.stderr, flush=True)
        r = run_query(case["q"])
        r["verdict"] = verdict(case, r)
        r["query"] = case["q"]
        r["expected"] = {k: v for k, v in case.items() if k != "q"}
        results.append(r)

    print("\n| # | query | route | answer (head) | err | ms | verdict |")
    print("|---|-------|-------|---------------|-----|----|---------|")
    for i, r in enumerate(results, 1):
        ans = r["answer"][:60].replace("|", "/").replace("\n", " ")
        print(f"| {i} | {r['query'][:45]} | {r['route_full']} | {ans} "
              f"| {'Y' if r['errored'] else 'n'} | {r['latency_ms'] or '?'} | {r['verdict']} |")
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    print(f"\n{passed}/{len(results)} PASS")

    if args.json:
        json.dump(results, open(args.json, "w"), indent=1, default=str)
        print(f"raw results → {args.json}")


if __name__ == "__main__":
    main()
