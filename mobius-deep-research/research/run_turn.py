"""Run one real turn and keep the whole exchange.

Ask chat, store the answer verbatim, run the invoker's evaluator over it, store
that verdict too. The transcript UI is built from these rows, so what it shows
is the actual conversation — not a summary of one.
"""
from __future__ import annotations

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
from dotenv import load_dotenv                       # noqa: E402
load_dotenv(ROOT + "mobius-chat/.env")
from app.services.llm_manager import generate_sync    # noqa: E402


def db():
    c = psycopg2.connect(DB)
    c.autocommit = True
    return c, c.cursor(cursor_factory=RealDictCursor)


def ask_chat(question: str) -> dict:
    """New thread every call — a long run must not accumulate context."""
    cid = str(uuid.uuid4())
    body = {"message": question, "correlation_id": cid,
            "use_react": True, "chat_mode": "copilot"}
    req = urllib.request.Request(f"{CHAT}/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=60).read()
    errs = 0
    for _ in range(80):
        time.sleep(8)
        try:
            d = json.load(urllib.request.urlopen(
                f"{CHAT}/chat/response/{cid}", timeout=45))
            errs = 0
        except Exception:
            errs += 1
            if errs >= 6:
                break
            continue
        if d.get("message") and d.get("status") not in ("processing", "pending"):
            return {"message": d["message"], "sources": d.get("sources") or []}
    return {"error": "timed out"}


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
  "next_query": "a sharper question worth asking next, or empty if none would help"}}"""


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


def run(turn_id: int) -> None:
    conn, cur = db()
    cur.execute("""select t.*, r.evaluator_prompt, r.consumer, r.subject_id
                     from research.turn t join research.request r on r.id = t.request_id
                    where t.id = %s""", (turn_id,))
    t = cur.fetchone()
    if not t:
        sys.exit(f"no turn {turn_id}")
    print(f"turn {t['request_id']}.{t['n']} — asking chat…\n  {t['query'][:100]}\n")

    res = ask_chat(t["query"])
    if res.get("error"):
        print("chat:", res["error"]); return
    answer = res["message"]
    docs = []
    for s in res["sources"]:
        d = s.get("document_name") or s.get("title") or s.get("document") or ""
        if d and d not in docs:
            docs.append(d)
    print(f"  answer: {len(answer)} chars, {len(docs)} documents cited")

    ev = evaluate(t["evaluator_prompt"] or "Extract the requirement if stated.",
                  t["query"], answer, docs)
    print(f"  evaluator: extracted={ev.get('extracted')} "
          f"gap={ev.get('gap_class')} model={ev.get('_model')}")

    cur.execute("""insert into research.attempt
                     (request_id, round, asked, answered_by, sources_seen, top_documents,
                      outcome, statement, quote, source_document, reason, model,
                      answer_text, sources, evaluator_verdict, turn_id)
                   values (%s,%s,%s,'chat (ReAct, deployed)',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   returning id""",
                (t["request_id"], t["n"], t["query"], len(docs), docs[:8],
                 "extracted" if ev.get("extracted") else "not_answered",
                 ev.get("statement") or None, ev.get("quote") or None,
                 ev.get("document") or None, ev.get("verdict_reason"),
                 ev.get("_model"), answer, Json(res["sources"][:8]), Json(ev), turn_id))
    aid = cur.fetchone()["id"]
    cur.execute("""update research.turn
                      set attempt_id=%s,
                          extract_state=%s, extract_note=%s, next_query=%s
                    where id=%s""",
                (aid, "extracted" if ev.get("extracted") else "rejected",
                 ev.get("verdict_reason"), ev.get("next_query") or None, turn_id))
    print(f"  stored attempt {aid}; turn track A settled")


if __name__ == "__main__":
    run(int(sys.argv[1]))
