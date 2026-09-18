# Service Line answer card — render contract

**Owner of this spec:** Service Line Registry (the envelope).
**Owner of the implementation:** Chat Frontend/UX (`mobius-chat/frontend/src/answer-card.ts`).
**Status:** proposed, 2026-09-18. Nothing built. Payloads below are live responses,
not examples I wrote.

## Why this is not just another card

`answer-card.ts` today has **zero occurrences of `caveat`**. Every service-line
answer carries them, and two of the three states below are *only correct* if the
caveat renders. A card that shows `answer` and drops `caveats` will be confidently
wrong in the two cases the registry exists to get right.

That is the same defect this seat has been fixing all week in its own code: a
producer whose consumer was never wired. The caveat `directive` does reach the
model in the tool JSON, so the model is steered. The caveat `text` is written for
the **user** and currently has nowhere to go.

## The envelope (stable across all 7 service-line tools)

```
status     found | unknown | known_absent
answer     one sentence, already written for a human — render verbatim
caveats[]  { code, kind: material|blocking, text, directive }
citations[]{ document, page, sourced }
data       tool-specific payload
query      what was asked (echo)
meta       timings, tool identity
```

`status` is three-valued on purpose and the three are not interchangeable:

- `found` — we hold it.
- `known_absent` — we read the governing document and it does not say. **A finding.**
- `unknown` — we hold nothing. **An admission, not a "no".**

A card that renders `unknown` and `known_absent` the same way destroys the only
distinction that makes the registry trustworthy.

## The render rule, and it is one rule

> **`kind: "blocking"` means the card MUST NOT present a single answer.**
> Render the alternatives, or render the question back. `material` means show the
> caveat alongside the answer.

### Case 1 — `found` + blocking. Real payload, `/codes/H2019`:

```json
{"status":"found",
 "answer":"H2019 is 6 different billable services in this registry, distinguished by modifier: (none), HM, HN, HO, HQ, HR",
 "caveats":[{"code":"modifier_ambiguous","kind":"blocking",
   "text":"This code covers several different billable services, each with its own definition, rate and limits.",
   "directive":"Present the alternatives from the choices, or ask which one is meant. Never answer for one."}],
 "citations":[{"document":"2025 Community Behavoir Health Fee Schedule.pdf","page":2,"sourced":true}]}
```

Render as a **choice**, not a statement. `data.choices` carries `{id, title, subtitle}`
precisely so the UI does not have to reconstruct them — Chat FE asked for that shape.
Answering "H2019 needs prior auth" here is a billing error, not a UX blemish.

### Case 2 — `unknown` + absence. Real payload, `/lines/marchman_act`:

```json
{"status":"unknown",
 "answer":"Marchman Act services is a service line we recognise and it is in scope, but we have not sourced it — we hold no fee schedule, coverage document or codes for it yet.",
 "caveats":[{"code":"absence_is_not_denial","kind":"material",
   "text":"We hold nothing on this. That is a gap in our sources, not a finding that the benefit does not exist or is not covered.",
   "directive":"Say we do not hold it. Do not answer 'no'."}]}
```

Must not render as a negative result or an empty state. This is "we have not looked
it up yet", and a user who reads it as "not covered" has been misinformed by the UI
rather than by the data.

### Case 3 — `found` + partial (shipped 2026-09-18)

```json
{"caveats":[{"code":"partial_requirement","kind":"material",
  "text":"Some requirements here were answered in part. The statement is true as far as it goes, and named slots were never established or were read for and not stated. See unresolved_slots and absent_slots on each row."}]}
```

Each row carries `unresolved_slots[]` and `absent_slots[]`. **Keep them apart** —
never-established is not the same finding as read-and-not-stated. 20 of the first 41
delivered rows are partial; rendering the statement alone reads as complete.

## Minimum viable card

1. `answer` verbatim.
2. Every `caveat.text`, visibly, not behind a disclosure — `material` at minimum as a
   note under the answer; `blocking` replaces the single answer with the choice.
3. `citations` as the existing footnote component (already live).
4. `unresolved_slots` / `absent_slots` where present, named.

## What I will do on request

Add typed interfaces to the envelope the way Appeals did (`AppealsRulesData` etc.) —
`ServiceLineRequirementsData`, `ServiceLineCodeData` — if that is the shape you want
to consume. Say which and I will publish them; I would rather you name the shape than
have me guess it into your module.
