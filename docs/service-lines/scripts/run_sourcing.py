"""Start a sourcing run for one service line, and record it so a surface can follow it.

Per docs/service-lines/SOURCING_REQUEST_CONTRACT.md. Two things distinguish this from
the old source_requirements.py, which posted a prose question to /chat and polled for a
prose message:

  * It fills `expects` and `extraction_schema` (§11), so the state machine's typed
    extraction and its judge run on a guided request rather than an unguided one. The
    old path discarded both and kept the prose.

  * It emits `governing_resolved` BEFORE asking (§6.2) — the corpus check only the
    Registry can do. That single event is what makes `silent` decidable and
    `retrieval_miss` provable: if we state the document is held with 80 chunks and the
    run cannot read it, that is a retrieval failure by construction, not an absence.
    §0 of the contract is 125 attempts that lacked exactly this.

Registry stores the run, its membership and its own events. Turns, attempts, verdicts
and diagnoses stay in research.* and are read live — never copied.
"""
import argparse
import json
import sys
import traceback
import uuid

import psycopg2
from psycopg2.extras import Json, RealDictCursor

sys.path.insert(0, "/Users/ananth/Mobius/mobius-skills/deep-research")

ROOT = "/Users/ananth/Mobius/"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

JURISDICTION = "Florida Medicaid"

# ── §11: the slots, per requirement type ────────────────────────────────────
# `expects` names what must be filled. It replaces the compound prose question
# ("...and if so after how many units or under what conditions"), which asked two things
# in one sentence and reliably returned a paragraph.
SLOTS = {
    "prior_authorization": {
        "required":         "boolean — does the rule require prior authorization",
        "threshold_units":  "integer or null — units above which authorization is needed",
        "threshold_period": "one of day|week|month|state_fiscal_year, or null",
    },
    "place_of_service": {
        "pos_codes":          "array of POS codes stated verbatim, or empty",
        "settings":           "array of named settings stated verbatim",
        "telehealth_allowed": "boolean or null",
    },
    "age_population": {
        "min_age":    "integer or null", "max_age": "integer or null",
        "population": "string — the population named by the rule",
    },
    "supervision": {
        "supervisor_credential": "string — the credential that must oversee",
        "ratio":                 "string or null", "contact_type": "string or null",
    },
    "provider_qualification": {
        "credentials":    "array of practitioner credentials stated verbatim",
        "licence_levels": "array of licence levels, or empty",
    },
    "credentialing": {
        "enrollment_required": "boolean", "certification": "string or null",
        "programme":           "string or null",
    },
    "documentation": {
        "elements":         "array of required record elements stated verbatim",
        "retention_period": "string or null",
    },
    "coverage_criteria": {
        "criteria":          "array of medical-necessity criteria stated verbatim",
        "diagnosis_required": "boolean or null",
    },
    "referral_order": {
        "order_required":    "boolean", "orderer_credential": "string or null",
    },
    "setting": {"facility_type": "string or null", "staffing": "string or null"},
}

ASK = {
    "prior_authorization": "Does {subject} require prior authorization?",
    "place_of_service": "In which place-of-service settings may {subject} be delivered and billed?",
    "age_population": "Which age groups or populations is {subject} covered for?",
    "supervision": "What supervision is required for {subject}?",
    "provider_qualification": "Which practitioner types and licence levels may render {subject}?",
    "credentialing": "What provider enrollment, licensure or certification is required to bill {subject}?",
    "documentation": "What documentation must be in the record to support billing {subject}?",
    "coverage_criteria": "What medical-necessity or coverage criteria must a recipient meet for {subject}?",
    "referral_order": "Who must order or refer {subject} before it can be delivered?",
    "setting": "What facility, programme or staffing requirements apply to {subject}?",
}

EVAL = ("Fill only the named slots, each from a sentence quoted verbatim from a cited "
        "document. A slot the document does not address is null — do not infer it, and "
        "do not carry a value from a neighbouring service. If the document explicitly "
        "states that no requirement applies, that is an answer: say so plainly rather "
        "than reporting nothing found.")


def db():
    c = psycopg2.connect(DB)
    c.autocommit = True
    return c, c.cursor(cursor_factory=RealDictCursor)


def emit(cur, run_id, kind, data, text=None, seq=None):
    cur.execute("""insert into service_line.run_event (run_id, seq, kind, data, text)
                   values (%s,%s,%s,%s,%s)""", (run_id, seq, kind, Json(data), text))


def governing(cur, line_key):
    """The corpus check only the Registry can do — contract §6.2.

    Resolves the line's governing rule to a document and a chunk count. `resolvable`
    being true is a Registry ASSERTION: it makes 'the run could not read it' mean
    retrieval_miss rather than not_in_corpus, which is the distinction §0 lost.
    """
    cur.execute("select rule_ref from service_line.line where key=%s", (line_key,))
    row = cur.fetchone()
    ref = row["rule_ref"] if row else None
    if not ref:
        return {"rule_ref": None, "document_id": None, "resolvable": False, "chunks": 0,
                "why": "the service line has no governing rule recorded"}
    cur.execute("""select d.id, d.filename,
                          (select count(*) from hierarchical_chunks h where h.document_id=d.id) chunks
                     from documents d where d.filename ilike %s
                    order by chunks desc limit 1""", (f"%{ref}%",))
    d = cur.fetchone()
    if not d or not d["chunks"]:
        return {"rule_ref": ref, "document_id": d["id"] if d else None, "resolvable": False,
                "chunks": d["chunks"] if d else 0,
                "why": "held but holds no readable text" if d else "not in the corpus"}
    return {"rule_ref": ref, "document_id": d["id"], "document": d["filename"],
            "resolvable": True, "chunks": d["chunks"]}


def targets(cur, line_key, only_unsourced=True, limit=None):
    cur.execute(f"""select id, requirement_type, code, qualifier, sourced
                      from service_line.standard_requirement
                     where line_key=%s {'and not sourced' if only_unsourced else ''}
                       and requirement_type = any(%s)
                     order by requirement_type, code nulls first
                     {f'limit {int(limit)}' if limit else ''}""",
                (line_key, list(SLOTS)))
    return [dict(r) for r in cur.fetchall()]


def run(line_key, requested_by, limit=None, dry=False, max_rounds=2,
        existing_run=None, profile=None):
    conn, cur = db()
    cur.execute("select key, name from service_line.line where key=%s", (line_key,))
    line = cur.fetchone()
    if not line:
        sys.exit(f"no such service line: {line_key}")

    reqs = targets(cur, line_key, limit=limit)
    if not reqs:
        sys.exit(f"{line_key}: nothing unsourced to source")

    if existing_run:
        # The API already created the run and emitted run_started when it queued it.
        # Making a second row here would orphan the run_id the surface is streaming.
        run_id = existing_run
        cur.execute("""update service_line.sourcing_run set task_count=%s,
                          model_profile=coalesce(model_profile,%s) where id=%s""",
                    (len(reqs), profile, run_id))
        cur.execute("select model_profile from service_line.sourcing_run where id=%s", (run_id,))
        profile = (cur.fetchone() or {}).get("model_profile") or profile
    else:
        cur.execute("""insert into service_line.sourcing_run
                         (line_key, requested_by, task_count, model_profile)
                       values (%s,%s,%s,%s) returning id""",
                    (line_key, requested_by, len(reqs), profile))
        run_id = cur.fetchone()["id"]

    gov = governing(cur, line_key)
    if not existing_run:
        emit(cur, run_id, "run_started",
             {"line_key": line_key, "line_name": line["name"], "task_count": len(reqs),
              "requested_by": requested_by},
             f"Sourcing {len(reqs)} requirements for {line['name']}.")
    emit(cur, run_id, "model_profile", {"profile": profile},
         f"Asking under the {profile} model profile." if profile
         else "Asking under the worker's default model profile.")
    emit(cur, run_id, "governing_resolved", gov,
         (f"Governing rule {gov['rule_ref']} is held — {gov['chunks']} sections readable."
          if gov["resolvable"] else
          f"Governing rule {gov.get('rule_ref') or '(none recorded)'}: {gov['why']}."))

    print(f"run {run_id}  {line['name']}  {len(reqs)} requirements")
    print(f"  governing: {gov}")
    PROFILE_NOTE = profile or "worker default"
    if dry:
        cur.execute("""update service_line.sourcing_run
                          set status='cancelled', finished_at=now(),
                              note='dry run — nothing asked' where id=%s""", (run_id,))
        print("  (dry run — nothing asked)")
        return run_id

    # perform_turn, not service.open_and_run. Both ask, extract, judge and record — but
    # open_and_run calls ask_chat_streaming(q, chat_mode) with no profile, so a run takes
    # whatever model the worker instance happens to be set to. That is not a choice
    # anybody made, and it is how three runs died on Anthropic today while
    # /chat/admin/model-profile reported "gemini": the GET reads one of four Cloud Run
    # instances and the worker answering may be another. runner.perform_turn threads the
    # profile through to the request, where it cannot fragment.
    #
    # This uses Deep Research's public entry points and mints the turn the way work()
    # expects to find one. Nothing in their module is modified.
    from deep_research.runner import perform_turn                       # noqa: E402

    # TWO different LLM uses happen inside perform_turn, and only one of them is a
    # chat request:
    #
    #   1. the ASK — ask_chat_streaming() hits the chat SERVICE, which searches the
    #      corpus and answers. `profile` travels with that request and works.
    #   2. the EXTRACTOR and JUDGE — extract()/critique() run IN THIS PROCESS via
    #      llm_manager.generate_sync(stage="parser"). They turn the prose answer into
    #      the typed slots `expects` asked for, and check each field. generate_sync
    #      takes no profile argument, so #2 kept drawing Anthropic and dying on credits
    #      while #1 was happily answering on Gemini.
    #
    # profile_override sets a ContextVar the router reads, so it covers the in-process
    # half too. Without it, choosing a profile in the UI would silently steer only the
    # ask and leave the extraction on whatever the pool drew.
    from contextlib import ExitStack                                    # noqa: E402
    stack = ExitStack()
    if profile:
        try:
            from app.services.model_profile import profile_override     # noqa: E402
            stack.enter_context(profile_override(profile))
            print(f"  in-process extraction pinned to profile: {profile}")
        except Exception as exc:
            # Say so rather than running the extractor on an unintended model and
            # reporting the result as if the profile had been honoured.
            emit(cur, run_id, "error", {"profile": profile, "error": str(exc)[:300]},
                 f"Could not pin the extractor to {profile}; it will use the default pool.")
            print(f"  WARNING: extractor not pinned ({exc})")

    for seq, r in enumerate(reqs, 1):
        rtype = r["requirement_type"]
        subject = line["name"] + (f" (code {r['code']})" if r["code"] else "")
        question = (f"For {JURISDICTION}: " + ASK[rtype].format(subject=subject) +
                    (f" The governing rule is {gov['rule_ref']}." if gov["rule_ref"] else "") +
                    " Quote the governing policy text and name the source document.")
        subject_id = str(r["id"])

        cur.execute("""insert into research.request
                         (consumer, subject_type, subject_id, question, evaluator_prompt,
                          extraction_schema, jurisdiction, max_rounds, invoker, status)
                       values ('service_line_registry','standard_requirement',%s,%s,%s,%s,%s,%s,
                               'service_line_registry','open')
                       on conflict (consumer, subject_type, subject_id) do update
                         set question=excluded.question, status='open',
                             extraction_schema=excluded.extraction_schema
                       returning id""",
                    (subject_id, question, EVAL, Json(SLOTS[rtype]), JURISDICTION, max_rounds))
        pre_id = cur.fetchone()["id"]

        cur.execute("""insert into service_line.sourcing_link
                       (request_id, requirement_id, line_key, requirement_type, code,
                        qualifier, origin)
                       values (%s,%s,%s,%s,%s,%s,'declared')
                       on conflict (request_id) do update
                         set requirement_id=excluded.requirement_id, origin='declared'""",
                    (pre_id, r["id"], line_key, rtype, r["code"], r["qualifier"]))
        cur.execute("""insert into service_line.sourcing_run_member
                       (run_id, request_id, requirement_id, requirement_type, code, qualifier, seq)
                       values (%s,%s,%s,%s,%s,%s,%s)""",
                    (run_id, pre_id, r["id"], rtype, r["code"], r["qualifier"], seq))
        emit(cur, run_id, "request_opened",
             {"requirement_id": r["id"], "request_id": pre_id, "requirement_type": rtype,
              "code": r["code"], "expects": list(SLOTS[rtype]), "question": question,
              "model_profile": profile},
             None, seq)
        print(f"  [{seq}/{len(reqs)}] {rtype}{' ' + r['code'] if r['code'] else ''} "
              f"(profile: {PROFILE_NOTE}) …", flush=True)

        state, note, q, rounds = None, None, question, 0
        for n in range(1, max_rounds + 1):
            cur.execute("""insert into research.turn (request_id, n, query, status)
                           values (%s,%s,%s,'running')
                           on conflict (request_id, n) do update
                             set query=excluded.query, extract_state='pending',
                                 attempt_id=null, status='running'
                           returning *""", (pre_id, n, q))
            turn = dict(cur.fetchone())
            rounds = n
            try:
                out = perform_turn(cur, turn, "agentic", profile)
            except Exception as exc:
                traceback.print_exc()
                emit(cur, run_id, "error",
                     {"requirement_id": r["id"], "error": str(exc)[:500],
                      "model_profile": profile},
                     f"{rtype} failed to run.", seq)
                state, note = "error", str(exc)[:300]
                break
            state, note = out.get("state"), out.get("note")
            if state == "extracted":
                break
            # A turn left 'pending' means the ask itself failed — retrying the same
            # question against the same broken path just burns the round budget.
            if state == "pending":
                break
            cur.execute("select next_query from research.turn where id=%s", (turn["id"],))
            nxt = (cur.fetchone() or {}).get("next_query")
            if not nxt:
                break
            q = nxt

        if state == "extracted":
            cur.execute("""update research.request set status='sourced', resolved_at=now()
                            where id=%s""", (pre_id,))
        elif state != "error":
            cur.execute("update research.request set status='escalated' where id=%s", (pre_id,))

        cur.execute("""select outcome, source_document from research.attempt
                        where request_id=%s order by round desc, id desc limit 1""", (pre_id,))
        last = cur.fetchone() or {}
        emit(cur, run_id, "request_settled",
             {"requirement_id": r["id"], "request_id": pre_id, "state": state,
              "turns": rounds, "outcome": last.get("outcome"),
              "document": last.get("source_document"), "model_profile": profile},
             note, seq)
        print(f"        -> {state} in {rounds} turn(s)"
              f"{' — ' + note[:80] if note else ''}", flush=True)

    stack.close()
    cur.execute("""update service_line.sourcing_run set status='finished', finished_at=now()
                    where id=%s""", (run_id,))
    cur.execute("""select coalesce(f.finding,'undiagnosed') k, count(*) from (
                     select service_line.finding_of(d.gap_class) finding
                       from service_line.sourcing_run_member m
                       left join research.diagnosis d on d.request_id=m.request_id
                      where m.run_id=%s) f group by 1""", (run_id,))
    counts = {r["k"]: r["count"] for r in cur.fetchall()}
    emit(cur, run_id, "run_finished", {"counts": counts}, None)
    print(f"finished: {counts}")
    return run_id


def serve(poll_s=5, who=None):
    """Drain the queue the surface writes to. Ctrl-C to stop.

    The claim is a conditional UPDATE, not a read-then-write: two workers polling the
    same second would otherwise both see 'requested' and both drive the same run,
    asking every question twice and interleaving their steps in one stream.
    """
    import socket, time
    who = who or f"worker@{socket.gethostname()}"
    conn, cur = db()
    print(f"worker {who} — polling every {poll_s}s, Ctrl-C to stop")
    seen_idle = False
    while True:
        cur.execute("""update service_line.sourcing_run
                          set status='running', claimed_at=now(), claimed_by=%s
                        where id = (select id from service_line.sourcing_run
                                     where status='requested'
                                     order by started_at limit 1
                                     for update skip locked)
                    returning id, line_key, requested_by, requested_limit, max_rounds,
                              model_profile""",
                    (who,))
        row = cur.fetchone()
        if not row:
            if not seen_idle:
                print("  idle — waiting for a request from the surface")
                seen_idle = True
            time.sleep(poll_s)
            continue
        seen_idle = False
        print(f"\nclaimed {row['id']} ({row['line_key']}) requested by {row['requested_by']}")
        try:
            run(row["line_key"], row["requested_by"], row["requested_limit"],
                False, row["max_rounds"], existing_run=row["id"],
                profile=row["model_profile"])
        except Exception as exc:
            traceback.print_exc()
            cur.execute("""update service_line.sourcing_run
                              set status='failed', finished_at=now(), note=%s
                            where id=%s""", (str(exc)[:400], row["id"]))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("line_key", nargs="?", help="omit with --serve")
    p.add_argument("--serve", action="store_true",
                   help="drain runs requested from the review surface")
    p.add_argument("--by", default="registry")
    p.add_argument("--limit", type=int)
    p.add_argument("--rounds", type=int, default=2)
    p.add_argument("--profile", default=None,
                   help="chat model profile: gemini | anthropic | auto | bandit | "
                        "optimal | default. Omit to take the worker's own default.")
    p.add_argument("--dry", action="store_true")
    a = p.parse_args()
    if a.serve:
        serve()
    elif a.line_key:
        print(run(a.line_key, a.by, a.limit, a.dry, a.rounds, profile=a.profile))
    else:
        p.error("give a line_key, or --serve to take requests from the surface")
