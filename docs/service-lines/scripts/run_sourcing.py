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


def run(line_key, requested_by, limit=None, dry=False, max_rounds=2):
    conn, cur = db()
    cur.execute("select key, name from service_line.line where key=%s", (line_key,))
    line = cur.fetchone()
    if not line:
        sys.exit(f"no such service line: {line_key}")

    reqs = targets(cur, line_key, limit=limit)
    if not reqs:
        sys.exit(f"{line_key}: nothing unsourced to source")

    cur.execute("""insert into service_line.sourcing_run (line_key, requested_by, task_count)
                   values (%s,%s,%s) returning id""", (line_key, requested_by, len(reqs)))
    run_id = cur.fetchone()["id"]

    gov = governing(cur, line_key)
    emit(cur, run_id, "run_started",
         {"line_key": line_key, "line_name": line["name"], "task_count": len(reqs),
          "requested_by": requested_by},
         f"Sourcing {len(reqs)} requirements for {line['name']}.")
    emit(cur, run_id, "governing_resolved", gov,
         (f"Governing rule {gov['rule_ref']} is held — {gov['chunks']} sections readable."
          if gov["resolvable"] else
          f"Governing rule {gov.get('rule_ref') or '(none recorded)'}: {gov['why']}."))

    print(f"run {run_id}  {line['name']}  {len(reqs)} requirements")
    print(f"  governing: {gov}")
    if dry:
        cur.execute("""update service_line.sourcing_run
                          set status='cancelled', finished_at=now(),
                              note='dry run — nothing asked' where id=%s""", (run_id,))
        print("  (dry run — nothing asked)")
        return run_id

    from deep_research.service import open_and_run   # noqa: E402

    for seq, r in enumerate(reqs, 1):
        rtype = r["requirement_type"]
        subject = line["name"] + (f" (code {r['code']})" if r["code"] else "")
        question = (f"For {JURISDICTION}: " + ASK[rtype].format(subject=subject) +
                    (f" The governing rule is {gov['rule_ref']}." if gov["rule_ref"] else "") +
                    " Quote the governing policy text and name the source document.")
        # §4.5 — subject_id must resolve. Until the producer accepts a structured
        # subject we send the requirement id itself, which is the only string that
        # joins. The composite convention ('bh_therapy/service_limit_H2019_HR') is
        # exactly what 0 of 9 existing requests could not be filed under.
        subject_id = str(r["id"])

        # Create the request row HERE, not inside open_and_run, so membership carries a
        # request_id from the start. Without this the live stream shows nothing from the
        # state machine until a task FINISHES — the joins to research.turn/attempt have
        # no key to join on — which is a progress bar that only moves once the work is
        # already done. open_and_run upserts on the same (consumer, subject_type,
        # subject_id) conflict target, so it adopts this row rather than making a second.
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
              "code": r["code"], "expects": list(SLOTS[rtype]), "question": question},
             None, seq)
        print(f"  [{seq}/{len(reqs)}] {rtype}{' ' + r['code'] if r['code'] else ''} …", flush=True)

        try:
            res = open_and_run(
                consumer="service_line_registry", subject_type="standard_requirement",
                subject_id=subject_id, question=question, evaluator_prompt=EVAL,
                extraction_schema=SLOTS[rtype], jurisdiction=JURISDICTION,
                max_rounds=max_rounds)
        except Exception as exc:
            traceback.print_exc()
            emit(cur, run_id, "error", {"requirement_id": r["id"], "error": str(exc)[:500]},
                 f"{rtype} failed to run.", seq)
            continue

        rid = res.get("request_id")
        if rid != pre_id:
            # open_and_run should have adopted our row via the conflict target. If it
            # did not, the stream has been following the wrong request all along — say
            # so loudly rather than quietly repointing and losing the earlier steps.
            emit(cur, run_id, "error",
                 {"expected_request_id": pre_id, "got": rid},
                 "The state machine opened a different request than the one this run "
                 "was following; live steps for this task were not captured.", seq)
            cur.execute("""update service_line.sourcing_run_member set request_id=%s
                            where run_id=%s and seq=%s""", (rid, run_id, seq))
        emit(cur, run_id, "request_settled",
             {"requirement_id": r["id"], "request_id": rid, "status": res.get("status"),
              "turns": res.get("turns_run"), "gap_class": res.get("gap_class"),
              "document": res.get("source_document")},
             res.get("statement"), seq)
        print(f"        -> {res.get('status')} in {res.get('turns_run')} turn(s)"
              f"{' [' + str(res.get('gap_class')) + ']' if res.get('gap_class') else ''}", flush=True)

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


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("line_key")
    p.add_argument("--by", default="registry")
    p.add_argument("--limit", type=int)
    p.add_argument("--rounds", type=int, default=2)
    p.add_argument("--dry", action="store_true")
    a = p.parse_args()
    print(run(a.line_key, a.by, a.limit, a.dry, a.rounds))
