# Payor fact catalog — appeals' seed list

**For:** Payor Platform, as the store's seed. Other consumers will add; this is what appeals needs.
**Status of the live data behind it:** 141 records · 339 filing-critical values · **0 citable · 0.0% sourced.**

---

## 1. Predicates appeals consumes

| Predicate | Value shape | Filing-critical? | Conflict policy |
|---|---|---|---|
| `appeal.deadline_days` | `{days, day_type: calendar\|business, anchor_event, receipt_presumption, basis_citation}` | **yes** | shortest |
| `appeal.resubmit_deadline_days` | same | **yes** | shortest |
| `appeal.submission_channels` | `[{channel: portal\|fax\|mail\|email, value, party}]` | **yes** | union |
| `appeal.required_docs` | `[{doc, required, url, notes, party}]` | **yes** | union |
| `appeal.levels` | `[{level, name, path, deadline_days, submission, notes, party, requires_consent_artifact}]` | **yes** | union |
| `appeal.contacts` | `[{role, phone, email, notes}]` | no | union |
| *(later)* `recoupment.lookback_days` | as deadline | yes | **longest** — inverted |
| *(later)* `appeal.accepted_proof_types` | `[enum]` | no | union |

**`anchor_event` must be able to name a prior level.** Level 2 usually anchors on the level-1
decision date, not the original denial. A flat enum cannot express it.

## 2. Key dimensions appeals must declare

`(payer, product_line, state, network_status, audience, appeal_level, predicate)` + `effective_from`/`effective_to`.

| Dimension | Why | Failure if absent |
|---|---|---|
| `product_line` | Medicaid MCO / Marketplace QHP / Medicare Advantage → 42 CFR 438 / 45 CFR 156 / 42 CFR 422 | one row serves the wrong regime **silently** |
| `state` | multi-state MCO's Medicaid terms come from the state contract | same payer, same product, wrong number |
| `network_status` | contracted vs not → **different appeal chain entirely** (MA non-par: reconsideration → IRE → ALJ + Waiver of Liability; contracted: contract dispute, no IRE) | wrong counterparty, wrong document set, wrong number of levels |
| `audience` | provider vs member | **the 141-row incident** |
| `appeal_level` | level 1 and 2 have different clocks and channels | `deadline_days` singular is wrong |
| `effective_from/to` | resolve **as-of the DENIAL date, never now()** | today's appeal cites today's deadline for a November claim; every completed assessment goes retroactively wrong on contract renewal |
| **ASO / self-funded** | neither product_line nor network_status — inherits the **plan document's** terms, not the payer's | common in commercial CMHC volume |

## 3. Provenance — per FIELD, not per record
`{basis, ref{source, locator, url, observed_on, sample_n, who}, date, note}`

The deadline and the fax number come from different documents and age differently. Record-level
provenance cannot express that.

Basis ladder (weakest → strongest) and exact thresholds: see `04_thresholds_as_coded.json` —
port verbatim, not approximately.

**`stated_verbal` is the one to get right:** sufficient to *investigate* and to *file early*,
**never** sufficient to establish the **outer bound of a deadline**. Acting on a rep's phone call
for a regulated deadline is the original bug with a source attached.

## 4. Read contract appeals will use
```
resolve(payer_key, predicate, audience='provider', party='provider', as_of=<denial_date>)
```
- Undeclared dimension → **serves nothing** (fail-closed, generalised).
- Below `CITABLE` on a filing-critical field → **removed, not labelled**. A draft banner does not
  stop a coordinator acting on a number, and if the number is a deadline the harm is a permanently
  lost claim.
- Conflicts → surfaced, not silently resolved.

## 5. What other consumers will likely need (size the key now, not in a third migration)
*Second-hand — confirm with each owner; recorded so the key isn't sized for appeals alone.*

- **Credentialing** — enrollment/revalidation windows, roster submission channels, delegated-credentialing
  terms, par-effective dates. **Note the overlap:** CARC 185 / B7 denials are a *credentialing action*,
  not an appeal, and Mobius has a credentialing module with **no seam named yet**. Same payer, different
  predicate family, same key.
- **Contracts** — fee schedules, rate effective dates, amendment history. Effective dating is
  load-bearing for them in a way it merely *should* be for us.
- **Eligibility** — verification endpoints, COB/TPL rules, retro-eligibility windows.
- **Common shape across all four:** payer + product_line + state + network_status + effective dating.
  The appeal-specific bits are `appeal_level`, `party`, and `requires_consent_artifact` — generalise
  or keep, your call as owner.

## 6. Scoping note — please confirm with Ananth
My handoff implied "build the whole store." On reflection that risks repeating the mistake this
project just made: **we generated 800 questions and 141 fact records before sourcing a single one.**
A complete fact store for all payers before appeals ships anything is that error with more expensive
work. Suggested bar: **one payer × the predicates the pilot needs, sourced properly, plus the UI that
makes the next payer cheap.**

Also worth pushing back on the phrase "indisputed source of truth": payor facts **conflict by nature**
— regulation 90 / contract 120 / manual 60, all correctly sourced. The store's value is being the
single place where the conflict is **visible and explicitly resolved**, not where it is hidden behind
one number. Authoritative about *what we know and how we know it*.

## 7. Files in this handoff
| File | What |
|---|---|
| `00_FACT_CATALOG.md` | this |
| `01_live_141_rows.json` | the full live dataset — migration source |
| `02_fixture_divergence.json` | **Sunshine: 14 distinct fact signatures** that must resolve to one |
| `03_fixture_wrong_party.json` | the writes that must be **rejected**, and the MA consent-artifact case that must be **accepted** |
| `04_thresholds_as_coded.json` | evidence ladder, CITABLE set, filing-critical list, conflict-policy defaults — as coded |

**Code to port:** `mobius-skills/appeals-agent/api/facts_guard.py` — `screen_playbook_facts`,
`normalize_playbook_parties` (fail-closed: an undeclared enrollee-reading action defaults to
**member**, never provider — blanket-defaulting to provider is exactly how the rung survived the
first fix), `visible_to`, `evidence_for`, `screen_field_evidence`,
`suppress_unsourced_filing_fields`, and the **`DDL` string containing the Postgres trigger**
(`appeals_guard_playbook_party`). The trigger is the piece that must survive the move — verified
live rejecting a write that bypassed the application guard entirely.
