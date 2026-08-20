"""Seed for Lexicon's j:service_line doc-side assignment.

Two independent bases, both provenance — never concept:

  rule_ref         the document IS the policy that governs the line; the rule
                   number is in its filename
  cited_source     the document is where the line's code bindings were read
                   from; it prices the line

The second is what produces the multi-line cases correctly and without guessing.
The CBH fee schedule is the cited source for codes on four different lines, so
it earns four assignments — not because anything matched, but because that is
literally where those bindings came from.

Emits docs/service-lines/service-line-doc-assignment.seed.json as
[{document_id, line_key, basis}], multi-valued by design.
"""
import json
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = "/Users/ananth/Mobius/"
OUT = ROOT + "docs/service-lines/service-line-doc-assignment.seed.json"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")


def main():
    c = psycopg2.connect(DB)
    cur = c.cursor(cursor_factory=RealDictCursor)

    pairs = defaultdict(set)          # (document_id, line_key) -> {basis, ...}
    doc_name = {}

    # ── basis 1: the governing rule, matched on the rule number in the filename
    cur.execute("select key, rule_ref from service_line.line where rule_ref is not null")
    for l in cur.fetchall():
        cur.execute("""select id, filename from documents
                        where status='completed'
                          and (filename ilike %s or display_name ilike %s)""",
                    ("%" + l["rule_ref"] + "%", "%" + l["rule_ref"] + "%"))
        for d in cur.fetchall():
            pairs[(str(d["id"]), l["key"])].add(l["rule_ref"])
            doc_name[str(d["id"])] = d["filename"]

    # ── basis 2: the document a line's bindings were actually read from
    cur.execute("""select distinct c.line_key, c.source_document
                     from service_line.line_code c
                    where c.source_document is not null""")
    cited = cur.fetchall()
    for r in cited:
        cur.execute("select id, filename from documents where filename=%s and status='completed'",
                    (r["source_document"],))
        d = cur.fetchone()
        if not d:
            continue                    # cited but not held — acquisition, not assignment
        pairs[(str(d["id"]), r["line_key"])].add("cited_source")
        doc_name[str(d["id"])] = d["filename"]

    seed = [{"document_id": doc, "line_key": line,
             "basis": " + ".join(sorted(b))}
            for (doc, line), b in sorted(pairs.items(), key=lambda kv: (kv[0][1], kv[0][0]))]
    json.dump(seed, open(OUT, "w"), indent=1)

    per_doc = defaultdict(list)
    for a in seed:
        per_doc[a["document_id"]].append(a["line_key"])
    multi = {d: ls for d, ls in per_doc.items() if len(ls) > 1}

    print(f"wrote {OUT}")
    print(f"  assignments      {len(seed)}")
    print(f"  distinct docs    {len(per_doc)}")
    print(f"  distinct lines   {len({a['line_key'] for a in seed})} of 31")
    print(f"  multi-line docs  {len(multi)}")
    for d, ls in sorted(multi.items(), key=lambda kv: -len(kv[1])):
        print(f"    {doc_name.get(d, d)[:46]:<47}{len(ls)} lines: {', '.join(sorted(ls))}")


if __name__ == "__main__":
    main()
