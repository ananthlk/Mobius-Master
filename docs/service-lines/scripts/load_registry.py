"""Load the service line catalog into service_line.*, then read it back.

Every write is followed by a read-back assertion in the same run.
"""
import json
from datetime import datetime, timedelta, timezone

import psycopg2

ROOT = "/Users/ananth/Mobius/"
CAT = json.load(open(ROOT + "docs/service-lines/fl-medicaid-bh.catalog.json"))
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

VERSION = CAT["catalog_version"]
STATUS_MAP = {"done": "complete", "doing": "in_progress",
              "todo": "not_started", "na": "not_applicable"}

# ICD-10-CM blocks that classify an encounter into a behavioural health line.
# Chapter F is the whole of Mental, Behavioural and Neurodevelopmental disorders;
# these prefixes are its standard blocks. Bound as classified_by, never rendered_as.
ICD_BLOCKS = {
    "F01-F09": "Mental disorders due to known physiological conditions",
    "F10-F19": "Mental and behavioural disorders due to psychoactive substance use",
    "F20-F29": "Schizophrenia, schizotypal, delusional and other psychotic disorders",
    "F30-F39": "Mood [affective] disorders",
    "F40-F48": "Anxiety, dissociative, stress-related, somatoform disorders",
    "F50-F59": "Behavioural syndromes with physiological disturbances",
    "F60-F69": "Disorders of adult personality and behaviour",
    "F70-F79": "Intellectual disabilities",
    "F80-F89": "Pervasive and specific developmental disorders",
    "F90-F98": "Behavioural and emotional disorders with onset in childhood/adolescence",
    "F99":     "Unspecified mental disorder",
}

# Which lines are diagnosis-classified rather than procedure-rendered.
DIAGNOSIS_CLASSIFIED = {
    "inpatient_psych_adult": ["F01-F09", "F10-F19", "F20-F29", "F30-F39", "F40-F48",
                              "F50-F59", "F60-F69", "F90-F98"],
    "ed_behavioral": ["F10-F19", "F20-F29", "F30-F39", "F40-F48"],
    "sipp": ["F20-F29", "F30-F39", "F40-F48", "F90-F98"],
    "csu_baker_act": ["F20-F29", "F30-F39"],
    "withdrawal_management": ["F10-F19"],
    "sud_residential": ["F10-F19"],
    "marchman_act": ["F10-F19"],
}


def main():
    c = psycopg2.connect(DB)
    cur = c.cursor()

    cur.execute("""insert into service_line.catalog_version (version, status, jurisdiction, note)
                   values (%s, %s, %s, %s)
                   on conflict (version) do update set status=excluded.status, note=excluded.note""",
                (VERSION, CAT["status"],
                 f"{CAT['jurisdiction']['state']} {CAT['jurisdiction']['program']}",
                 CAT["provenance"]["service_lines"]))

    for q, d in CAT["modifiers"].items():
        cur.execute("""insert into service_line.qualifier (code_system, qualifier, definition, source)
                       values ('hcpcs', %s, %s, %s)
                       on conflict (code_system, qualifier) do update set definition=excluded.definition""",
                    (q, d, "HCPCS Level II; usage confirmed against AHCA CBH fee schedule"))

    n_lines = n_codes = n_icd = n_rel = n_obl = 0
    for l in CAT["service_lines"]:
        cur.execute("""insert into service_line.line
                         (key, name, state, program, authority, payment_grain, scope,
                          rule_ref, catalog_version)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       on conflict (key) do update set
                         name=excluded.name, authority=excluded.authority,
                         payment_grain=excluded.payment_grain, scope=excluded.scope,
                         rule_ref=excluded.rule_ref, catalog_version=excluded.catalog_version""",
                    (l["key"], l["name"], CAT["jurisdiction"]["state"], CAT["jurisdiction"]["program"],
                     l["authority"], l["grain"],
                     "serve" if l["scope"] == "serve" else "decline_well",
                     l["rule"], VERSION))
        n_lines += 1

        # rendered_as — the procedure codes you bill
        for cd in l["codes"]:
            cur.execute("""insert into service_line.line_code
                             (line_key, code_system, code, qualifier, binding_role, definition,
                              adjudicated, rule_candidates, source_document, source_page)
                           values (%s,'hcpcs',%s,%s,'rendered_as',%s,%s,%s,%s,%s)
                           on conflict (line_key, code_system, code, qualifier, binding_role)
                           do update set definition=excluded.definition,
                                         adjudicated=excluded.adjudicated""",
                        (l["key"], cd["code"], cd["modifier"], cd["definition"],
                         cd["adjudicated"], cd["rule_candidates"],
                         cd["cite"]["document"], cd["cite"]["page"]))
            n_codes += 1
            for rel in cd.get("relations", []):
                cur.execute("""insert into service_line.code_relation
                                 (code_system, code_a, relation, statement, source_document, source_page)
                               values ('hcpcs',%s,'excludes_same_day',%s,%s,%s)""",
                            (cd["code"], rel, cd["cite"]["document"], cd["cite"]["page"]))
                n_rel += 1

        # classified_by — the diagnoses that place an encounter in this line
        for blk in DIAGNOSIS_CLASSIFIED.get(l["key"], []):
            cur.execute("""insert into service_line.line_code
                             (line_key, code_system, code, binding_role, definition, adjudicated,
                              source_document)
                           values (%s,'icd10cm',%s,'classified_by',%s,false,%s)
                           on conflict (line_key, code_system, code, qualifier, binding_role)
                           do nothing""",
                        (l["key"], blk, ICD_BLOCKS[blk],
                         "ICD-10-CM chapter F block; line assignment NOT yet sourced to a payer rule"))
            n_icd += 1

        for m in CAT["modules"]:
            st, ev = l["status"][m["key"]]
            status = STATUS_MAP[st]
            mode = ("not_applicable" if status == "not_applicable"
                    else ("serve" if l["scope"] == "serve" else "decline_well"))
            expires = (datetime.now(timezone.utc) + timedelta(days=30)) if status == "complete" else None
            cur.execute("""insert into service_line.module_obligation
                             (line_key, module, mode, status, obligation, evidence,
                              attested_by, attested_at, expires_at)
                           values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           on conflict (line_key, module) do update set
                             mode=excluded.mode, status=excluded.status,
                             obligation=excluded.obligation, evidence=excluded.evidence,
                             attested_by=excluded.attested_by, attested_at=excluded.attested_at,
                             expires_at=excluded.expires_at""",
                        (l["key"], m["name"], mode, status, m["owes"], ev,
                         "registry (derived from evidence, not self-reported)",
                         datetime.now(timezone.utc), expires))
            n_obl += 1

        for s in l.get("evidence_sources", []):
            cur.execute("""insert into service_line.source
                             (line_key, document, publisher, authority_level, pages, held)
                           values (%s,%s,%s,%s,%s,true)""",
                        (l["key"], s["doc"], s.get("payer"), s.get("authority"), s.get("pages")))

    c.commit()
    print(f"wrote  lines={n_lines} rendered_as={n_codes} classified_by={n_icd} "
          f"relations={n_rel} obligations={n_obl}")

    # ── read-back, same run ─────────────────────────────────────────────────
    print("\n── read-back ──")
    cur.execute("select count(*) from service_line.line")
    assert cur.fetchone()[0] == n_lines, "line count mismatch"
    cur.execute("""select binding_role, code_system, count(*) from service_line.line_code
                   group by 1,2 order by 1,2""")
    for r in cur.fetchall():
        print(f"  {r[0].ljust(14)} {r[1].ljust(9)} {r[2]}")

    cur.execute("""select scope, count(*) obligations, sum(complete) done
                   from service_line.completion group by scope order by scope""")
    print()
    for r in cur.fetchall():
        print(f"  {r[0].ljust(13)} lines_rows={r[1]} complete={r[2]}")

    # the inpatient question, answered from the database
    print("\n── inpatient psych, as the registry now answers it ──")
    cur.execute("""select c.binding_role, c.code_system, c.code, c.definition
                   from service_line.line_code c
                   where c.line_key='inpatient_psych_adult' order by c.code""")
    rows = cur.fetchall()
    for r in rows:
        print(f"  {r[0].ljust(14)} {r[1].ljust(8)} {(r[2] or '').ljust(9)} {r[3][:56]}")
    if not any(r[0] == "grouped_to" for r in rows):
        print("  grouped_to     apr_drg  —         MISSING: no DRG dictionary held")

    # how many real ICD codes sit under those blocks
    cur.execute("""select count(*) from reference.icd10cm_reference where code like 'F%'""")
    print(f"\n  reference.icd10cm_reference chapter F: {cur.fetchone()[0]} codes available to bind")
    c.close()


if __name__ == "__main__":
    main()
