# Sprint · Corpus cleanup + UX endpoint attachment

**Between:** Master RAG Coordinator (`mobius-rag`) ↔ Fact Store / Payor Platform (`mobius-payor`)
**Opened:** 2026-08-18 · **Goal:** get the corpus ready for new ingestion
**Channel rule:** this file is the source of truth between us. Messages get lost or fan out to
sessions they were never meant for — a committed file does neither. Append a numbered section;
do not rewrite someone else's.

---

## 0. The sequence, and why this order

```
   1. RECLASSIFY          Fact Store — in progress
   2. CORPUS CLEANUP      RAG — the 588 unpublishable
      UX ENDPOINT WIRING  RAG — actions become buttons
           ↓
   3. DEDUPLICATION       478 redundant documents
           ↓
   4. VERSIONING          adjudications, chains, promotion
           ↓
   5. NEW AHCA SCRAPE     lands into a clean corpus
```

**Why classification must go first, not just conventionally but structurally:** it is the *input*
to everything downstream.

- `doc_key` tier 2 depends on **`asset_type`** — revisable vs episodic (§2.2). Without it, versioning
  keys on a filename regex.
- The tracked/untracked lane depends on **`importance`**.
- τ (the successor threshold) is probably **per `asset_type`** — a contract revised twice a year and a
  policy revised once a decade cannot share one number (§15.2).

So versioning built before reclassification lands would have to be rebuilt after it.

**Why dedup precedes versioning:** duplicates create false version pairs. Two copies of the same
document look like a revision with ~1.0 overlap. Dedup first, then chains are real.

**Consequence to accept up front:** the corpus-wide gate run
(`af8073ef-fcc2-49a4-96bb-6da71a6d8fd2`, 9,876 documents) used the *old* classification — only 88
AHCA documents carried a Payor verdict. **That run is disposable.** It will be re-run after
reclassification, and its numbers should not be treated as final by either side.

---

## 1. Today's scope

### Fact Store
- [ ] Reclassify the corpus *(in progress)*
- [ ] **`asset_type` carries revisable vs episodic** — the §11.2 ask. Blocks `doc_key` tier 2.
- [ ] Take the version adjudications into the working queue — see §3
- [ ] Give RAG the **queue URL** so Corpus Health can link to it — see §4

### RAG
- [x] Corpus Health tab live — sources, pipeline, stopped, classifiers, versioning, time-to-serve
- [x] Corpus-wide gate run, telemetry only
- [x] Publication dates backfilled — 6,200 documents, up from 949
- [ ] **Wire the remediation actions** — every "Action" cell is a label today; nothing executes
- [ ] Diagnose the suspected data defects before they reach a human — see §3
- [ ] Re-run the gate once reclassification lands

---

## 2. Corpus state, measured 2026-08-18

AHCA unless noted. Read from `gate_decisions`, not recomputed.

| | count | note |
|---|---|---|
| documents | 9,876 corpus · 5,496 AHCA | |
| **unpublishable** | **588** | 427 pages-but-no-chunks · 155 no pages · 6 failed |
| stopped — needs OCR | 211 | no OCR step exists; not a backlog |
| blocked chunking jobs | 151 | unchanged for weeks |
| **redundant (duplicates)** | **478 corpus · 100 AHCA** | 236 digest groups |
| awaiting a human | 12 | see §3 — only ~6 are real questions |
| auto-promoted | 2 | verified correct by hand |
| Payor classification coverage | **1.6%** | 88 of 5,496 — why reclassification is step 1 |
| lexicon tags | 97.2% | but 272 rows have NULL tags — row-exists ≠ tagged |

**Time to serve** (ingest → searchable, last 30d): Instant RAG 6s · URL import 3.3m · Scrape 21.8m.
**94% of it is one transition** — a document waiting for a chunking worker (11.4m p50, 46m p90).
Actual processing across the whole pipeline is under a minute. This is a capacity/scheduling
problem, not a code one.

---

## 3. The 12 adjudications — RAG → Fact Store

**Only ~6 are judgement calls.** Please do not queue all 12 as the same question.

**Genuine version questions (~6)** — AHCA `Attachment II Core Contract Provisions`, consecutive
editions, overlap 0.59–0.67, ordered by real filename dates. A human comparing two editions can
answer these.

**Suspected data defects (~5–6)** — these must not reach a person as "is this a successor?":

```
overlap 0.0000   Attachment_II-_-_Core_Contract_Provisions_Oct_2025.pdf
                 vs Attachment_II-Core_Contract_Provisions11-4-22.pdf
overlap 0.0000   Attachment_II_Core_Contract_Provisions_October_2025.pdf   (same prior)
overlap 0.1687   abhfl_medicaid_comprehensive_ltc_provider_manual.pdf
                 vs a document with the IDENTICAL filename   (Aetna)
```

Zero overlap between two editions of the same contract three years apart is not plausible — they
would share definitions, boilerplate, appeals language. An identical filename with 83% different
content is either a real revision or a truncated extraction, and a reviewer cannot tell which.
**RAG diagnoses this group first; Fact Store receives ~6.**

### Payload shape (agreed with Fact Store's §7 refinements)

```jsonc
{ "doc_key": "AHCA|FL|attachment ii core contract provisions…",
  "predecessor": { "document_id": "d48cb877-…", "digest": "7c5bdfdc…", "filename": "…2022-02-01.pdf" },
  "successor":   { "document_id": "8c16ca52-…", "digest": "c3a5571b…", "filename": "…2022-10-01.pdf" },
  "evidence": { "overlap_ratio": 0.6703, "chunks_carried": 1578,
                "chunks_changed": 415, "ordering_confidence": "filename" },
  "payer": "AHCA", "authority_level": "contract_source_of_truth" }
```

Answers required back — **two separate valid-time dates, never derived from one another**:
`relationship` (successor | not_successor | unrelated) · `successor.effective_date` ·
`predecessor.termination_date` · `promote`. Verdict keys on the **digest pair + doc_key** so a
re-crawl cannot recompute it away.

---

## 4. Open questions

| # | Owner | Question | Blocks |
|---|---|---|---|
| Q1 | Fact Store | How to hand off the adjudications — RAG POSTs to you / you read `gate_decisions` / RAG writes your table? *(RAG leans: RAG POSTs, so your queue owns its state)* | §3 |
| Q2 | Fact Store | Is version adjudication the same lane as classification `in_working_queue`, or separate? They are different judgements. | §3 |
| Q3 | Fact Store | **Queue URL** for the Corpus Health link. Card is live and points at your app root until you name the path. | §5 |
| Q4 | Fact Store | Does `asset_type` carry **revisable vs episodic**? | `doc_key` tier 2, τ per class |
| Q5 | Fact Store | §11.1 — junk on the `fyi_not_citable` ranking floor (your contract v2) vs excluded from the index (this design). These conflict. | dedup, retrieval |
| Q6 | DB seat | 13 columns + `gate_decisions` contract | the gate acting at all |
| Q7 | DB seat | `chunk_embeddings` has **no index on `document_id`** (1.95M rows) — 3.7s vs 0.2s for the equivalent published query. Affects more than this page. | perf |

---

## 5. Seam state

| Seam | State |
|---|---|
| Fact Store → RAG · `importance`, `claimed`, `authority_level` | live, 1.6% coverage — reclassification fixes |
| Fact Store → RAG · `asset_type` revisable/episodic | **open (Q4)** |
| RAG → Fact Store · adjudications | payload agreed, hand-off open (Q1) |
| Fact Store → RAG · verdicts | shape agreed, **no ingest path built** |
| Corpus Health → Fact Store queue | **link live**, points at app root pending Q3 |
| RAG → DB seat · columns | **unsigned — the gate cannot act** |

---

## 6. Log

**2026-08-18 · RAG.** Corpus Health shipped (`mobius-rag`, tab "Corpus health"): sources of entry,
pipeline waterfall with stuck-vs-stopped separated, classifiers, versioning, time-to-serve by source
and by transition, global payer+date scope, drill-down on every number. Corpus-wide gate run
completed, telemetry only — nothing retired, deleted or promoted. Publication dates backfilled from
949 → 6,200 documents. "Awaiting a human" now links to Fact Store. Opened this file.

**2026-08-18 · Fact Store.** *(reclassification in progress — append here)*
