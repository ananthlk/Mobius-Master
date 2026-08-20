"""Per-line definition packets for Lexicon.

The registry page shows a line at six levels. A user can ask at any of them, so
the dictionary has to reach all six — a code→alias list only covers one:

  1 the line itself          "was he Baker Acted"        -> csu_baker_act
  2 the authority            "the Baker Act"             -> FL Statute 394
  3 how it is paid           "per diem", "DRG", "EAPG"   -> payment_grain
  4 what you bill            "bio-psych"                 -> H0031 HN
  5 what classifies it       "substance use", "SUD"      -> ICD F10-F19
  6 what it groups to        "schizophrenia admission"   -> APR-DRG 750

Every element gets a `vernacular` slot Lexicon fills, and a `needs` note saying
what kind of language belongs there. Nothing here is a suggested alias — the
registry has no business guessing clinical vernacular, and a wrong guess in this
domain is worse than a blank.

Emits docs/service-lines/lexicon-packets.json.
"""
import json

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = "/Users/ananth/Mobius/"
OUT = ROOT + "docs/service-lines/lexicon-packets.json"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

NEEDS = {
    "line": "What a clinician, intake coordinator or CMHC director calls this service. "
            "Include the verb form people actually use ('Baker Acted', 'Marchman'd').",
    "authority": "What people call the governing law or rule, not its citation.",
    "payment": "How billing staff refer to this payment shape.",
    "code": "What practitioners and intake forms call THIS service at THIS modifier. "
            "The modifier changes the service — do not write one alias set for the bare code.",
    "diagnosis": "How the presenting problem is described in referral and intake language.",
    "drg": "How an admission for this is described in plain speech.",
}


def main():
    c = psycopg2.connect(DB)
    cur = c.cursor(cursor_factory=RealDictCursor)

    cur.execute("select qualifier, definition from service_line.qualifier where code_system='hcpcs'")
    MOD = {r["qualifier"]: r["definition"] for r in cur.fetchall()}

    cur.execute("""select key, name, rule_ref, authority, payment_grain, payment_method, scope
                     from service_line.line order by (scope <> 'serve'), key""")
    packets = []
    for l in cur.fetchall():
        key = l["key"]

        cur.execute("""select code_system, code, qualifier, binding_role, definition,
                              general_rule, adjudicated, source_document
                         from service_line.line_code where line_key=%s
                         order by binding_role, code, qualifier""", (key,))
        binds = cur.fetchall()

        rendered, classified, grouped = [], [], {}
        for b in binds:
            if b["binding_role"] == "rendered_as":
                rendered.append({
                    "code": b["code"], "qualifier": b["qualifier"],
                    "qualifier_means": MOD.get(b["qualifier"]),
                    "source_definition": b["definition"],
                    "service_limits": b["general_rule"] or [],
                    "source": b["source_document"],
                    "vernacular": [], "needs": NEEDS["code"],
                })
            elif b["binding_role"] == "classified_by":
                classified.append({
                    "block": b["code"], "source_definition": b["definition"],
                    "adjudicated": b["adjudicated"],
                    "vernacular": [], "needs": NEEDS["diagnosis"],
                })
            else:  # grouped_to — collapse the four severities into one entry
                g = grouped.setdefault(b["code"], {
                    "drg": b["code"], "severities": [],
                    "source_definition": b["definition"],
                    "vernacular": [], "needs": NEEDS["drg"]})
                if b["qualifier"]:
                    g["severities"].append(b["qualifier"])

        cur.execute("""select requirement_type, statement, sourced
                         from service_line.standard_requirement where line_key=%s
                        order by sourced desc, requirement_type""", (key,))
        reqs = [dict(r) for r in cur.fetchall()]

        cur.execute("""select document, publisher, pages from service_line.source
                        where line_key=%s and held order by pages desc nulls last limit 6""", (key,))
        evidence = [dict(r) for r in cur.fetchall()]

        packets.append({
            "line_key": key,
            "identity": {
                "canonical_name": l["name"], "scope": l["scope"],
                "vernacular": [], "needs": NEEDS["line"],
            },
            "authority": {
                "value": l["authority"], "rule_ref": l["rule_ref"],
                "vernacular": [], "needs": NEEDS["authority"],
            },
            "payment": {
                "grain": l["payment_grain"], "how_it_is_paid": l["payment_method"],
                "vernacular": [], "needs": NEEDS["payment"],
            },
            "rendered_as": rendered,
            "classified_by": classified,
            "grouped_to": sorted(grouped.values(), key=lambda g: g["drg"]),
            "standard_requirements": reqs,
            "corpus_evidence": evidence,
        })

    doc = {
        "purpose": "One packet per service line, mirroring every level of the registry page. "
                   "Lexicon fills each `vernacular` array; the registry fills nothing there.",
        "rules": [
            "A modifier changes the service. H0031 is four different services at "
            "'', HN, HO and TS — never one alias set for the bare code.",
            "TS is not 'established patient' globally. On H0032 it turns treatment plan "
            "DEVELOPMENT into REVIEW. Modifier meaning is per-code.",
            "H0001 is the substance-use twin of H0031 with near-identical English. The "
            "SUD/MH split is carried by the code, not the words.",
            "Lines with no bindings still need vernacular — that is where user language "
            "is strongest and our evidence weakest.",
        ],
        "lines": packets,
    }
    json.dump(doc, open(OUT, "w"), indent=1)

    slots = sum(1 for p in packets for _ in [p["identity"], p["authority"], p["payment"]]) \
        + sum(len(p["rendered_as"]) + len(p["classified_by"]) + len(p["grouped_to"]) for p in packets)
    print(f"wrote {OUT}")
    print(f"  lines            {len(packets)}")
    print(f"  vernacular slots {slots}")
    for lvl, n in [("rendered_as", sum(len(p['rendered_as']) for p in packets)),
                   ("classified_by", sum(len(p['classified_by']) for p in packets)),
                   ("grouped_to (base DRGs)", sum(len(p['grouped_to']) for p in packets))]:
        print(f"    {lvl:<24}{n}")


if __name__ == "__main__":
    main()
