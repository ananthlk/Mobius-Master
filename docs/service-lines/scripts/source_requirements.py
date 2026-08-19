"""Source the registry's standard requirements by asking Mobius chat.

The loop, per the design:

    round 1   ask every unsourced requirement            -> extract what validates
    round 2   re-ask only what is still unsourced, with a sharper question
    round 3   same again, narrowed to the document the corpus actually surfaced
    residue   what survives three rounds is the document-acquisition backlog

Questions go through chat's ReAct loop, not raw corpus_search — ReAct plans,
picks tools, escalates and returns sources, which is exactly the behaviour we
want exercised. A separate extraction pass turns the prose answer into a typed
requirement and refuses anything it cannot ground.

Grounding is checked, not trusted: the extractor's quote must appear in chat's
own answer, and the document it names must be one chat actually cited. An
answer with no sources is never written, however confident it sounds.

    python3 source_requirements.py --rounds 3 [--limit N] [--type place_of_service]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = "/Users/ananth/Mobius/"
CHAT = os.environ.get("MOBIUS_CHAT_URL", "https://mobius-chat-ortabkknqa-uc.a.run.app")
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")
# The extractor runs through LLMManager, not a direct provider call: the model
# router picks the model, the call is logged to llm_calls, and no model ID or
# API key is pinned here. Nothing in this file should name a model.
sys.path.insert(0, ROOT + "mobius-chat")
from dotenv import load_dotenv                                    # noqa: E402
load_dotenv(ROOT + "mobius-chat/.env")
from app.services.llm_manager import generate_sync                # noqa: E402

# ── what to ask, per requirement type ───────────────────────────────────────
ASK = {
    "place_of_service":
        "In which place-of-service settings may {line} be delivered and billed? "
        "List the POS codes or named settings.",
    "documentation":
        "What documentation must be in the record to support billing {line}? "
        "List the required elements.",
    "coverage_criteria":
        "What are the medical-necessity or coverage criteria a recipient must meet "
        "for {line} to be covered?",
    "prior_authorization":
        "Does {line} require prior authorization under the state rule, and if so "
        "after how many units or under what conditions?",
    "credentialing":
        "What provider enrollment, licensure or certification is required to bill {line}?",
    "provider_qualification":
        "Which practitioner types and licence levels may render {line}?",
    "supervision":
        "What supervision is required for {line} — who must oversee the rendering "
        "practitioner?",
    "setting":
        "What facility, programme or staffing requirements apply to {line}?",
    "age_population":
        "Which age groups or populations is {line} covered for?",
    "referral_order":
        "Who must order, refer or authorize {line} before it can be delivered?",
}

JURISDICTION = "Florida Medicaid"


def question_for(req: dict, round_no: int, prior: dict | None) -> str:
    """Round 1 asks plainly. Later rounds narrow using what the corpus surfaced."""
    line = req["line_name"]
    rule = f" (rule {req['rule_ref']})" if req.get("rule_ref") else ""
    base = ASK[req["requirement_type"]].format(line=f"{line}{rule}")
    codes = req.get("codes") or ""
    head = f"For {JURISDICTION}: {base}"

    if round_no == 1:
        tail = (f" The billed codes are {codes}." if codes else "")
        return head + tail + " Quote the governing policy text and name the source document."

    if round_no == 2:
        return (head + (f" The billed codes are {codes}." if codes else "") +
                " Search the AHCA coverage policy and the Florida Medicaid provider handbook "
                "for this service specifically. If the policy states this, quote the exact "
                "sentence and name the document. If no document in the corpus states it, "
                "say plainly that it is not in the corpus — do not infer it.")

    seen = ", ".join((prior or {}).get("top_documents") or []) or "none"
    return (head + f" Earlier searches surfaced these documents: {seen}. "
            "Look inside those documents specifically. Quote the exact sentence that answers "
            "this and name the document and page. If none of them state it, say so plainly.")


# ── chat client ─────────────────────────────────────────────────────────────
def _post(url: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def ask_chat(question: str, tries: int = 3) -> dict:
    """POST to chat, poll until answered. Transient network errors are retried —
    a dropped poll must not be recorded as 'the corpus has nothing'."""
    for attempt in range(tries):
        # Deliberately a NEW thread per call — no thread_id is ever sent. Each
        # question stands alone, so a long sourcing run cannot accumulate context
        # and blow the thread's memory. Round 2/3 carry their refinement in the
        # question text instead of in conversation history.
        cid = str(uuid.uuid4())
        try:
            _post(f"{CHAT}/chat", {"message": question, "correlation_id": cid,
                                   "use_react": True, "chat_mode": "copilot"}, 60)
        except Exception as exc:
            if attempt == tries - 1:
                return {"error": f"post failed: {exc}"}
            time.sleep(5)
            continue

        consecutive_errors = 0
        for _ in range(75):
            time.sleep(8)
            try:
                d = json.load(urllib.request.urlopen(
                    f"{CHAT}/chat/response/{cid}", timeout=45))
                consecutive_errors = 0
            except Exception:
                consecutive_errors += 1
                if consecutive_errors >= 6:
                    break
                continue
            if d.get("message") and d.get("status") not in ("processing", "pending"):
                return {"message": d.get("message") or "",
                        "sources": d.get("sources") or [],
                        "status": d.get("status")}
        if attempt == tries - 1:
            return {"error": "timed out waiting for chat"}
        time.sleep(5)
    return {"error": "exhausted"}


# ── extraction ──────────────────────────────────────────────────────────────
EXTRACT_PROMPT = """You are extracting one typed requirement for a healthcare service-line registry.

SERVICE LINE: {line}
REQUIREMENT TYPE: {rtype}
QUESTION ASKED: {question}

CHAT'S ANSWER:
{answer}

DOCUMENTS CHAT CITED:
{docs}

Return ONLY JSON:
{{
  "answered": true|false,
  "statement": "one sentence stating the requirement, in the policy's own terms",
  "quote": "verbatim sentence from CHAT'S ANSWER that supports it",
  "document": "the cited document this came from, exactly as listed above",
  "confidence": 0.0-1.0,
  "reason": "if answered is false, why"
}}

Rules, applied strictly:
- answered=false if the answer is generic, hedged, or describes the service rather
  than stating this specific requirement.
- answered=false if the answer says the information is not in the corpus.
- answered=false if no document is cited. A requirement without a source is worthless here.
- "quote" must be copied verbatim from CHAT'S ANSWER. Never paraphrase, never invent.
- "document" must be one of the documents listed above, copied exactly.
- Prefer refusing over guessing. An unsourced requirement is worse than a known gap."""


EXTRACT_SCHEMA = {  # the shape the prompt asks for; validated in validate()

    "type": "object",
    "properties": {
        "answered": {"type": "boolean"},
        "statement": {"type": "string"},
        "quote": {"type": "string"},
        "document": {"type": "string"},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["answered", "statement", "quote", "document", "confidence", "reason"],
    "additionalProperties": False,
}


def extract(req: dict, question: str, answer: str, docs: list[str]) -> dict:
    prompt = EXTRACT_PROMPT.format(
        line=req["line_name"], rtype=req["requirement_type"],
        question=question, answer=answer[:12000],
        docs="\n".join(f"- {d}" for d in docs) or "(none)")
    try:
        raw, usage = generate_sync(prompt, stage="parser", max_tokens=4096, parser=True)
    except Exception as exc:
        return {"answered": False, "reason": f"extractor error: {exc}"}
    if not (raw or "").strip():
        return {"answered": False, "reason": "extractor returned nothing"}
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {"answered": False, "reason": "extractor returned no JSON"}
    try:
        out = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        return {"answered": False, "reason": f"bad JSON from extractor: {exc}"}
    out["_model"] = (usage or {}).get("model")
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def validate(ext: dict, answer: str, docs: list[str]) -> tuple[bool, str]:
    """Grounding is verified here, not taken on faith."""
    if not ext.get("answered"):
        return False, ext.get("reason") or "not answered"
    if not docs:
        return False, "chat cited no documents"
    quote, doc = ext.get("quote") or "", ext.get("document") or ""
    if not quote or _norm(quote)[:80] not in _norm(answer):
        return False, "quote not present verbatim in chat's answer"
    if not any(_norm(doc) in _norm(d) or _norm(d) in _norm(doc) for d in docs):
        return False, f"cited document '{doc[:60]}' is not one chat returned"
    if not (ext.get("statement") or "").strip():
        return False, "empty statement"
    return True, ""


# ── loop ────────────────────────────────────────────────────────────────────
def open_requirements(cur, rtype: str | None, limit: int | None) -> list[dict]:
    cur.execute("""
        select r.id, r.line_key, r.requirement_type, l.name as line_name, l.rule_ref,
               (select string_agg(distinct c.code, ', ')
                  from service_line.line_code c
                 where c.line_key = r.line_key and c.binding_role = 'rendered_as') as codes
          from service_line.standard_requirement r
          join service_line.line l on l.key = r.line_key
         where not r.sourced
           and (%s is null or r.requirement_type = %s)
         order by r.line_key, r.requirement_type
         limit %s""", (rtype, rtype, limit))
    return [dict(r) for r in cur.fetchall()]


def prior_attempt(cur, req_id: int) -> dict | None:
    cur.execute("""select top_documents, reason from service_line.sourcing_attempt
                    where requirement_id=%s order by round desc limit 1""", (req_id,))
    r = cur.fetchone()
    return dict(r) if r else None


def run(rounds: int, rtype: str | None, limit: int | None) -> None:
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=RealDictCursor)

    for rnd in range(1, rounds + 1):
        todo = open_requirements(cur, rtype, limit)
        print(f"\n{'='*66}\nROUND {rnd} — {len(todo)} unsourced requirements\n{'='*66}", flush=True)
        if not todo:
            break
        extracted = 0
        for i, req in enumerate(todo, 1):
            q = question_for(req, rnd, prior_attempt(cur, req["id"]))
            print(f"[{rnd}.{i}/{len(todo)}] {req['line_key']} · {req['requirement_type']}", flush=True)

            res = ask_chat(q)
            if res.get("error"):
                outcome, reason, answer, docs = "error", res["error"], "", []
            else:
                answer = res.get("message") or ""
                docs = []
                for s in res.get("sources") or []:
                    d = s.get("document_name") or s.get("title") or s.get("document") or ""
                    if d and d not in docs:
                        docs.append(d)
                if not docs:
                    outcome, reason = "no_retrieval", "chat returned no sources"
                else:
                    ext = extract(req, q, answer, docs)
                    ok, why = validate(ext, answer, docs)
                    if ok:
                        outcome, reason = "extracted", ""
                        cur.execute("""update service_line.standard_requirement
                                          set statement=%s, source_ref=%s, sourced=true
                                        where id=%s""",
                                    (ext["statement"], ext["document"], req["id"]))
                        extracted += 1
                    else:
                        outcome = ("ungrounded" if "quote" in why or "document" in why
                                   else "not_answered")
                        reason = why
                    ext_saved = ext
            cur.execute("""insert into service_line.sourcing_attempt
                             (requirement_id, line_key, requirement_type, round, question,
                              retrieved, top_documents, outcome, statement, quote,
                              source_document, confidence, model, reason)
                           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (req["id"], req["line_key"], req["requirement_type"], rnd, q,
                         len(docs), docs[:6], outcome,
                         (locals().get("ext_saved") or {}).get("statement") if outcome == "extracted" else None,
                         (locals().get("ext_saved") or {}).get("quote") if outcome == "extracted" else None,
                         (locals().get("ext_saved") or {}).get("document") if outcome == "extracted" else None,
                         (locals().get("ext_saved") or {}).get("confidence") if outcome == "extracted" else None,
                         (locals().get("ext_saved") or {}).get("_model") or "llm_manager",
                         reason or None))
            print(f"        -> {outcome}" + (f" · {reason[:70]}" if reason else ""), flush=True)
            ext_saved = None
        print(f"\nround {rnd}: extracted {extracted} of {len(todo)}", flush=True)

    cur.execute("""select count(*) filter (where sourced) s, count(*) filter (where not sourced) u
                     from service_line.standard_requirement""")
    r = cur.fetchone()
    print(f"\nFINAL — sourced {r['s']}, still unsourced {r['u']}")
    cur.execute("""select requirement_type, count(*) n, bool_or(never_retrieved) nr
                     from service_line.sourcing_gap group by 1 order by 2 desc""")
    print("\nacquisition backlog by type:")
    for row in cur.fetchall():
        print(f"  {row['requirement_type'].ljust(24)} {str(row['n']).rjust(3)}"
              f"{'  (never retrieved — document missing)' if row['nr'] else ''}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--type", default=None)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    run(a.rounds, a.type, a.limit)
