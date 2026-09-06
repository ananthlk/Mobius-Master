"""Backfill service_line.benefit — is this a covered benefit under the standard.

Coverage is the STATE's answer, not ours, so this writes only what a held
document supports. Two bases exist in the corpus, and they are not equally
strong, so the row says which one it stands on:

  quoted       the rule's own sentence says "Medicaid reimburses ..." for this
               service. The words are the evidence; they go in verbatim.
  rate_listed  no sentence, but AHCA publishes a reimbursement rate for this
               exact (code, modifier) on a fee schedule we hold. A published
               rate IS the state paying for the service — but it is a table row
               being read, not a sentence being quoted, so the statement says so
               in those terms and names the rate a reader can check.

What this deliberately does NOT do:

  * No line-level coverage. 24 of 31 lines have no code bound and no held
    document. "Florida Medicaid covers partial hospitalisation" is almost
    certainly true and we cannot source it, so nothing is written and the line
    shows as uncovered-unknown rather than as not covered.
  * No coverage for the decline_well lines on the strength of our own reasoning.
    048's comment notes Medicaid covers Baker Act receiving-facility services
    while Mobius declines them — that asymmetry is exactly why covered must come
    from a document and not from the registry's scope decision.
  * No effective_from. The schedule is titled 2025 and the exact effective date
    lives inside the document, unparsed. A year is not a date, and inventing
    2025-01-01 would make a fabricated fact look sourced.

population comes only from the modifier dictionary, which is a real source:
HA is defined as "Child/adolescent program", so a binding carrying HA is a
benefit restricted to that population. No other modifier in this set carries a
population — HE and HF name a programme, not who is eligible.
"""
import re

import psycopg2

ROOT = "/Users/ananth/Mobius/"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

# The benefit grouping, taken from the document's own title. The CBH schedule is
# a flat table with a repeating header and no section headings — verified by
# reading all four pages — so the title is the only grouping the source states.
CATEGORY = {
    "2025 Community Behavoir Health Fee Schedule.pdf": "Community Behavioral Health",
    "TCM_for_Children_At-Risk_2022_Fee_Schedule.pdf": "Targeted Case Management, Children At-Risk",
}

POPULATION = {"HA": "Child/adolescent"}

REIMBURSES = re.compile(r"Medicaid reimburses", re.I)


def main():
    c = psycopg2.connect(DB)
    cur = c.cursor()

    cur.execute("select filename from documents where status='completed'")
    held = {r[0] for r in cur.fetchall()}

    cur.execute("""select line_key, code_system, code, qualifier, definition,
                          general_rule, standard_rate, standard_rate_unit,
                          source_document, source_page, rate_authority
                     from service_line.line_code
                    where binding_role = 'rendered_as'
                    order by line_key, code, qualifier""")
    rows = cur.fetchall()

    docs = {r[8] for r in rows if r[8]}
    cur.execute("delete from service_line.benefit where source_ref = any(%s)", (sorted(docs),))
    removed = cur.rowcount

    written = 0
    basis_count = {"quoted": 0, "rate_listed": 0}
    skipped_no_doc = 0

    for (line_key, cs, code, qual, dfn, rules, rate, unit,
         doc, page, auth) in rows:
        if not doc:
            skipped_no_doc += 1
            continue

        quote = next((s for s in (rules or []) if REIMBURSES.search(s)), None)
        if quote:
            statement, basis = quote, "quoted"
        elif rate is not None:
            statement = (f"Listed on the {CATEGORY.get(doc, doc)} fee schedule at "
                         f"${rate:,.2f} {unit or ''}".rstrip() +
                         f" for {code}" + (f" with modifier {qual}" if qual else " with no modifier") +
                         f" ({dfn}). AHCA publishes a reimbursement rate for this "
                         f"pair, which is the state paying for the service; the "
                         f"schedule states no coverage sentence for it.")
            basis = "rate_listed"
        else:
            skipped_no_doc += 1
            continue

        basis_count[basis] += 1
        cur.execute("""insert into service_line.benefit
                         (line_key, code_system, code, qualifier, benefit_category,
                          covered, population, statement, authority,
                          source_ref, source_page, sourced)
                       values (%s,%s,%s,%s,%s,true,%s,%s,%s,%s,%s,%s)
                       on conflict do nothing""",
                    (line_key, cs, code, qual or None, CATEGORY.get(doc),
                     POPULATION.get(qual), statement, auth or "AHCA|FL|Medicaid",
                     doc, page, doc in held))
        written += cur.rowcount

    c.commit()

    print(f"removed prior rows        {removed}")
    print(f"coverage rows written     {written}")
    print(f"  from a quoted sentence  {basis_count['quoted']}")
    print(f"  from a published rate   {basis_count['rate_listed']}")
    print(f"no document, not written  {skipped_no_doc}")

    # ── read-backs ──────────────────────────────────────────────────────────
    cur.execute("""select count(*), count(*) filter (where sourced),
                          count(*) filter (where covered),
                          count(distinct line_key), count(distinct code)
                     from service_line.benefit""")
    n, s, cov, lines, codes = cur.fetchone()
    print(f"\nbenefit: {n} rows · {s} sourced · {cov} covered · {lines} lines · {codes} codes")

    cur.execute("select count(*) from service_line.benefit where not sourced")
    assert cur.fetchone()[0] == 0, "a coverage row was written without a held document"

    cur.execute("""select l.key, l.scope from service_line.line l
                    where not exists (select 1 from service_line.benefit b where b.line_key = l.key)
                    order by (l.scope <> 'serve'), l.key""")
    gap = cur.fetchall()
    print(f"\nlines with NO coverage answer: {len(gap)} of 31 — no code bound, no held document")
    for k, sc in gap:
        print(f"  {k:<26}{sc}")

    cur.execute("""select population, count(*) from service_line.benefit
                    where population is not null group by 1""")
    for p, cnt in cur.fetchall():
        print(f"\npopulation-restricted: {cnt} rows · {p}")


if __name__ == "__main__":
    main()
