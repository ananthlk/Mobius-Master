# Lexicon P-Tag Gaps — Enrichment Backlog (found during shape gate build)

**Status:** FILED to Curation/Lexicon 2026-07-22 (Ananth approved release) — catalogued as the "D-TAG GAP QUEUE" in Curation's [[project_tag_selectivity_loop]] backlog (loop part 2, mine-failed-queries). Awaiting Curation scoping/prioritization; not blocking.
**Revised 2026-07-22:** after adding the `process_intent` structural heuristic (see gate.py), most of the originally-logged gaps turned out to be either already-correct or resolved without any lexicon change. This doc reflects the corrected, final picture.
**Purpose:** isolate what the shape/gate **refactor** got us vs what a **lexicon data-enrichment** pass would additionally get us. Measure both separately against the cmhc 22-query baseline so the delta is attributable.

**Context:** while building the Step 1 SHAPE gate (`app/services/retriever/shape/gate.py`), contour classification is grounded in J/P/D lexicon expansion + a document_tags corpus probe. Contour rules require D+J; P is enrichment EXCEPT when D matched only the bare umbrella/`.general` bucket for a domain that has specific siblings (e.g. "eligibility" has ~90 leaves) — there P disambiguates which facet is meant.

---

## Correction: most originally-logged "gaps" were not gaps

Initial pass (before the `process_intent` fix) flagged cmhc005/012/022 (billing) and cmhc004/013 (coverage) as needing new `p:billing`/`p:coverage_determination` tags. **This was wrong** — all five queries were already `contour=exact` in the locked logic, because their matched D-codes span multiple non-general roots or hit specific leaves (e.g. `health_care_services.dental`, `place_of_service.telehealth`), never falling into the general-only-D branch where P matters at all. No lexicon change needed for these.

## Remaining real finding: "how do I ..." resolves without a lexicon change at all

Added a **structural process-intent detector** (`_PROCESS_INTENT_RE` in gate.py — regex on "how do I / how to / what's the process for" phrasing) that satisfies the P-disambiguation requirement independent of lexicon phrase-matching. This fully resolves the "check" case:

| Query | Before (lexicon-only) | After (+ process_intent) |
|---|---|---|
| "Eligibility for Medicaid" (bare) | underspecified | underspecified (correct — no signal of any kind) |
| "How do I **check** eligibility for Medicaid" | underspecified (only "verify" was aliased, not "check") | **exact** — resolved structurally, zero lexicon change |
| "How do I **verify** eligibility for Medicaid" | exact (lexicon alias hit) | exact (unchanged) |
| "What are the eligibility **criteria** for Medicaid" | underspecified | underspecified (**correctly** — this is a genuinely different, still-ambiguous ask: which facet's rules? income/categorical/age-band? not a phrasing gap) |

**Net effect:** the generic "how do I X" structural signal generalizes across every unmatched action verb (check/confirm/validate/look up/...) without enumerating each one as a lexicon alias. This is a shape-side win, not a lexicon-side one — **no P-tag enhancement is actually needed for the verb-synonym problem.**

## D-tag gaps found (still real, still separate from P)

| Query | Missing domain | Notes |
|---|---|---|
| cmhc016 "How do I get **credentialed** with Sunshine Health?" | no `d:credentialing*` tag exists | entire credentialing domain appears unmapped in the D lexicon — `process_intent` fires here too but can't help, since D is empty, not general-only; a real domain tag is needed |
| cmhc021 "What documentation is required to **enroll** a new pediatric patient..." | no `d:enrollment*`/pediatric-intake tag matched | `d:eligibility.enrollment*` exists but didn't fire — possibly a phrase-matching gap, not a missing tag; worth Curation checking why "enroll a new pediatric patient" didn't hit `eligibility.enrollment` |

These are the **only two remaining real backlog items** — both D-tag (domain), not P-tag (process) issues.

---

## Why this matters for the build (meet-old vs exceed measurement)

The gate's contour logic (D+J required, P as enrichment/disambiguator via lexicon alias OR structural process-intent) is **locked and correct** as of 2026-07-22 — verified against all 22 cmhc queries + synthetic contrasts, zero regressions, 20/22 exact. The 2 remaining `underspecified` results (cmhc016, cmhc021) are honestly attributable to **D-tag lexicon coverage**, not shape design, and not P at all.

**Plan:** run the full build (shape → pool → router → fillers → observe → synthesis → contract → timing) against the CURRENT lexicon first, measure against cmhc baseline. That's the "refactor" number. Then fire this backlog to Curation/lexicon owner as a **separate enrichment pass** (add `d:credentialing*`, investigate the enrollment phrase-match miss) and re-measure. The delta is the "lexicon enrichment" number — cleanly separated from "did the refactor itself help."

**Action when ready to fire:** file to Curation (lexicon-build owner) with this log as the spec — now scoped to just the 2 D-tag items, since the process-intent fix eliminated the P-tag backlog entirely. Do NOT fire yet — holding until after the shape/pool/router build completes its own baseline measurement.
