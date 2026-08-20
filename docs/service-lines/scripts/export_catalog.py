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

        cur.execute("""select document, publisher, authority_level, pages
                       from service_line.source where line_key=%s and held
                       order by pages desc nulls last limit 6""", (key,))
        ev = [{"doc": r[0], "payer": r[1], "authority": r[2], "pages": r[3]} for r in cur.fetchall()]

        rendered = bind["rendered_as"]
        lines.append({
            "key": key, "name": name, "rule": rule, "authority": authority,
            "grain": grain, "scope": "serve" if scope == "serve" else "decline_well",
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
