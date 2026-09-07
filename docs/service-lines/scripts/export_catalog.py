"""Export the catalog from service_line.* — the database is the master.

build_master.py seeds the database from AHCA sources. From then on the database
is authoritative and this script regenerates the JSON and the page from it, so
the artifact can never drift from what modules actually read.
"""
import json
from datetime import date

import psycopg2

ROOT = "/Users/ananth/Mobius/"
OUT = ROOT + "docs/service-lines/fl-medicaid-bh.catalog.json"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

BACK = {"complete": "done", "in_progress": "doing", "not_started": "todo", "not_applicable": "na"}
ROLES = ("rendered_as", "classified_by", "grouped_to")


def main():
    c = psycopg2.connect(DB)
    cur = c.cursor()

    cur.execute("select version, status, jurisdiction from service_line.catalog_version order by version desc limit 1")
    version, status, juris = cur.fetchone()

    cur.execute("select key, name, steward, qualifier_kind, reference_table, license_note "
                "from service_line.code_system order by key")
    systems = [{"key": r[0], "name": r[1], "steward": r[2], "qualifier_kind": r[3],
                "dictionary_held": r[4] is not None, "reference_table": r[4],
                "license_note": r[5]} for r in cur.fetchall()]

    cur.execute("""select code_a, array_agg(statement order by id)
                   from service_line.code_relation group by code_a""")
    relations = dict(cur.fetchall())

    cur.execute("select qualifier, definition from service_line.qualifier where code_system='hcpcs'")
    modifiers = dict(cur.fetchall())

    cur.execute("""select distinct module, obligation from service_line.module_obligation""")
    owes = {}
    for m, o in cur.fetchall():
        owes.setdefault(m, o)
    # Stable keys: the page addresses modules by key, never by display name.
    MODULES = [("facts", "Fact Store", "facts & rates"),
               ("lexicon", "Lexicon", "vocabulary"),
               ("cred", "Credentialing", "who may render"),
               ("appeals", "Appeals", "denial playbook"),
               ("analytics", "Analytics", "marts & benchmarks"),
               ("chat", "Chat / RAG", "the answer")]
    modules = [{"key": k, "name": n, "role": r, "owes": owes.get(n, "")}
               for k, n, r in MODULES]

    cur.execute("select filename from documents where status='completed'")
    _held = {r[0] for r in cur.fetchall()}

    cur.execute("""select key, name, authority, payment_grain, scope, rule_ref, payment_method
                   from service_line.line
                   order by (scope <> 'serve'), payment_grain, key""")
    lines = []
    for key, name, authority, grain, scope, rule, method in cur.fetchall():
        cur.execute("""select code_system, code, qualifier, binding_role, definition,
                              adjudicated, rule_candidates, source_document, source_page,
                              general_rule, standard_rate, standard_rate_unit, payment_basis,
                              telemedicine, rate_authority
                       from service_line.line_code where line_key=%s
                       order by binding_role, code, qualifier""", (key,))
        def provenance(src):
            """Three states, never two. 'sourced' means we can open the document."""
            if not src:
                return ("asserted", "Registry judgement — no document cited.")
            if src in _held:
                return ("sourced", "Cites a document in the corpus.")
            if "NOT yet sourced" in src or "not yet" in src.lower():
                return ("asserted", "Registry judgement — " + src)
            return ("unheld", "Read from a real document we do NOT hold: " + src)

        bind = {r: [] for r in ROLES}
        for (cs, code, q, role, dfn, adj, cands, doc, page,
             grule, rate, runit, basis, tele, rauth) in cur.fetchall():
            bind[role].append({"code_system": cs, "code": code, "modifier": q,
                               "definition": dfn, "adjudicated": adj,
                               "rule_candidates": cands or [],
                               "relations": sorted(set(relations.get(code, []))) if role == "rendered_as" else [],
                               "general_rule": grule or [],
                               "standard_rate": float(rate) if rate is not None else None,
                               "standard_rate_unit": runit, "payment_basis": basis,
                               "telemedicine": tele, "rate_authority": rauth,
                               "provenance": provenance(doc)[0],
                               "provenance_note": provenance(doc)[1],
                               "cite": {"document": doc, "page": page}})

        cur.execute("""select module, status, evidence from service_line.module_obligation
                       where line_key=%s""", (key,))
        by_name = {m: [BACK[s], e or ""] for m, s, e in cur.fetchall()}
        st = {k: by_name.get(n, ["todo", "Module has not reported."]) for k, n, _ in MODULES}

        cur.execute("""select predicate, label, payer_key, resolves_from, owner,
                              answer_text, authority_level, cert_status
                       from service_line.requirement_resolution where line_key=%s
                       order by predicate, payer_key nulls last""", (key,))
        reqs = {}
        for pred, lbl, payer, res, owner, ans, alvl, cert in cur.fetchall():
            r = reqs.setdefault(pred, {"predicate": pred, "label": lbl, "answers": []})
            if payer:
                r["answers"].append({"payer": payer, "answer": ans, "resolves_from": res,
                                     "owner": owner, "cert_status": cert, "authority_level": alvl})
        for r in reqs.values():
            r["has_standard"] = any(a["resolves_from"] == "standard" for a in r["answers"])
            r["deltas"] = [a for a in r["answers"] if a["resolves_from"] == "payor_delta"]
        requirements = sorted(reqs.values(), key=lambda x: (not x["answers"], x["predicate"]))

        cur.execute("""select requirement_type, statement, source_ref, sourced, authority, qualifier
                       from service_line.standard_requirement where line_key=%s
                       order by sourced desc, requirement_type, statement""", (key,))
        std_reqs = [{"type": r[0], "statement": r[1], "source": r[2], "sourced": r[3],
                     "authority": r[4], "qualifier": r[5]} for r in cur.fetchall()]

        cur.execute("""select domain, other_store, question_asked, payer_key, answer, statement
                       from service_line.exception_asks where line_key=%s
                       order by domain, (payer_key <> '*'), payer_key""", (key,))
        asks = [{"domain": r[0], "other_store": r[1], "question": r[2], "payer": r[3],
                 "answer": r[4], "statement": r[5]} for r in cur.fetchall()]

        cur.execute("""select spec->'query_expansion_phrases'
                       from policy_lexicon_entries
                       where kind='j' and active and code=%s""", ('service_line.' + key,))
        _r = cur.fetchone()
        jphrases = (_r[0] if _r else None) or []

        cur.execute("""select d.filename, a.basis from (
                         select distinct c.source_document fn, 'cited_source' basis
                           from service_line.line_code c
                          where c.line_key=%s and c.source_document is not null
                       ) a join documents d on d.filename = a.fn and d.status='completed'""", (key,))
        jdocs = [{"document": r[0], "basis": r[1]} for r in cur.fetchall()]

        # Three stages, read from the index rather than assumed. A seeded
        # assignment retrieves NOTHING until Lexicon applies it and the tag
        # propagates to published chunks.
        cur.execute("""select count(*) from document_tags
                        where j_tags::text like %s""", ('%service_line.' + key + '%',))
        tagged_docs = cur.fetchone()[0]
        cur.execute("""select count(*) from rag_published_embeddings
                        where chunk_j_tags::text like %s""", ('%service_line.' + key + '%',))
        tagged_chunks = cur.fetchone()[0]

        cur.execute("""select d_code, relation, state, confidence, evidence, requested_concept
                       from service_line.line_lexicon_d where line_key=%s
                       order by state, confidence desc nulls last, d_code""", (key,))
        lex = [{"d_code": r[0], "relation": r[1], "state": r[2],
                "confidence": float(r[3]) if r[3] is not None else None,
                "evidence": r[4], "requested_concept": r[5]} for r in cur.fetchall()]

        # Coverage — is this a covered benefit under the standard, and on what
        # evidence. A row exists only where a held document supports it.
        cur.execute("""select code, qualifier, covered, population, benefit_category,
                              statement, source_ref, source_page, sourced
                       from service_line.benefit where line_key=%s
                       order by code, qualifier nulls first""", (key,))
        cov = [{"code": r[0], "modifier": r[1], "covered": r[2], "population": r[3],
                "category": r[4], "statement": r[5], "source": r[6], "page": r[7],
                "sourced": r[8],
                # A quoted sentence and a read table row are not equal evidence,
                # and the card must be able to say which it is standing on.
                "basis": "quoted" if "Medicaid reimburses" in (r[5] or "") else "rate_listed"}
               for r in cur.fetchall()]

        # Limits, and what is still prose. The gap is exported alongside the
        # answer deliberately — a card that shows only the structured rows reads
        # as if the prose ones do not exist.
        cur.execute("""select code, qualifier, limit_type, reads_as, amount,
                              unit_definition, period, per_whom, unlimited,
                              exceedable_by, statement, source_ref, sourced
                       from service_line.benefit_limit_answer where line_key=%s
                       order by code, qualifier nulls first, period, limit_type""", (key,))
        limits = [{"code": r[0], "modifier": r[1], "limit_type": r[2], "reads_as": r[3],
                   "amount": float(r[4]) if r[4] is not None else None,
                   "unit_definition": r[5], "period": r[6], "per_whom": r[7],
                   "unlimited": r[8], "exceedable_by": r[9], "statement": r[10],
                   "source": r[11], "sourced": r[12]} for r in cur.fetchall()]

        cur.execute("""select code, qualifier, general_rule
                       from service_line.benefit_limit_gap where line_key=%s
                       order by code, qualifier""", (key,))
        limit_gap = [{"code": r[0], "modifier": r[1], "prose": r[2] or []} for r in cur.fetchall()]

        # System state, not domain fact: how this line got sourced, whether the
        # state machine is still working on it, and whether the other modules
        # have caught up. This is what "technical details" should mean.
        cur.execute("""select outcome, count(*), max(attempted_at)
                         from service_line.sourcing_attempt where line_key=%s
                        group by 1 order by 2 desc""", (key,))
        attempts = [{"outcome": r[0], "n": r[1], "last": str(r[2])[:16] if r[2] else None}
                    for r in cur.fetchall()]

        # Route through sourcing_link, not a LIKE on subject_id. The old convention
        # packed the line into a composite string ('bh_therapy/place_of_service'), which
        # is exactly what contract §4.5 is about: 0 of 9 such requests could be joined
        # to a requirement. New runs send the requirement id as the subject, so a
        # prefix match would silently stop finding them.
        cur.execute("""select r.id, r.status,
                              coalesce(sl.requirement_type,
                                       split_part(r.subject_id, '/', 2), r.subject_id) about,
                              (select count(*) from research.turn t where t.request_id = r.id),
                              d.gap_class,
                              service_line.finding_of(d.gap_class) finding,
                              service_line.repair_owner(d.gap_class, d.action) owner
                         from research.request r
                         left join service_line.sourcing_link sl on sl.request_id = r.id
                         left join lateral (select * from research.diagnosis d2
                                             where d2.request_id = r.id
                                             order by d2.created_at desc limit 1) d on true
                        where sl.line_key = %s
                           or (sl.line_key is null and r.consumer = 'service_line_registry'
                               and r.subject_id like %s)
                        order by r.id""", (key, key + "%"))
        machine = [{"ref": r[0], "state": r[1], "about": (r[2] or "").replace("_", " "),
                    "rounds": r[3], "gap": r[4], "finding": r[5], "owner": r[6]}
                   for r in cur.fetchall()]

        # Runs: what a button started, and every step it produced. This is the object
        # the surface streams live and replays afterwards — contract §7, one renderer
        # for both. Registry's own events plus the state machine's turns, attempts and
        # diagnoses, already unioned and ordered by service_line.run_stream.
        cur.execute("""select id, requested_by, status, task_count, started_at, finished_at, note
                         from service_line.sourcing_run where line_key = %s
                        order by started_at desc limit 10""", (key,))
        runs = []
        for rr in cur.fetchall():
            cur.execute("""select at, source, kind, seq, text, data
                             from service_line.run_stream where run_id = %s
                            order by at, source, seq nulls first, kind""", (rr[0],))
            events = [{"at": str(e[0])[11:19], "source": e[1], "kind": e[2],
                       "seq": e[3], "text": e[4], "data": e[5]} for e in cur.fetchall()]
            cur.execute("""select m.seq, m.requirement_type, m.code, p.finding, p.gap_class,
                                  p.repair_owner, p.quote, p.source_document, p.citation
                             from service_line.sourcing_run_member m
                             left join service_line.requirement_provenance p
                                    on p.request_id = m.request_id
                            where m.run_id = %s order by m.seq""", (rr[0],))
            tasks = [{"seq": t[0], "about": (t[1] or "").replace("_", " "), "code": t[2],
                      "finding": t[3], "gap": t[4], "owner": t[5], "quote": t[6],
                      "document": t[7],
                      # Registry's own corpus verdict on the citation, never the
                      # producer's word for it. 88 of 97 kept field quotes point at
                      # something a reviewer cannot follow; the surface must say so
                      # beside the quote rather than presenting it as evidence.
                      "citation": t[8]}
                     for t in cur.fetchall()]
            runs.append({"id": str(rr[0]), "by": rr[1], "status": rr[2], "tasks": rr[3],
                         "started": str(rr[4])[:16], "finished": str(rr[5])[:16] if rr[5] else None,
                         "note": rr[6], "events": events, "items": tasks})

        # The review queue for this line: every reviewable fact, its origin, and
        # what a person has decided about it. origin says how the value came to
        # exist; review_state says what a human concluded. Approving an
        # interpreted value never makes it parsed — the UI must not merge them.
        cur.execute("""select subject_kind, subject_id, code, qualifier, origin,
                              sourced, source_ref, value_text, binding_role,
                              code_system, review_state, actor, decided_at
                         from service_line.review_queue
                        where line_key = %s
                        order by (origin <> 'asserted'), subject_kind,
                                 code nulls first, subject_id""", (key,))
        review = [{"kind": r[0], "id": r[1], "code": r[2], "modifier": r[3],
                   "origin": r[4], "sourced": r[5], "source": r[6],
                   "value": r[7], "role": r[8], "system": r[9],
                   "state": r[10], "actor": r[11],
                   "decided_at": str(r[12]) if r[12] else None}
                  for r in cur.fetchall()]

        cur.execute("""select document, publisher, authority_level, pages
                       from service_line.source where line_key=%s and held
                       order by pages desc nulls last limit 6""", (key,))
        ev = [{"doc": r[0], "payer": r[1], "authority": r[2], "pages": r[3]} for r in cur.fetchall()]

        rendered = bind["rendered_as"]
        lines.append({
            "key": key, "name": name, "rule": rule, "authority": authority,
            "grain": grain, "scope": scope,
            "payment_method": method,
            "fee_schedule_family": None,
            "source_documents": 0,
            "codes": rendered,
            "code_count": len(rendered),
            "distinct_codes": len({x["code"] for x in rendered}),
            "allowed_modifiers": sorted({x["modifier"] for x in rendered if x["modifier"]}),
            "unadjudicated_codes": sum(1 for x in rendered if not x["adjudicated"]),
            "bindings": {r: bind[r] for r in ROLES},
            "binding_counts": {r: len(bind[r]) for r in ROLES},
            "provenance_counts": {
                r: {"sourced": sum(1 for x in bind[r] if x["provenance"] == "sourced"),
                    "unheld": sum(1 for x in bind[r] if x["provenance"] == "unheld"),
                    "asserted": sum(1 for x in bind[r] if x["provenance"] == "asserted")}
                for r in ROLES},
            "registry_asserted": [
                {"field": "authority", "value": authority},
                {"field": "payment grain", "value": grain},
                {"field": "how it is paid", "value": method},
            ],
            "j_service_line": {"query_phrases": jphrases, "documents": jdocs,
                               "seeded": len(jdocs), "tagged_documents": tagged_docs,
                               "retrievable_chunks": tagged_chunks},
            "lexicon_d": lex,
            "lexicon_d_counts": {
                "mapped": sum(1 for x in lex if x["d_code"]),
                "confirmed": sum(1 for x in lex if x["state"] == "confirmed"),
                "requested": sum(1 for x in lex if x["state"] == "requested"),
            },
            "benefit_coverage": cov,
            "benefit_counts": {
                "covered": sum(1 for x in cov if x["covered"]),
                "codes": len({(x["code"], x["modifier"]) for x in cov}),
                "quoted": sum(1 for x in cov if x["basis"] == "quoted"),
                "rate_listed": sum(1 for x in cov if x["basis"] == "rate_listed"),
                "sourced": sum(1 for x in cov if x["sourced"]),
                "category": (cov[0]["category"] if cov else None),
                "population": sorted({x["population"] for x in cov if x["population"]}),
            },
            "benefit_limits": limits,
            "benefit_limit_gap": limit_gap,
            "benefit_limit_counts": {
                "limits": len(limits),
                "codes": len({(x["code"], x["modifier"]) for x in limits}),
                "unlimited": sum(1 for x in limits if x["unlimited"]),
                "sourced": sum(1 for x in limits if x["sourced"]),
                "prose_only": len(limit_gap),
            },
            "sourcing_attempts": attempts,
            "state_machine": machine,
            "runs": runs,
            "review": review,
            "review_counts": {
                "total": len(review),
                "unreviewed": sum(1 for x in review if x["state"] == "unreviewed"),
                "approved": sum(1 for x in review if x["state"] == "approve"),
                "rejected": sum(1 for x in review if x["state"] == "reject"),
                "by_origin": {o: sum(1 for x in review if x["origin"] == o)
                              for o in ("parsed", "interpreted", "asserted", "human")},
            },
            "standard_requirements": std_reqs,
            "standard_requirement_counts": {
                "sourced": sum(1 for r in std_reqs if r["sourced"]),
                "unsourced": sum(1 for r in std_reqs if not r["sourced"]),
            },
            "exception_asks": asks,
            "payor_requirements": requirements,
            "requirement_counts": {
                "applies": len(requirements),
                "answered": sum(1 for r in requirements if r["answers"]),
                "standard": sum(1 for r in requirements if r["has_standard"]),
                "deltas": sum(len(r["deltas"]) for r in requirements),
                "payers": len({a["payer"] for r in requirements for a in r["answers"]}),
            },
            "evidence_pages": sum(x["pages"] or 0 for x in ev),
            "evidence_sources": ev,
            "status": st,
        })

    cur.execute("""select domain, registry_owns, other_store, other_owns, question_asked,
                          standard_held_by from service_line.linked_store order by domain""")
    seam = [{"domain": r[0], "registry_owns": r[1], "other_store": r[2], "other_owns": r[3],
             "question_asked": r[4], "standard_held_by": r[5]} for r in cur.fetchall()]

    catalog = {
        "ownership": seam,
        "catalog_version": version, "status": status, "generated": str(date.today()),
        "jurisdiction": {"state": juris.split()[0], "program": " ".join(juris.split()[1:]),
                         "regulator": "AHCA"},
        "master": "service_line.* in mobius_rag — this JSON is an export, not the source of truth",
        "provenance": {
            "service_lines": "AHCA 59G rule decomposition plus the acute/facility lines CMHCs run",
            "codes": "AHCA fee schedules and DRG rate worksheet; dictionaries in reference.*",
            "grain": "(code, qualifier) — HCPCS modifier or APR-DRG severity of illness",
        },
        "code_systems": systems,
        "modifiers": modifiers,
        "modules": modules,
        "service_lines": lines,
    }
    json.dump(catalog, open(OUT, "w"), indent=2)

    tot = sum(l["binding_counts"][r] for l in lines for r in ROLES)
    print(f"exported {len(lines)} lines, {tot} code bindings → {OUT}")
    for r in ROLES:
        print(f"  {r.ljust(14)} {sum(l['binding_counts'][r] for l in lines)}")


if __name__ == "__main__":
    main()
