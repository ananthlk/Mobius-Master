"""Run a multi-turn research and stream chat's working out as it happens.

Prints chat's live thinking log while it works, then the answer, then the
evaluator's verdict and the question it wants to ask next — turn after turn,
until something extracts or the rounds run out.

    python3 run_research.py --subject bh_therapy/provider_qualification \
        --query "..." --evaluator-file eval.txt --turns 3
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor, Json

ROOT = "/Users/ananth/Mobius/"
CHAT = "https://mobius-chat-ortabkknqa-uc.a.run.app"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

sys.path.insert(0, ROOT + "mobius-chat")
from dotenv import load_dotenv                        # noqa: E402
load_dotenv(ROOT + "mobius-chat/.env")
from app.services.llm_manager import generate_sync     # noqa: E402

BAR = "─" * 74


def db():
    c = psycopg2.connect(DB)
    c.autocommit = True
    return c, c.cursor(cursor_factory=RealDictCursor)


def ask_chat_streaming(question: str, mode: str = "copilot") -> dict:
    """Ask, and print chat's thinking log as it arrives.

    New thread every call — a multi-turn research must not accumulate context in
    the thread, or turn 3 is answered partly from turn 1's framing.
    """
    cid = str(uuid.uuid4())
    body = {"message": question, "correlation_id": cid,
            "use_react": True, "chat_mode": mode}
    req = urllib.request.Request(f"{CHAT}/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=60).read()
    print(f"  [thread {cid[:8]}] mode={mode}; streaming chat's working out\n", flush=True)

    seen, errs = 0, 0
    for _ in range(90):
        time.sleep(6)
        try:
            d = json.load(urllib.request.urlopen(
                f"{CHAT}/chat/response/{cid}", timeout=45))
            errs = 0
        except Exception:
            errs += 1
            if errs >= 6:
                break
            continue

        log = d.get("thinking_log") or []
        if isinstance(log, str):
            log = [l for l in log.split("\n") if l.strip()]
        for line in log[seen:]:
            print(f"      · {str(line).strip()[:150]}", flush=True)
        seen = len(log)

        if d.get("message") and d.get("status") not in ("processing", "pending"):
            return {"message": d["message"], "sources": d.get("sources") or []}
    return {"error": "timed out waiting for chat"}


def envelope(raw: str) -> tuple[str, dict]:
    try:
        d = json.loads(raw)
    except Exception:
        return raw, {}
    if not isinstance(d, dict):
        return raw, {}
    body = d.get("direct_answer") or d.get("answer") or raw
    meta = {k: v for k, v in d.items()
            if k in ("mode", "unfinished_reason", "confidence") and v}
    m = re.search(r"Unfinished Reason:\s*(\w+)", body)
    if m:
        meta.setdefault("unfinished_reason", m.group(1))
        body = body[:m.start()].rstrip()
    return body, meta


EVAL_WRAPPER = """{evaluator}

QUESTION PUT TO THE CORPUS:
{question}

THE ANSWER THAT CAME BACK:
{answer}

DOCUMENTS IT CITED:
{docs}

Return ONLY JSON:
{{"extracted": true|false,
  "statement": "the requirement in one sentence, or empty",
  "quote": "verbatim sentence from THE ANSWER supporting it, or empty",
  "document": "which cited document, exactly as listed, or empty",
  "verdict_reason": "why you accepted or rejected it",
  "gap_class": "not_in_corpus|not_retrievable|vocabulary|absent_from_source|none",
  "next_query": "a sharper question worth asking next, or empty if none would help"}}

The quote must be copied verbatim from THE ANSWER. Prefer refusing over guessing —
an unsourced requirement is worse than a known gap."""


def evaluate(evaluator: str, question: str, answer: str, docs: list[str]) -> dict:
    prompt = EVAL_WRAPPER.format(evaluator=evaluator, question=question,
                                 answer=answer[:12000],
                                 docs="\n".join(f"- {d}" for d in docs) or "(none)")
    raw, usage = generate_sync(prompt, stage="parser", max_tokens=4096, parser=True)
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return {"extracted": False, "verdict_reason": "evaluator returned no JSON"}
    out = json.loads(m.group(0))
    out["_model"] = (usage or {}).get("model")
    return out


def run(subject: str, query: str, evaluator: str, turns: int, consumer: str,
        mode: str = "copilot") -> None:
    conn, cur = db()
    cur.execute("""insert into research.request
                     (consumer, subject_type, subject_id, question, evaluator_prompt,
                      max_rounds, invoker, status)
                   values (%s,'standard_requirement',%s,%s,%s,%s,%s,'open')
                   on conflict (consumer, subject_type, subject_id) do update
                     set question=excluded.question, evaluator_prompt=excluded.evaluator_prompt,
                         max_rounds=excluded.max_rounds, status='open'
                   returning id""",
                (consumer, subject, query, evaluator, turns, consumer))
    rid = cur.fetchone()["id"]
    print(f"\n{BAR}\nRESEARCH  request {rid}  ·  {subject}  ·  chat mode: {mode}"
          f"{'  (think — 10 rounds)' if mode == 'agentic' else '  (3 rounds)'}\n{BAR}")
    print(f"evaluator says: {evaluator[:150]}…\n")

    q = query
    for n in range(1, turns + 1):
        cur.execute("""insert into research.turn (request_id, n, query, status)
                       values (%s,%s,%s,'running')
                       on conflict (request_id, n) do update set query=excluded.query,
                         extract_state='pending', status='running'
                       returning id""", (rid, n, q))
        tid = cur.fetchone()["id"]

        print(f"\n{BAR}\nTURN {n}\n{BAR}")
        print(f"  ASK → {q}\n")

        res = ask_chat_streaming(q, mode)
        if res.get("error"):
            print(f"  chat: {res['error']}")
            break

        body, meta = envelope(res["message"])
        docs = []
        for s in res["sources"]:
            d = s.get("document_name") or s.get("title") or s.get("document") or ""
            if d and d not in docs:
                docs.append(d)

        print(f"\n  ANSWER  ({len(docs)} documents cited"
              + (f", {meta}" if meta else "") + ")\n")
        for para in [p for p in body.split("\n") if p.strip()][:14]:
            print(f"    {para.strip()[:170]}")
        if docs:
            print(f"\n    sources: {', '.join(d[:36] for d in docs[:6])}")

        ev = evaluate(evaluator, q, body, docs)
        got = bool(ev.get("extracted"))
        print(f"\n  EVALUATOR  [{ev.get('_model')}]  →  "
              f"{'EXTRACTED' if got else 'REJECTED'}"
              + (f"  · gap={ev.get('gap_class')}" if not got else ""))
        print(f"    {(ev.get('verdict_reason') or '')[:280]}")
        if got:
            print(f"\n    statement: {ev.get('statement')}")
            print(f"    grounded on: \"{(ev.get('quote') or '')[:200]}\"")
            print(f"    document: {ev.get('document')}")

        cur.execute("""insert into research.attempt
                         (request_id, round, asked, answered_by, sources_seen, top_documents,
                          outcome, statement, quote, source_document, reason, model,
                          answer_text, sources, evaluator_verdict, turn_id)
                       values (%s,%s,%s,'chat (ReAct, deployed)',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       returning id""",
                    (rid, n, q, len(docs), docs[:8],
                     "extracted" if got else "not_answered",
                     ev.get("statement") or None, ev.get("quote") or None,
                     ev.get("document") or None, ev.get("verdict_reason"),
                     ev.get("_model"), res["message"], Json(res["sources"][:8]), Json(ev), tid))
        aid = cur.fetchone()["id"]
        cur.execute("""update research.turn
                          set attempt_id=%s, extract_state=%s, extract_note=%s,
                              next_query=%s, status='complete', both_settled_at=now()
                        where id=%s""",
                    (aid, "extracted" if got else "rejected",
                     ev.get("verdict_reason"), ev.get("next_query") or None, tid))

        if got:
            cur.execute("""update research.request set status='sourced', resolved_at=now()
                            where id=%s""", (rid,))
            print(f"\n{BAR}\nSOURCED on turn {n}\n{BAR}")
            return

        nxt = ev.get("next_query")
        if not nxt:
            print("\n  evaluator has no sharper question — nothing more to ask")
            break
        print(f"\n  REFINES → {nxt}")
        q = nxt

    cur.execute("""insert into research.escalation (request_id, reason, asked, what_we_checked)
                   values (%s,'rounds_exhausted',%s,%s)""",
                (rid, query, f"{turns} turns, each refined by the evaluator; "
                             f"last gap class recorded on the final attempt"))
    cur.execute("update research.request set status='escalated' where id=%s", (rid,))
    print(f"\n{BAR}\nNOT SOURCED after {turns} turns — escalated to a human\n{BAR}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--evaluator-file", required=True)
    ap.add_argument("--turns", type=int, default=3)
    ap.add_argument("--consumer", default="service_line_registry")
    ap.add_argument("--mode", default="copilot",
                    help="copilot (3 rounds) | agentic (think mode, 10 rounds)")
    a = ap.parse_args()
    run(a.subject, a.query, open(a.evaluator_file).read(), a.turns, a.consumer, a.mode)
