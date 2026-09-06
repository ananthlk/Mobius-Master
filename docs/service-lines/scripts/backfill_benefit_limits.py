"""Turn the prose service limits in line_code.general_rule into computable limits.

The 343 code bindings carry 52 codes with a general_rule — the limit sentence as
the AHCA fee schedule states it. You can read those. You cannot compute against
them, so nothing can check a claim with them.

This is TRANSCRIPTION, not inference, and the distinction is the whole design:

  * Every reading below is keyed on the EXACT sentence. There is no regex over
    prose, no number pulled out by pattern. 28 distinct sentences exist; each one
    was read and structured by hand, and is written here where it can be argued
    with.
  * A sentence not in the table is NOT parsed. It stays prose and shows up in
    service_line.benefit_limit_gap. Silence is the correct output for anything
    unread.
  * `statement` stores the sentence verbatim as held, so every structured row
    round-trips to the words it came from.
  * `sourced` is true only because both source documents are in the corpus and
    can be opened. It is a claim about the document, not about our confidence.

Two readings are judgement rather than transcription, and are called out as
such rather than buried:

  H0032/T1007 development  "one treatment plan per provider, per state fiscal
                           year" is stored as per_whom='recipient_per_provider',
                           not 'provider'. Read literally, 'provider' would cap a
                           provider at one treatment plan per YEAR across every
                           recipient, which the paired sentence ("a maximum total
                           of two treatment plans per recipient") contradicts.
  T1015 medication mgmt    "as medically necessary" is a real sourced answer of
                           NO numeric cap: unlimited=true. It must not read the
                           same as a limit we never sourced.

And one sentence is deliberately REFUSED:

  T2023/HA  "Maximum 1 unit per month." states a number and never defines the
            unit. By the table's own CHECK constraint that is an incomplete
            answer, not a limit. It stays in the gap view where Deep Research
            can source what a TCM unit is.
"""
import psycopg2

ROOT = "/Users/ananth/Mobius/"
DB = [l.split("=", 1)[1].strip().strip('"').strip("'")
      for l in open(ROOT + "mobius-rag/.env") if l.startswith("DATABASE_URL")][0].replace("+asyncpg", "")

QH = "15 minutes (quarter-hour unit)"
SFY = "state_fiscal_year"

# sentence (verbatim, as held) -> (limit_type, amount, unit_definition, period, per_whom)
# amount None with unlimited intent is expressed by the sentinel UNLIMITED.
UNLIMITED = "UNLIMITED"

READING = {
 "event Medicaid reimburses 52 behavioral health-related medical services: medical procedures, per recipient, per state fiscal year.":
   ("encounters", 52, "one behavioral health-related medical service (medical procedure)", SFY, "recipient"),
 "event Medicaid reimburses 52 behavioral health – related medical services: alcohol and other drug screening specimen collections, per recipient, per state fiscal year.":
   ("encounters", 52, "one alcohol and other drug screening specimen collection", SFY, "recipient"),
 "quarter hour There is a maximum daily limit of two quarter-hour units.":
   ("units", 2, QH, "day", None),
 "There is a maximum daily limit of four quarter-hour units (1 hour).":
   ("units", 4, QH, "day", None),
 "assessment Medicaid reimburses one in-depth assessment, per recipient, per state fiscal year.":
   ("evaluations", 1, "one in-depth assessment", SFY, "recipient"),
 "assessment Medicaid reimburses one biopsychosocial evaluation, per recipient, per state fiscal year.":
   ("evaluations", 1, "one biopsychosocial evaluation", SFY, "recipient"),
 "assessment Medicaid reimburses a maximum of three limited functional assessments, per recipient, per state fiscal year.":
   ("evaluations", 3, "one limited functional assessment", SFY, "recipient"),
 "evaluation Medicaid reimburses a maximum of two psychiatric evaluations per recipient, per state fiscal year.":
   ("evaluations", 2, "one psychiatric evaluation", SFY, "recipient"),
 "review Medicaid reimburses a maximum of two psychiatric reviews of records, per recipient, per state fiscal year.":
   ("evaluations", 2, "one psychiatric review of records", SFY, "recipient"),
 "quarter hour Medicaid reimburses a maximum of 1920 quarter-hour units (480 hours) annually, per recipient, per state fiscal year.":
   ("units", 1920, QH, SFY, "recipient"),
 "quarter hour Medicaid reimburses a maximum of 1,920 quarter-hour units (480 hours) of psychosocial rehabilitation services, per recipient, per state fiscal year.":
   ("units", 1920, QH, SFY, "recipient"),
 "Medicaid reimburses a maximum of 16 quarter-hour units (4 hours) of brief individual medical psychotherapy, per recipient, per state fiscal year.":
   ("units", 16, QH, SFY, "recipient"),
 "Medicaid reimburses a maximum of 16 quarter-hour units (4 hours) of brief individual medical psychotherapy, per recipient, per state fiscal year.* Brief individual medical psychotherapy is not reimbursable on the same day, for the same recipient, as brief group medical therapy or medication management.":
   ("units", 16, QH, SFY, "recipient"),
 "Medicaid reimburses a maximum of 18 quarter-hour units (4.5 hours) of group medical therapy, per recipient, per state fiscal year.":
   ("units", 18, QH, SFY, "recipient"),
 "Medicaid reimburses for brief behavioral health status examinations a maximum of 10 quarter-hour units annually (2.5 hours), per recipient, per state fiscal year.":
   ("units", 10, QH, SFY, "recipient"),
 "quarter Medicaid reimburses a maximum of 104 quarter-hour units (26 hours) of individual and family therapy services, per recipient, per state fiscal year.":
   ("units", 104, QH, SFY, "recipient"),
 "quarter hour Medicaid reimburses a maximum of 156 quarter-hour units (39 hours) of group therapy services, per recipient, per state fiscal year.":
   ("units", 156, QH, SFY, "recipient"),
 "quarter hour Medicaid reimburses a maximum of 40 quarter-hour units (10 hours) of psychological testing per state fiscal year.":
   ("units", 40, QH, SFY, None),
 "quarter hour Medicaid reimburses therapeutic behavioral on-site therapeutic support services for a maximum of 128 quarter-hour units per month (32 hours), per recipient.":
   ("units", 128, QH, "month", "recipient"),
 "quarter hour Medicaid reimburses therapeutic behavioral on-site therapy services a maximum combined limit of a total of 36 15- minute units per month.":
   ("units", 36, "15 minutes", "month", None),
 "quarter hour Medicaid reimburses therapeutic behavioral on-site behavior management and therapeutic behavioral on-site therapy services for a maximum combined total of 36 15-minute units per month.":
   ("units", 36, "15 minutes", "month", None),
 "event Medicaid reimburses a maximum of four treatment plan reviews, per recipient, per state fiscal year.":
   ("encounters", 4, "one treatment plan review", SFY, "recipient"),
 "event Medicaid reimburses for the development of one treatment plan per provider, per state fiscal year.":
   ("encounters", 1, "development of one treatment plan", SFY, "recipient_per_provider"),
 "Medicaid reimburses for a maximum total of two treatment plans per recipient per state fiscal year.":
   ("encounters", 2, "one treatment plan", SFY, "recipient"),
 "event Medicaid reimburses two behavioral health medical screening services, per recipient, per state fiscal year.":
   ("encounters", 2, "one behavioral health medical screening service", SFY, "recipient"),
 "rate Medicaid reimburses medication assisted treatment services 52 times, per recipient, per state fiscal year.":
   ("encounters", 52, "one medication assisted treatment service", SFY, "recipient"),
 "event Medicaid reimburses medication management as medically necessary.":
   ("encounters", UNLIMITED, None, None, None),
}

# Read, and deliberately not structured. Keeping the reason next to the sentence
# is the point — an empty result with no explanation is indistinguishable from a
# bug.
REFUSED = {
 "Maximum 1 unit per month.":
   "states an amount but never defines the unit; incomplete by the table's own "
   "unit_count_needs_unit_definition constraint. Left for Deep Research to source.",
}


def main():
    c = psycopg2.connect(DB)
    cur = c.cursor()

    cur.execute("""select line_key, code_system, code, qualifier, general_rule,
                          source_document, source_page, rate_authority
                     from service_line.line_code
                    where general_rule is not null and general_rule <> '{}'
                    order by line_key, code, qualifier""")
    rows = cur.fetchall()

    cur.execute("select filename from documents where status='completed'")
    held = {r[0] for r in cur.fetchall()}

    docs = {r[5] for r in rows if r[5]}
    # Rebuild only what this script owns, so a re-run cannot double-insert.
    cur.execute("delete from service_line.benefit_limit where source_ref = any(%s)",
                (sorted(docs),))
    removed = cur.rowcount

    written = skipped = 0
    unknown = {}
    for line_key, cs, code, qual, rules, doc, page, auth in rows:
        for sentence in rules:
            r = READING.get(sentence)
            if r is None:
                if sentence in REFUSED:
                    skipped += 1
                else:
                    unknown[sentence] = unknown.get(sentence, 0) + 1
                continue
            ltype, amount, unit_def, period, per_whom = r
            unlimited = amount is UNLIMITED
            cur.execute("""insert into service_line.benefit_limit
                             (line_key, code_system, code, qualifier, limit_type,
                              amount, unit_definition, period, per_whom, unlimited,
                              statement, authority, source_ref, source_page, sourced)
                           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           on conflict do nothing""",
                        (line_key, cs, code, qual or None, ltype,
                         None if unlimited else amount, unit_def, period, per_whom,
                         unlimited, sentence, auth or "AHCA|FL|Medicaid",
                         doc, page, doc in held))
            written += cur.rowcount

    c.commit()

    print(f"removed prior rows   {removed}")
    print(f"limits written       {written}")
    print(f"refused (incomplete) {skipped}")
    if unknown:
        print(f"\nUNREAD sentences — not structured, left as prose:")
        for s, n in sorted(unknown.items(), key=lambda kv: -kv[1]):
            print(f"  [{n}] {s[:100]}")

    cur.execute("""select count(*), count(*) filter (where sourced),
                          count(*) filter (where unlimited),
                          count(distinct line_key), count(distinct code)
                     from service_line.benefit_limit""")
    n, s, u, lines, codes = cur.fetchone()
    print(f"\nbenefit_limit: {n} rows · {s} sourced · {u} unlimited · "
          f"{lines} lines · {codes} codes")

    cur.execute("select count(distinct (line_key, code, qualifier)) from service_line.benefit_limit_gap")
    print(f"still prose-only (benefit_limit_gap): {cur.fetchone()[0]} code bindings")

    print("\nreads_as sample:")
    cur.execute("""select line_key, code, qualifier, reads_as from service_line.benefit_limit_answer
                    order by line_key, code, qualifier limit 12""")
    for lk, code, q, reads in cur.fetchall():
        print(f"  {lk:<22} {code:<6} {(q or ''):<3} {reads}")


if __name__ == "__main__":
    main()
