# Service Line Registry API → chat tool manifest

**From:** Service Line Registry · **For:** Chat Master / ReAct
**Service:** `mobius-payor` · **Prefix:** `/api/service-line` · all GET, no auth beyond the service's own
**Status:** built, 19/19 endpoint tests green against live data, **not yet deployed** — see §6

---

## 1. What this is for

The registry holds the FL Medicaid behavioural-health master contract: which
services we serve, what codes bill them, what the published standard covers, how
much may be billed, and on whose authority. Chat currently answers these from
retrieval over fee-schedule PDFs, which is how you get *"H2017 is 1,920 units"*
from a table slab that is mostly about other codes.

These endpoints answer from certified rows instead. Every answer cites the
document it came from.

## 2. The one rule that matters

**Every response carries `status`, and the three values are not
interchangeable:**

| `status` | Meaning | What chat must do |
|---|---|---|
| `found` | We hold a sourced answer | Answer, and cite `source_ref` |
| `known_absent` | We looked. The governing document **is held** and is **silent**. | Say the source does not state it. **Do not** infer, and do not fall back to retrieval and present the result as equivalent. |
| `unknown` | We hold nothing | Say we do not have it. **This is not a denial.** |

The failure this prevents: *"is H0032 covered?"* → nothing found → chat answers
"no". A code we never sourced and a code that is genuinely not covered are
different facts, and a naive API makes them identical.

Each payload also carries a `note` written for the model. It is not decoration —
it states the trap for that specific endpoint. Put it in the tool result.

## 3. Tools to register

Seven tools over eleven endpoints. Names are suggestions; shapes are not.

### `service_line_code_lookup(code, modifier?)`
`GET /api/service-line/codes/{code}` — optional `?modifier=`

What a HCPCS/CPT code actually is: every `(code, modifier)` pair, its definition,
rate, payment basis, telemedicine flag, coverage and limits.

> **A bare code is not one service.** `H0031` is four billable services at ``,
> `HN`, `HO`, `TS` — four definitions, four rates, four rules. The response
> returns `pair_count` and `modifiers`. If the user did not give a modifier and
> `pair_count > 1`, present the alternatives or ask; never answer for the bare
> code.

### `service_line_limits(code, modifier?)`
`GET /api/service-line/codes/{code}/limits`

How much may be billed.

> **Quote `distinct_readings`, not `limits`.** 15 `(code, modifier)` pairs are
> bound to more than one service line, so `limits` repeats each cap per line.
> `H2019/HR` returns 4 rows for 2 real caps. Summing them answers 208 for a
> 104-unit cap.
>
> **A service usually has more than one cap.** H2019/HR is 4 units/day *and*
> 104 units/state fiscal year. Both apply. Returning only the larger is wrong.
>
> `unlimited: true` means the source affirmatively states no numeric cap
> ("as medically necessary"). That is an answer, not a blank.
>
> `status: known_absent` with `not_computable` populated means the schedule
> states an amount and never defines the unit. Give the raw wording; do not
> guess what a unit is.

### `service_line_coverage(code, modifier?)`
`GET /api/service-line/codes/{code}/coverage`

Whether the published standard covers it, plus any population restriction.

> `basis` says how strong the evidence is: `quoted_rule` is the rule's own
> sentence; `published_rate` means AHCA prints a rate for the pair and we read
> the table row. Both sourced, not equal. Prefer quoting a `quoted_rule`.
>
> This is the **AHCA/CMS standard only**. A payor covering less, or capping
> tighter, is a delta held by the Fact Store — say so rather than implying the
> standard binds a specific plan.

### `service_line_search(q)`
`GET /api/service-line/search?q=`

Free text across line names, code definitions and coverage statements. Use when
the user names a service in words — "psychosocial rehab", "group therapy",
"Baker Act" — and you need the line key or code before another call.

### `service_line_detail(line_key)`
`GET /api/service-line/lines/{key}` · list via `GET /api/service-line/lines`

The whole card for one line: codes, coverage, limits, prose-only limits,
standard requirements.

> `scope: decline_well` means **Florida Medicaid covers this and Mobius does not
> serve it.** Decline the work; do not say the service does not exist. Ten of
> the 31 lines are in this state.

### `service_line_requirements(line_key?, requirement_type?)`
`GET /api/service-line/requirements`

What the standard requires to bill: place of service, documentation,
supervision, credentialing, prior authorisation, provider qualification.

> **`sourced: false` rows are placeholders.** They name a requirement we know
> exists and have not extracted. The `statement` on an unsourced row is our
> wording, not policy. Never quote it. Currently 78 of 153 are sourced.

### `service_line_gaps()`
`GET /api/service-line/gaps`

What the registry does *not* know: lines with no coverage answer (24 of 31),
limits that stayed prose (1), requirements unsourced (~64).

> Call this before telling a user something is not covered. All three are gaps
> in what we hold, not findings about the benefit.

## 4. Suggested routing

| User asks | Tool |
|---|---|
| "what is H2017" / "can I bill H0031 HN" | `code_lookup` |
| "how many units of X" / "is there a daily cap" | `limits` |
| "is X covered" / "who is it covered for" | `coverage` |
| "what can I bill for psychosocial rehab" | `search` → `code_lookup` |
| "what do I need to bill bh_assessment" | `requirements` |
| "do you do partial hospitalisation" | `detail` (check `scope`) |
| any "is X not covered" | `gaps` first |

## 5. Worked example — the whole point

**"How many units of H2019 with modifier HR can we bill per year?"**

`service_line_limits(code="H2019", modifier="HR")` →

```json
{ "status": "found",
  "lines": ["bh_intervention", "fact"],
  "note": "... bound to 2 service lines, so `limits` repeats each cap per line.
           Quote `distinct_readings` — the caps are the SAME allowance, not additive.",
  "distinct_readings": [
    { "amount": 104, "limit_type": "units", "unit_definition": "15 minutes (quarter-hour unit)",
      "period": "state_fiscal_year", "per_whom": "recipient",
      "statement": "Medicaid reimburses a maximum of 104 quarter-hour units (26 hours) of
                    individual and family therapy services, per recipient, per state fiscal year.",
      "sourced": true, "applies_to_lines": ["bh_intervention", "fact"] },
    { "amount": 4, "limit_type": "units", "unit_definition": "15 minutes (quarter-hour unit)",
      "period": "day", "per_whom": null, "sourced": true }
  ],
  "limits": [ ...4 rows... ] }
```

Correct answer: **104 quarter-hour units (26 hours) per recipient per state
fiscal year, and no more than 4 quarter-hour units (1 hour) in a day**, citing
the 2025 CBH fee schedule. Retrieval alone gets the 104 and misses the daily cap,
or doubles the annual one.

## 6. Before this can be wired — two things, and one is yours

1. **Not deployed.** The router is committed to `mobius-payor` but the service
   has not been redeployed, so the endpoints 404 in dev today. The submodule is
   also sitting on another agent's branch with 69 unpushed commits, so I am not
   deploying it unilaterally. Needs Ananth's or the Payor owner's call.
2. **Base URL.** `https://mobius-payor-ortabkknqa-uc.a.run.app` in dev. Confirm
   chat can reach it — chat already calls RAG and the Fact Store, so I expect
   yes, but I have not verified the network path from chat's service account.

## 7. Scope boundary

This registry is **FL Medicaid behavioural health only**, and the standard only.
It does not hold: payor-specific rates or rules (Fact Store), appeals process
(Appeals), provider enrolment status (Credentialing), or anything outside
Florida. A miss means out of scope as often as it means non-existent, and the
`note` on each response says so.
