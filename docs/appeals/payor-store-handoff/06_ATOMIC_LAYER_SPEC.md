# Atomic layer — appeals' answer to the three questions

**To:** Payor Platform / Fact Store · **From:** Appeals · **Date:** 2026-08-15
**Status:** answers Q1/Q2/Q3 from their 2026-08-15 message. Normative alongside
`00_FACT_CATALOG.md` (predicates + key) and `05_INTEGRATION_CONTRACT.md` (the seam).

---

## 0. First, an apology and a correction

You asked for a shape I had already written down. That is my fault, not yours:
`docs/appeals/payor-store-handoff/` was **untracked** — it lived only in my worktree and
never reached `main`. You have been designing blind against a contract you could not read.
It is committed now. Read `00_FACT_CATALOG.md` and `05_INTEGRATION_CONTRACT.md` first;
this file is the delta that answers your three questions directly.

Also: **your live Sunshine result is the single most valuable thing that has happened to this
project.** Not the design — the *90 calendar days with a locator*. Our corpus is 141 records /
339 filing-critical values / **0 citable**. You just produced value #1. And the way you handled
the fax is exactly right: **not found, reported as a real gap, not masked**. That is the
contract's `value: null` + `reason: "unsourced"` behaviour, arrived at independently. Keep it.

---

## 1. Q1 — the raw facts appeals needs

Full table in `00_FACT_CATALOG.md §1`. Consolidated, with your five mapped in:

| Predicate | Yours | Filing-critical | Conflict policy |
|---|---|---|---|
| `appeal.deadline_days` | `appeal_filing_deadline_days` | **yes** | shortest |
| `appeal.resubmit_deadline_days` | — | **yes** | shortest |
| `appeal.submission_channels` | `appeal_mailing_address` + `appeal_fax` | **yes** | union |
| `appeal.required_docs` | — | **yes** | union |
| `appeal.levels` | — | **yes** | union |
| `appeal.contacts` | — | no | union |
| `appeal.payor_ack_sla_days` | `appeal_ack_sla_days` | no | **longest** |
| `appeal.payor_determination_sla_days` | `appeal_determination_sla_days` | no | **longest** |
| *(later)* `recoupment.lookback_days` | — | yes | **longest** |

**Three notes on the deltas:**

**(a) Your two SLA facts are a real addition — I'm adopting them.** I had not modelled them and
should have. They are a different *kind* of clock: mine are **provider obligations** (miss it,
lose the claim), yours are **payor obligations** (miss it, the provider has an escalation
argument). That's why their conflict policy is **inverted** — for a provider deadline the
shortest sourced value is the safe one; for a payor SLA the *longest* is, because asserting the
payor is late is the risky direction. They are not filing-critical (a missing SLA doesn't lose a
claim), but they drive the card's follow-up date and they'd be the basis of a "you are out of
compliance" escalation. Please keep them.

**(b) Don't split channels into scalar keys.** `appeal_mailing_address` and `appeal_fax` as
separate top-level facts breaks two things: the **union** conflict policy across channels, and
the fact that each channel carries its own `party` (the member fax is not the provider fax).
One predicate returning a typed list:
```jsonc
"appeal.submission_channels": [
  {"channel":"mail","value":{"attn":"Adjustments/Reconsiderations/Disputes",
                             "line1":"PO Box 3070","city":"Farmington","state":"MO","zip":"63640-3823"},
   "party":"provider"},
  {"channel":"fax","value":null,"reason":"unsourced","party":"provider"}
]
```
Note the fax row **survives as a row** with a reason, rather than vanishing. The card must be
able to say "fax: not sourced" rather than silently omitting the concept.

**(c) `appeal.levels` is the one you're missing, and it's the one that bit us.** The chain of
rungs — who each is with, what the next one is, and **whose action each is**. Details in §3.

---

## 2. Q2 — shape. Not flat key-value, and here's specifically why

Flat KV fails on three counts, each of which we've already been burned by.

**(a) A deadline is never a bare integer.**
```jsonc
{"days": 90, "day_type": "calendar", "anchor_event": "claim_denial_notice",
 "receipt_presumption": null, "basis_citation": "CMS-PRO-PE-Manual.pdf p.50"}
```
`90` alone is unusable — 90 from *what*, counted *how*. And this matters for your own result
right now: you wrote *"90 calendar days from the original UM/claim denial."* **UM appeal and
claim dispute are two different clocks with two different anchors**, and a manual that covers
both will often state them separately. Worth re-reading p.50/51/53 with that split in mind —
if they genuinely share one clock, great, record it once; if not, that's `appeal.deadline_days`
vs `appeal.resubmit_deadline_days` and collapsing them serves the wrong number.

**`anchor_event` must be able to name a prior level.** Level 2 anchors on the level-1 *decision*
date, not the original denial. A flat enum cannot express that.

**(b) Provenance per FIELD, not per record.** The deadline comes from the provider manual; the
fax number comes from a web page; they age at completely different rates. One timestamp on a
record that is half fresh and half rotten is worse than none. Every value carries:
```jsonc
{"basis": "stated_policy", "citable": true,
 "ref": {"source":"CMS-PRO-PE-Manual.pdf","locator":"p.50","url":"…","observed_on":"2026-08-15"},
 "effective_from":"…","effective_to":null}
```
Ladder (weakest→strongest), port verbatim from `04_thresholds_as_coded.json`:
`unverified < inferred < network_experience < stated_verbal < observed_claims < stated_policy < regulatory`
**CITABLE = (`stated_policy`, `regulatory`)** — only these may be quoted *inside* an appeal letter.
Your Sunshine facts are `stated_policy`. **Citable. First ones we've ever had.**

**`stated_verbal` is the one to get exactly right:** a rep's phone call is enough to *investigate*
and to *file early*; **never** enough to establish the **outer bound** of a deadline.

**(c) The key is not `payer`. It's a tuple — and your own result proves it.**
```
(payer, product_line, state, network_status, audience, appeal_level, predicate) + effective_from/to
```
You sourced from **CMS-PRO-PE-Manual** — that's Sunshine's **Medicare** product. Sunshine also
sells a Florida **Medicaid MCO** plan governed by 42 CFR 438 and the state contract, with a
different chain and a different number. Filed under `payer=sunshine_health` alone, that 90 would
serve Medicaid denials **silently, with a real citation attached**. Same failure shape as the
audience bug, one dimension over.

`network_status` matters for the same reason and is still absent from your `(state, payer,
product)` health-plan unit: contracted vs non-contracted Medicare Advantage isn't a different
number, it's a **different chain entirely** (non-par: reconsideration → IRE → ALJ, plus a Waiver
of Liability; contracted: contract dispute, no IRE).

**And `as_of` resolves to the DENIAL date, never `now()`** — otherwise today's appeal cites
today's deadline for a November claim, and every completed assessment goes retroactively wrong
at contract renewal.

---

## 3. Q3 — provider or member? **Model both. Serve provider. Never merge.**

Store both — member appeals and grievances are real, differently-governed, and Mobius will want
them. But they are **separate facts on the `audience` dimension**, never reconciled into one row,
and appeals declares `audience='provider'` on every call today.

This is not hypothetical caution. It is our worst production incident:

> An **unsourced member fair-hearing deadline** reached **all 141 rows** and rendered on live
> customer cards as a **provider** deadline. My first fix stripped the number but left the
> **rung** — the wrong-counterparty *action* survived the fix that was supposed to remove it.

The structural lesson, and the thing I'd most like your schema to encode:

> **`audience` scopes VALUES. `party` scopes ACTIONS.**

A deadline has an audience. A *rung in the chain* has a party — because "request a State Fair
Hearing" is a thing the **enrollee** does, and it stays wrong even after you delete the number
attached to it. Conflating the two is precisely how it survived.

Two enforcement asks:
1. **Fail closed on undeclared.** An action with no declared party that reads as an enrollee
   remedy defaults to **`member`**, never `provider`. Blanket-defaulting to provider is how the
   rung survived. (`facts_guard.py :: normalize_playbook_parties`.)
2. **Port the Postgres trigger, not just the app guard.** `facts_guard.py`'s `DDL` string
   contains `appeals_guard_playbook_party` — verified live rejecting a write that bypassed the
   application guard entirely. Generation jobs write straight to the table; an app-layer check
   is not a guarantee. This is the piece that must survive the move to your table, and it's
   your own §9.6 DoD ("audience wrong is structurally blocked") made executable.

**One legitimate exception:** a member-party action renders to a provider **if and only if** it
carries `requires_consent_artifact` — the Medicare Advantage Waiver of Liability case. It renders
**with the artifact attached and never without it**.

---

## 4. Scope — please don't build the whole store

We generated 800 questions and 141 fact records before sourcing a single one. Building a complete
store for all payers before anything ships is that same mistake at greater expense. The bar I'd
propose is the one you just cleared by accident:

> **One payer × the predicates the pilot needs, sourced properly, plus the UI that makes the
> next payer cheap.**

Sunshine × the appeal predicates. You are most of the way there tonight.

---

## 5. Cutover — mechanical, and the consumer side is already built

`api/fact_store_adapter.py` implements §1/§2 of the integration contract: two backends behind one
interface, `resolve_many` batching (~6 predicates per card render), and **fail-closed on resolver
outage** — `resolver_unavailable`, deliberately a *distinct* reason code from `unsourced`, so a
transient blip doesn't masquerade as a sourcing gap and corrupt coverage telemetry.

Cutover is `APPEALS_FACT_STORE_URL=<your resolver>`. Nothing else in appeals changes.

**Acceptance, verbatim from `05_INTEGRATION_CONTRACT.md §5`:**
1. Resolver answers the §1 call with the §2 shape for one payer × the appeal predicates.
2. `03_fixture_wrong_party.json` passes **at your table**: (a) and (b) rejected, (c) the MA
   consent-artifact case accepted, (d) unsourced-duration rejected.
3. `02_fixture_divergence.json`: Sunshine's **14 fact signatures resolve to one**.
4. A fact sourced through your UI comes back `citable: true` with its locator, and appeals renders it.
5. A fact with no source comes back `value: null` and appeals renders an honest gap. **Your fax
   is fixture #5 already.**
6. **Appeals' evidence audit reports `percent_citable > 0` for the first time.** Today: 0.0%.
   Your 90-day value is the one that flips it.
