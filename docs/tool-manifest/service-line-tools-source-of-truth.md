# Service Line tools — source of truth

**Owner:** Service Line Registry seat. **Written:** 2026-09-10.
**Against:** `mobius-tool-manifest/docs/tool-description-dimensions.md`.
Seven tools, served by `mobius-payor` at `/api/service-line/*` over
`service_line.*` in `mobius_rag`.

Every number below was measured, not estimated, on the date above. Where a
count would mislead, the misleading reading is named.

---

## Read this first: two thirds of the registry has no data behind it

The single most useful thing for the selector, and the thing least visible from
the code.

| | lines | what a tool call returns |
|---|---|---|
| **billable-code lines** | 7 | codes, limits, coverage, requirements — all real |
| **requirements-only** | 9 | requirements answer; codes/limits/coverage return empty |
| **grouped/per-diem** | 7 | **no billable codes by design** — see below |
| **placeholder or empty** | 8+ | a well-formed answer built on our own placeholder |

The seven with real billable codes, and the only keys for which
`service_line_code_lookup`, `service_line_limits` and `service_line_coverage`
return anything:

```
bh_medication_mgmt  bh_assessment  bh_intervention  fact
bh_community_support  bh_therapy  tcm_children_at_risk
```

### The failure mode that matters more than the empties

**65 of 153 requirement rows carry `origin='asserted'`** — text the registry
wrote as a placeholder, not text read from a rule. They read like findings:

> *"Place-of-service set for this line is stated in its coverage policy; not yet
> extracted."*

A model receiving that gets a grammatical, confident sentence and **cannot tell
it from a sourced fact**. `sourced` is on the row and a caller that ignores it
will report our own to-do list as Florida Medicaid policy. Lines where **every**
requirement is a placeholder:

```
evaluation_management  fqhc_encounter  specialized_therapeutic
state_mental_health  therapeutic_group_care
```

For those keys the honest ranking is: this tool will answer, and its answer
asserts nothing.

### "No codes" does not mean "no data"

Seven lines have zero billable codes **because they are not paid per procedure
code**, and a demotion that reads zero-codes as no-data would be wrong on all
seven:

```
inpatient_psych_adult  72 DRG groupings   APR-DRG, pays relative weight × base rate
ed_behavioral          72 groupings       EAPG, ambulatory grouping
sipp                   48 groupings       per-diem, one rate per day
sud_residential        24                 per-diem
marchman_act           24                 per-diem
withdrawal_management  24                 per-diem
csu_baker_act           —                 per-diem
```

A question about how one of these is *paid* is answerable. A question about
*which code to bill* has the answer "not billed per procedure code", which is a
finding, not an absence.

---

## 1. `service_line_code_lookup`

### The question it answers
- "what service line is H2019 part of"
- "H0031 HO — what is that"
- "which line does T1015 belong to"
- "is H2010 mental health or substance abuse"
- "what does modifier HR mean on H2019"
- "what's the difference between H2019 HR and H2019 HQ"
- "H2019 with HO — same thing as HN?"
- "code on the claim is H0001 TS, what service is that"
- "which behavioral health line covers 90834" *(not held — see boundary)*
- "psychosocial rehab code"
- "what line is this HCPCS under"

### The decision
A biller has a code — usually off a claim, a denial or a fee schedule — and
needs to know which service it represents before deciding anything else about
it.

### Entity vocabulary
HCPCS · CPT · procedure code · billing code · modifier · HO HN HQ HR HM HE HF
HP TS · H0001 H0020 H0031 H0040 H0047 H0048 H2000 H2010 H2012 H2017 H2019 H2030
T1015 T2023 · APR-DRG · EAPG · DRG · severity of illness · ICD-10-CM · diagnosis
code · service line · rendered as · grouped to · classified by · behavioral
health · Florida Medicaid · AHCA

### What the user has in hand
A code, usually with a modifier. Sometimes only a partial code, or a code with
the modifier omitted — which matters, because the modifier is what distinguishes
the service.

### What this does NOT answer
The dollar amount. The registry holds no rates. It also does not hold every
HCPCS code — only those bound to a Florida Medicaid behavioural health service
line, which is **18 distinct billable codes across 58 bindings**. A CPT code
such as 90834 is not in it and the correct response is that it is not held, not
a guess at the nearest line.

### Coverage
58 `rendered_as` bindings · 18 distinct codes · 14 distinct modifiers · **7
lines**. Plus 264 APR-DRG/EAPG groupings across 18 distinct grouper codes and 21
ICD-10-CM diagnosis bindings, which answer "how is this grouped", not "what do I
bill".

**The grain is `(code, modifier)`, never a bare code.** H2019 alone is five
different services; H2019 with HR is one. A lookup on the bare code returns
several lines and that is correct, not ambiguity to be resolved by picking one.

### Arguments
`code` required, exact. `modifier` optional — supplying it narrows to one
service; omitting it returns every binding for the code.

### Return shape
Envelope: `status` (`found` | `known_absent` | `unknown`), one-sentence `answer`,
`caveats[]` with stable machine codes, `citations[]`, `data`, `query`, `meta`.
Branch on `caveats[].code`, never on the prose.

### Failure modes
A code we do not hold returns `status: unknown` — an admission, not a denial.
`known_absent` means something different and stronger: we hold the governing
document and it is silent. Collapsing the two produces a confidently wrong
answer.

---

## 2. `service_line_limits`

### The question it answers
- "how many units of H2019 HR per year"
- "what's the cap on psychosocial rehab"
- "is there a daily limit on H2010"
- "how many assessments can we bill per recipient"
- "annual limit for behavioral health overlay"
- "can we bill more than 4 units a day"
- "units per state fiscal year for H2017"
- "what happens if we exceed the limit"
- "limit on brief behavioral health status exam"

### The decision
Whether a planned or already-delivered service is inside the benefit, before
billing it or before appealing a denial that says it was not.

### Entity vocabulary
service limit · unit limit · cap · maximum · units per day · units per week ·
units per month · per state fiscal year · SFY · per recipient · quarter hour ·
15-minute unit · encounter · visit · per diem · unlimited · exceedable ·
authorisation above the cap

### What the user has in hand
A code and modifier, or a service-line name, and usually a number of units they
are trying to justify.

### What this does NOT answer
Whether a specific recipient has already consumed the limit. The registry holds
the rule, never claim history or a member's remaining balance.

### Coverage
**62 limit rows across only 6 lines.** Every other line returns empty — including
lines that certainly have limits in their rule and have simply not been sourced.
An empty result here is far more often "not yet extracted" than "no limit
exists", which is the opposite of the natural reading.

**`caps_not_additive`**: 15 `(code, modifier)` pairs are bound to more than one
service line, so a naive sum across lines double-counts. Summing gives 208 for a
104-unit cap. The caveat fires when it applies and its absence is information.

### Arguments
`code` + optional `modifier`, or `line`. Modifier changes the answer: H2019 HR
is 104 units per state fiscal year; H2019 HQ is 156.

### Failure modes
Empty is ambiguous by nature here and the envelope disambiguates it: `unknown`
means not sourced, `known_absent` means the rule was read and states none.

---

## 3. `service_line_coverage`

### The question it answers
- "is H0031 covered by Florida Medicaid"
- "does Medicaid pay for clubhouse services"
- "is this service covered for adults"
- "covered or not — H2030"
- "does FL Medicaid cover peer support"
- "is telehealth allowed for this code"
- "can we bill this at all"

### The decision
Whether to deliver or bill a service at all.

### Entity vocabulary
covered · coverage · reimbursable · payable · billable · excluded · not covered ·
telehealth · telemedicine · same-day exclusion · not reimbursable on the same day

### What this does NOT answer
Whether a particular claim will pay. Coverage is the rule; adjudication depends
on eligibility, authorisation, the rendering provider and the plan.

### Coverage
**58 rows across 7 lines.** Two bases, and they differ in strength: a coverage
sentence quoted from a policy, versus a rate appearing on a fee schedule. A rate
listing is strong evidence of coverage and is not a coverage statement — the
distinction is carried in the row.

**Same-day exclusions are held but not surfaced by this tool**: 29 rules across
9 codes live in `service_line.code_relation` (for example, a brief behavioural
assessment is not reimbursable the same day as a psychiatric evaluation). A
coverage answer that omits them can be true and still lead a biller into a
denial.

### Failure modes
`unknown` for any of the 24 lines with no benefit rows.

---

## 4. `service_line_search`

### The question it answers
- "find the line for psychosocial rehabilitation"
- "what services are there for substance abuse"
- "search for assertive community treatment"
- "is there a line for mobile crisis"
- "H2019" *(codes match too)*
- "targeted case management"
- "which lines cover children"
- "baker act"

### The decision
Orientation — the user does not yet know which service line they need.

### Entity vocabulary
Service names and their vernacular: psychosocial rehabilitation · PSR ·
clubhouse · FACT · assertive community treatment · TBOS · therapeutic behavioral
on-site · targeted case management · TCM · Baker Act · Marchman Act · CSU ·
crisis stabilisation · SIPP · statewide inpatient psychiatric · QRTP · IOP · PHP ·
withdrawal management · detox · CBHA · behavioural health overlay · medication
management · MAT

### Coverage
All **31** lines are searchable by name and vernacular, and codes match as well —
a biller arrives with the code on the claim more often than the service name.
Searchability is not data: a line can be found and then have nothing behind it.

### What this does NOT answer
Anything about the line it finds. It returns identity, not content.

---

## 5. `service_line_detail`

### The question it answers
- "tell me about behavioral health assessment services"
- "what's in the psychosocial rehab line"
- "everything on TCM for children at risk"
- "which rule governs FACT"
- "how is inpatient psych paid"
- "what codes are in this line"

### The decision
A user has identified a line and wants the whole picture before acting.

### Coverage
All 31 lines return. **What comes back varies enormously** and the shape is the
same either way — this is the tool most likely to look complete while being
empty. 18 of 31 name a governing rule; 7 carry billable codes; 8 have no
requirements at all.

### What this does NOT answer
Rates. Provider enrolment status. Anything member-specific.

---

## 6. `service_line_requirements`

### The question it answers
- "does H2019 need prior authorization"
- "do we need a PA for psychosocial rehab"
- "what documentation do we need for this service"
- "who can render this service"
- "what licence level for modifier HO"
- "can a bachelors-level practitioner bill this"
- "what place of service codes apply"
- "is a diagnosis required"
- "what supervision is required"
- "what has to be in the chart"
- "age limits on this service"

### The decision
Whether the service can be billed as delivered — before delivering it, or when
answering a denial that says a condition was not met.

### Entity vocabulary
prior authorization · PA · precert · authorisation · documentation · chart notes ·
progress notes · medical record · place of service · POS · setting · provider
qualification · licence · licensure · credential · bachelors · masters ·
doctoral · supervision · supervising practitioner · medical necessity · coverage
criteria · eligibility · age · population · referral · order

### Coverage — read this before ranking it

**153 rows, 88 sourced, 65 placeholders.** By type:

```
credentialing            48 rows  47 sourced
place_of_service         21 rows   2 sourced      <- 19 placeholders
documentation            21 rows   5 sourced
coverage_criteria        21 rows   7 sourced
prior_authorization      21 rows   6 sourced
provider_qualification   11 rows  11 sourced
supervision               6 rows   6 sourced
age_population            4 rows   4 sourced
```

`place_of_service`, `documentation`, `coverage_criteria` and `prior_authorization`
were **seeded as placeholders on 21 lines each** and mostly never filled. A
question about place of service is the single most likely to receive our own
wording back.

Two further limits on the sourced ones:
- a sourced requirement may still rest on a citation nobody has followed;
- three were unfiled on 2026-09-09 for citing a health plan on a state-rule
  question, which is inadmissible. That check runs now; rows sourced before it
  existed have not all been re-examined.

`setting` and `referral_order` are declared types with **zero rows** — a question
about either returns nothing, always.

### Failure modes
The important one is not an error. It is a fluent placeholder returned with
`sourced: false`, which a caller that does not read that field will present as
policy.

---

## 7. `service_line_gaps`

### The question it answers
- "what's missing from the registry"
- "which service lines have no data"
- "what still needs sourcing"
- "how complete is the behavioral health registry"
- "which requirements have never been answered"
- "what are we waiting on documents for"

### The decision
Operational, not clinical. Someone is deciding what to work on, or judging
whether an answer elsewhere can be trusted.

### Entity vocabulary
gap · missing · unsourced · not sourced · incomplete · coverage · backlog ·
awaiting sources · placeholder · never attempted · stale

### Coverage
Complete by construction — it reports absence, so it is the one tool whose
answer is fully backed for every line. **24 of 31 lines are awaiting sources.**

### What this does NOT answer
It reports what the registry lacks, not what the corpus lacks. A requirement can
be unsourced while the governing document sits in the index — which was true
three times this week, and each time the natural reading ("go acquire it") was
wrong.

---

## Cross-cutting

**One envelope, every tool.** `status` / `answer` / `caveats[]` / `citations[]` /
`data` / `query` / `meta`. `caveats[]` carries stable machine codes and is
**conditional** — a caveat is absent when it does not apply, so its presence is
information. Branch on the code, never on the sentence.

**Three states that must never collapse**: `found` · `known_absent` (we hold the
document and it is silent — a real answer) · `unknown` (we hold nothing — an
admission). A code that is not covered and a code nobody sourced look identical
to a caller that treats both as "no".

**Latency**: sub-second, one Postgres round trip, no model call, no external
fetch. These are cheap enough to call speculatively.

**What no tool here holds**: rates and fee amounts (Fact Store), member
eligibility or benefit balances, claim adjudication, appeals rules, provider
enrolment status.
