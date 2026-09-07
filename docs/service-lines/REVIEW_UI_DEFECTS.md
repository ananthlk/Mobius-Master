# Service Lines review surface — defect list

**Found:** 2026-09-07, walking the page against real data rather than eyeballing.
**Status:** logged, not fixed. Ananth: *"just mark all the bugs and we will fix
them once for all."*

Ordered by what a reviewer hits first, not by effort. Each one names how it was
measured so nobody has to re-derive it.

---

## 1. The same sentence appears three times on one code — **worst defect**

`H0001 with HO` shows three rows, two of them word-for-word identical:

```
Medicaid reimburses one in-depth assessment, per recipient, per state fiscal year.   From the fee schedule
Medicaid reimburses one in-depth assessment, per recipient, per state fiscal year.   Read from the policy
In-depth assessment, new patient, substance abuse                                    From the fee schedule
```

They are three different records — the coverage answer, the limit, and the code
definition — and **nothing on the surface says which is which.** The `kind` is
only visible after opening "Why this is here."

**Measured:** 51 of 127 distinct texts on code cards appear more than once. Both
the coverage row and the limit row were sourced from the same fee-schedule
sentence, so they will keep colliding.

**Not a styling fix.** Either each row states what it is ("Coverage", "Limit",
"What the code means") or the three merge into one row with the value shown once
and its several sources listed. Merging is probably right: a reviewer confirming
"is this the correct limit for H0001 HO" should decide once, not three times.

---

## 2. "Applies to the whole service" is a dumping ground

Anything whose code is not one of the billable codes falls into it. That is
**285 rows across the registry**, and they are not service-wide facts:

| Service | Items | What they actually are |
|---|---|---|
| Inpatient Psychiatric — adult | 80 | APR-DRG groupings |
| Emergency Department behavioral health | 76 | APR-DRG groupings |
| Statewide Inpatient Psychiatric Program | 57 | 52 DRG + 5 requirements |
| Marchman Act services | 25 | diagnosis groupings |

A reviewer opening adult inpatient psych meets eighty rows reading
`MENTAL ILLNESS DIAGNOSIS WITH O.R. PROCEDURE`, four of which are that exact
string, before anything they can act on.

**Cause:** diagnosis (`classified_by`) and DRG (`grouped_to`) bindings are being
treated as billable-code review items. They are neither service-wide nor
billable — they answer "what diagnosis places this encounter", which is a
different question and arguably does not belong on this surface at all.

**Where it is right:** `bh_assessment` shows 7 genuine service-wide items —
place of service, prior authorisation, three practitioner-level rules,
documentation, eligibility. That is what the section is for.

---

## 3. Four severity levels render as four identical rows

`MENTAL ILLNESS DIAGNOSIS WITH O.R. PROCEDURE` appears **4×**, `SCHIZOPHRENIA`
**4×** — one per APR-DRG severity of illness (1–4). The severity is the only
thing distinguishing them and it is not shown. Fixing #2 may remove these from
the surface entirely; if they stay, severity has to be on the row.

---

## 4. Unsourced services invite a review that cannot be done

20 services sit under "Awaiting sources" and still show a count — `Behavior
Analysis Services 4`, `Mental Health Targeted Case 22`. Those items are
placeholders in our own words with no document behind them. Confirming one would
mean approving our own guess, which is the one thing the schema forbids.

**Fix direction:** these should not read as "to check". They are "to source".
Different verb, different queue, and Confirm should not be offered on them at
all — only Edit, or a Find a source action.

---

## 5. Four services show nothing whatsoever

`Baker Act involuntary examination` and three others: 0 codes, 0 items, 0 to
check, and no count in the rail. The page renders the empty state, which is
honest, but the rail gives no signal that opening it is pointless.

---

## 6. The collapsed rail is unusable

At 48px every service is an identical grey dot — no initials, no icon, no
tooltip. Nothing distinguishes nine services. Chat's collapsed sidebar solves
this already; copy whatever it does rather than invent.

---

## 7. Sidebar names truncate mid-word

`Behavioral Health Assessme… 35`, `Behavioral Health Medication … 43`. Six of
the seven ready services begin "Behavioral Health", so the truncation removes
exactly the part that distinguishes them. Consider dropping the common prefix in
the rail, or a tooltip carrying the full name.

---

## 8. "COVERED 9" means nothing to a reviewer

Covered *what*? It is a row count from `service_line.benefit`. Next to
"BILLABLE CODES 9" it reads as a duplicate of the same number — which today it
is, on every ready service. Either say what it counts or drop the tile.

**Open question, not a defect:** whether the KPI row earns its place above the
codes at all.

---

## 9. Search only matches service names

Typing `H0031` or `psychosocial` finds nothing. A billing user is far more
likely to arrive with a code than with a service name — the code is what is on
the claim in front of them.

---

## 10. "Show everything to check" does not do what it says

It jumps to the first service with pending items. It does not show everything.
A cross-service work queue is what a reviewer actually wants, and it is a
structural addition rather than a rename.

---

## Fixed already, recorded so they are not re-found

- Cards clipped their own titles — `.main` is a flex column and children shrink
  by default, so cards were squeezed to fit the viewport and `overflow:hidden`
  cut the headers. `.main > * {flex:0 0 auto}`.
- `1 evaluations (one in-depth assessment) per state_fiscal_year per recipient` —
  plural on 1, redundant gloss, raw enum. Rebuilt from parts; the exact unit
  definition moved to the evidence panel.
- `rate Medicaid reimburses…` — the fee schedule's unit column bled into the
  extraction. Stripped for display, kept verbatim in the evidence panel.
