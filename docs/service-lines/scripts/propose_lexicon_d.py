"""Propose which Lexicon `d` codes describe each service line.

Deterministic on purpose. Every proposal carries the evidence that produced it —
which phrase in the d code matched which text in the line — so Lexicon can argue
with a specific claim rather than a score. No LLM guessing at vocabulary the
registry does not own.

Matching runs over the line's own words: its canonical name, and the source
definitions of every code bound to it. A d code is proposed when one of its
`strong_phrases` (or its code leaf) appears in that text.

The valuable output is not the matches. It is the lines that match NOTHING —
those are concepts the registry binds and the vocabulary cannot express, and
they are written as state='requested' so Lexicon sees the gap rather than an
empty result.
"""
import re

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = "/Users/ananth/Mobius/"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

# d-code families and what relation they carry to a line.
FAMILY_RELATION = [
    ("place_of_service", "setting"),
    ("health_care_services.behavioral_health", "describes"),
    ("health_care_services", "describes"),
    ("claims.reimbursement", "payment"),
    ("care_management", "describes"),
]

# A matched phrase can mean something else in context. "abuse" inside "substance
# abuse" is not child abuse reporting; "review" inside "psychiatric review of
# records" is not utilisation review. Guard the term by what precedes it.
CONTEXT_GUARD = {
    "abuse": {"substance", "drug", "alcohol", "other"},
    "review": {"records", "plan"},
    "screening": {"specimen"},
}

STOP = {"services", "service", "health", "behavioral", "the", "and", "for", "of", "a",
        "florida", "medicaid", "program", "general", "other", "care", "with", "new",
        "patient", "established", "mental", "in", "to", "by", "or"}


def relation_for(code: str) -> str:
    for prefix, rel in FAMILY_RELATION:
        if code.startswith(prefix):
            return rel
    return "describes"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())


def main():
    c = psycopg2.connect(DB)
    c.autocommit = True
    cur = c.cursor(cursor_factory=RealDictCursor)

    cur.execute("""select code, spec->>'description' descr, spec->'strong_phrases' phrases
                     from policy_lexicon_entries where kind='d' and active""")
    d_codes = []
    for r in cur.fetchall():
        phrases = r["phrases"] or []
        leaf = r["code"].rsplit(".", 1)[-1].replace("_", " ")
        terms = {norm(p).strip() for p in phrases if p and len(p) > 3}
        terms.add(norm(leaf).strip())
        d_codes.append({"code": r["code"], "descr": r["descr"], "terms": {t for t in terms if len(t) > 3}})
    print(f"d codes considered: {len(d_codes)}")

    cur.execute("""select l.key, l.name, l.scope,
                          coalesce(string_agg(distinct c.definition, ' | '), '') defs
                     from service_line.line l
                     left join service_line.line_code c
                            on c.line_key = l.key and c.binding_role = 'rendered_as'
                    group by l.key, l.name, l.scope
                    order by (l.scope <> 'serve'), l.key""")
    lines = cur.fetchall()

    proposed = requested = 0
    for l in lines:
        haystack = norm(f"{l['name']} {l['defs']}")
        hits = []
        for d in d_codes:
            for t in d["terms"]:
                if not t or t in STOP or t not in haystack:
                    continue
                guard = CONTEXT_GUARD.get(t)
                if guard:
                    # Look at the word immediately before each occurrence.
                    before = {m.group(1) for m in
                              re.finditer(r"(\w+)\s+" + re.escape(t), haystack)}
                    if before and before <= guard:
                        continue
                hits.append((d["code"], t, d["descr"]))
                break
        # Keep the most specific match per d-code family so one line does not
        # collect forty near-duplicate ancestors.
        seen_family = {}
        for code, term, descr in sorted(hits, key=lambda h: -len(h[0])):
            fam = code.split(".")[0] + "." + (code.split(".")[1] if "." in code else "")
            if fam in seen_family and len(seen_family[fam]) >= 4:
                continue
            seen_family.setdefault(fam, []).append(code)
            rel = relation_for(code)
            conf = round(min(0.9, 0.4 + len(term) / 40), 2)
            cur.execute("""insert into service_line.line_lexicon_d
                             (line_key, d_code, relation, state, confidence, evidence)
                           values (%s,%s,%s,'proposed',%s,%s)
                           on conflict (line_key, d_code, relation) do nothing""",
                        (l["key"], code, rel, conf,
                         f'matched phrase "{term}" against the line name and its code '
                         f'definitions; d code means: {(descr or "")[:90]}'))
            proposed += cur.rowcount

        if not hits:
            cur.execute("""insert into service_line.line_lexicon_d
                             (line_key, d_code, relation, state, requested_concept, evidence)
                           values (%s,NULL,'describes','requested',%s,%s)
                           on conflict do nothing""",
                        (l["key"], l["name"],
                         "No active d code shares any phrase with this line's name or its "
                         "code definitions. The vocabulary cannot currently express it."))
            requested += cur.rowcount

    print(f"proposed {proposed} line->d_code mappings")
    print(f"requested {requested} new d codes (no vocabulary exists)\n")

    cur.execute("""select line_key, name, scope, proposed, requested, d_codes
                     from service_line.lexicon_coverage order by d_codes, line_key""")
    print(f"{'LINE':<26}{'D CODES':>8}  STATE")
    print("-" * 74)
    for r in cur.fetchall():
        state = "NO VOCABULARY" if r["requested"] else ""
        print(f"{r['line_key']:<26}{r['d_codes']:>8}  {state}")


if __name__ == "__main__":
    main()
