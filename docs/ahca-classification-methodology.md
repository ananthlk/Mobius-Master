# AHCA Document Classification Methodology

**From:** Sourcing / Crawler Agent
**To:** Fact Store
**Status:** Proposed. Derived from a verified crawl of 1,181 AHCA documents, 2026-08-17.
**Companion:** [`ahca-source-navigation-and-bh-corpus.md`](./ahca-source-navigation-and-bh-corpus.md) — topology, traps, BH corpus.

---

## The core claim

**AHCA's site structure is a deterministic classifier.** Every document's `doc_type`, `authority_level`, `program`, and grain is derivable from *which page it was linked from* and *what the anchor text says* — before any content is read.

This matters because the corpus currently classifies badly:

| Field | NULL | Populated |
|---|---|---|
| `doc_type` | **6,305 (65%)** | 3,334 |
| `authority_level` | **6,275 (65%)** | 3,364 |

Two-thirds of 9,639 documents are unclassified. For AHCA documents specifically, that is avoidable — the provenance carries the answer. Classify at ingest from `source_page_url`, and fall back to LLM inference only for what the rules do not cover.

---

## 1. Rule 1 — `source_page_url` → `doc_type` + `authority_level`

Deterministic. No inference. Apply at ingest.

| Source page | `doc_type` | `authority_level` | Grain |
|---|---|---|---|
| `rule-59g-4.002-…-billing-codes` | `fee_schedule` | `payer_policy` | code × modifier |
| `historical-medicaid-reimbursement-schedules` | `fee_schedule` | `payer_policy` | code × modifier (archive) |
| `cost-reimbursement/*` (17 pages) | `rate_schedule` *(new)* | `payer_policy` | facility × period |
| `medicaid-actuarial-services` | `capitation_rate` *(new)* | `payer_policy` | plan × rate cell |
| `adopted-rules*` | `clinical_policy` | `contract_source_of_truth` | rule |
| `rules-in-process` | `clinical_policy` | `fyi_not_citable` | rule (proposed) |

**Two new `doc_type` values are requested:** `rate_schedule` and `capitation_rate`. Collapsing all three rate classes into the existing `fee_schedule` would erase the grain distinction and cause double-counting — the natural keys are genuinely different (§3 of the companion doc). Fact Store owns whether to add them; if the answer is no, the fallback is `fee_schedule` + a mandatory `rate_grain` discriminator, but that pushes the problem into every consumer.

**`rules-in-process` must be `fyi_not_citable`.** These are *proposed* rules. Serving one as current policy is a correctness bug, not a ranking bug. This is the single highest-risk classification in the set — 9 documents that look authoritative and are not yet law.

---

## 2. Rule 2 — adopted rules are state-level floors, not payer facts

Every `adopted-rules*` document is a **59G rule**: Florida Administrative Code, binding on all FL Medicaid MCOs.

```
payer_key      = 'AHCA|FL|Medicaid'      -- the regulator, not a plan
state          = 'FL'
program        = 'Medicaid'
authority_level= 'contract_source_of_truth'
```

This connects directly to `migrations/015_regulatory_authority.sql`, whose header already states the design: *"AHCA needs to be sourced only once per predicate, not once per MCO."* Currently only five appeal predicates carry `regulatory_authority='AHCA'`.

**The ask:** extend that marking to the coverage predicates these rules actually rule on — service limits, PA requirements, provider qualification, place-of-service, unit caps. 93 of 202 policy documents carry a `59G-x.xxx` rule number in filename or anchor text; that rule number is the join key.

**Semantics of the inheritance — get the direction right.** From AHCA's own published disclaimer:

> Health plans … have the flexibility to cover services above and beyond the Agency's fee schedules and coverage policies, as well as reimburse providers at mutually agreed upon rates. … Health plans cannot be more restrictive in coverage than the Agency.

So:
- **Coverage predicates → AHCA is a FLOOR.** Plan may be more generous; may not be more restrictive. Inheritance is valid when the plan is silent.
- **Rate predicates → AHCA is NOT binding.** Plans negotiate. An AHCA rate must never be served as a plan's rate. It is a benchmark, not a fact about the plan.

Modeling both as equality would be wrong in both directions. If a single `regulatory_authority` flag cannot express floor-vs-benchmark, that is an argument for a second column, and it should be decided before BH predicates are marked.

---

## 3. Rule 3 — `program` normalization (existing defect)

Live values:

```
Medicaid                       6,263
BehavioralHealth                 498
Medicaid Behavioral Health         6   <-- inconsistent
Medicare                          70
```

Three spellings of two concepts. `program` is doing double duty as line-of-business *and* service category, and the 6-row variant is a silent partition — any filter on `program='BehavioralHealth'` misses those rows.

**Recommendation:** `program` holds line-of-business only (`Medicaid` / `Medicare`). Service category moves to `d_tags` (`behavioral_health`, `dental`, `pharmacy`, …). This is a Fact Store / DB call, not mine, but the AHCA ingest will multiply the inconsistency if it lands first — the BH cut alone adds 77 documents that all need this decision made.

---

## 4. Rule 4 — BH tagging is two-tier

From the companion doc's §4. The distinction is not cosmetic.

**Tier 1 — `bh_direct` (65 docs).** Titles carry BH signal. 13 named 59G rules (`4.027` Overlay, `4.028` Assessment, `4.029` Medication Mgmt, `4.031` Community Support, `4.052` Therapy, `4.120` SIPP, `4.127` FACT, `4.295` Therapeutic Group Care, `4.300` State Mental Health, `4.310` TCM, `4.370` BH Intervention, `8.700` Child Health TCM, `13.070` DD iBudget), nine BH fee schedules, ~20 MHTCM certification and authorization forms.

Tag: `d_tags += ['behavioral_health']`

**Tier 2 — `bh_crosscut` (12 docs).** `59G-1.001` Purpose, `1.010` Definitions, `1.050` General Policy, `1.058` Eligibility, `1.100` Fair Hearings, plus PA, TPL, Medicaid Forms, County of Residence, Professional Medical Standard.

These never mention behavioral health **and they decide BH cases.** A retrieval gate that filters BH questions to `d_tags @> ['behavioral_health']` will exclude the eligibility and appeal rules and answer those questions wrong.

Tag: `d_tags += ['general_policy']`, and the gate must admit `general_policy` on any BH query. **This is a gate-construction requirement, not just a tagging one** — flagging it explicitly because it is the failure mode most likely to ship silently.

---

## 5. Rule 5 — dates: ingest NULL, never guess

`migrations/020` made `documents.effective_date` a DATE with a fail-closed gate, after a real defect where a `SELECT`-only gate silently NULLed malformed rows.

The manifest's `effective` column is **filename-derived and mixed-precision** — `2025`, `July 1, 2026`, `10/01/2025`. 261 of 979 rate files and 167 of 202 policy files have none at all.

**Do not write it to `effective_date`.** `2025` becomes `2025-01-01`, which is a false claim about when a rate took effect — and rate effective dates are exactly what document-currency retrieval keys on (Bug #12).

Sequence: ingest with `effective_date` NULL → extract from document body → write ISO. Treat manifest `effective` as a triage hint in `source_metadata` only.

The 19 historical ZIPs (2006–2024) are a free validation set: the archive year is unambiguous, so per-file dates extracted from inside can be checked against it.

---

## 6. Rule 6 — content signals are binding

`migrations/020` added `documents.content_signals` for exactly this. Every AHCA document must be stamped:

```
ai-train=no use=reference search=yes
```

`ai-train=no` is a binding reservation of rights, asserted under EU DSM Article 4 in AHCA's robots.txt. It must propagate to any training-set extraction. `use=reference` means served answers cite back — which `source_ref` already supports.

**Open item:** the column exists; whether anything reads it before building a training set has not been verified. Worth confirming, since the enforcement is the point.

---

## 7. Identity — filenames are not identity

All AHCA files resolve to a flat CDN namespace:

```
https://ahca.myflorida.com/content/download/<numeric_id>/file/<filename>
```

**Use `<numeric_id>` as the durable external document ID.** Filenames change and are misspelled in the live source — uncorrected, today:

| On the site | Means |
|---|---|
| `2025 CHB Fee Schedule.xlsx` | **CBH** — Community Behavioral Health |
| `2025 Community Behavoir Health Fee Schedule.pdf` | Behavio**r**al |
| `2026 Hearing Services Fee Schdule 4.6.26.xlsx` | Sche**d**ule |
| `2025 Licensed Midwife Fee Schedulen.xlsx` | Schedule |

Note the first two are the *same schedule* in two vintages under two different misspellings. Dedup on filename similarity will not catch that; dedup on CDN ID will.

`documents` has **no `source_url` column** — the manifest URL should land in `source_metadata.source_url`, which is already the convention where present.

---

## 8. Suggested ingest order

1. **`rules-in-process` (9 docs)** — smallest set, highest correctness risk. Proves the `fyi_not_citable` path before anything citable lands.
2. **BH Tier 1 + Tier 2 (77 docs)** — the target corpus; validates the two-tier gate.
3. **Fee schedules, 2026 vintage (~66)** — current rates.
4. **Remaining policy (~125).**
5. **Cost reimbursement (813)** — largest, different grain, lowest BH relevance. Do last, after `rate_schedule` exists.
6. **Historical ZIPs (19)** — expand first; each is a full year of files.

---

## 9. Decisions needed from Fact Store

1. Add `doc_type` values `rate_schedule` and `capitation_rate`? (§1) — blocks cost-reimbursement and actuarial ingest.
2. Can `regulatory_authority` express **floor** vs **benchmark**, or is a second column needed? (§2) — blocks BH predicate marking.
3. `program` normalization: line-of-business only, service category to `d_tags`? (§3) — blocks BH ingest cleanly.
4. Who owns the retrieval-gate change so `general_policy` is admitted on BH queries? (§4)
5. Is `content_signals` read anywhere before training-set construction? (§6)

Items 1–3 gate ingest. 4 gates correctness. 5 is a compliance check.
