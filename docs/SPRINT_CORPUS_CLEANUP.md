# Sprint · Corpus cleanup + UX endpoint attachment

**Between:** Master RAG Coordinator (`mobius-rag`) ↔ Fact Store / Payor Platform (`mobius-payor`)
**Opened:** 2026-08-18

**OBJECTIVE (Ananth, 2026-08-18):** *"the scope for now is fact store and rag to be in unison across
(a) classification (b) dedup and versioning."*

Two seats, three things, one answer each. Success is **not** "both shipped something" — it is that
neither of us can be asked one of these three questions and give a different answer. Everything else
in this file is context for those three.

**Explicitly out of scope for this sprint:** OCR, the 151 blocked jobs, worker capacity, the
chunker defect (§3.1 — logged, not fixed here), UX action wiring. They are real and they are
recorded; they are not what "in unison" means.

**Carries Bug #12** (`BUG_LOG.md`) — filed by Fact Store 2026-08-16, claimed by RAG 2026-08-18.
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

## 1. The three things, and what "in unison" means for each

### (a) CLASSIFICATION
One classification, both seats reading it the same way.

| | Fact Store | RAG |
|---|---|---|
| owns | the verdict | consuming it |
| doing | reclassifying the corpus *(in progress)* | re-running the gate once it lands |
| **unison test** | — | **RAG's lane assignment == Fact Store's `importance`, for every document** |

Open: **`asset_type` must carry revisable vs episodic** (Q4). Without it RAG derives revisability
from a filename regex, and the two seats are guessing separately at the same property. This is the
single biggest blocker to (a) being true.

### (b) DEDUP
One definition of "duplicate", both seats counting the same number.

| | Fact Store | RAG |
|---|---|---|
| owns | which copy is canonical (`authority_level` — authority is a property of origin) | detecting the duplicate set |
| **unison test** | — | **same duplicate count, same canonical pick, on the same corpus** |

RAG currently measures **478 redundant documents** across 236 digest groups. Fact Store has not
verified that number. Until they have, we do not have (b).

Open: §11.1 (Q5) — junk on the `fyi_not_citable` ranking floor vs excluded from the index. Two
different answers to "what happens to a non-canonical copy", and both are currently written down as
policy.

### (c) VERSIONING
One lineage, one verdict store, one set of dates.

| | Fact Store | RAG |
|---|---|---|
| owns | the human verdict + valid-time dates | detection, chains, the gate |
| **unison test** | — | **a version verdict reached in Fact Store is readable in RAG and changes what retrieval serves** |

Today that round trip does not exist in either direction: no hand-off (Q1), no verdict ingest path,
no lineage columns (Q6). RAG can detect and Fact Store can decide, and the two never meet.

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

### 3.0 Why this sprint exists — a real, observed retrieval failure

From Bug #12, filed by Fact Store 2026-08-16 while sourcing AHCA appeal-deadline facts. This is the
user-visible cost of everything else in this file:

> A `corpus_search_agent` call asking for the **current** enrollee plan-appeal deadline returned
> **10 chunks, zero of them from the correct Oct 2025 document.** One came from the **2020-02-01**
> version of the same contract. The right answer — 60-calendar-day deadline, citing 42 CFR
> 438.402/.406/.408 — is in the corpus and fully embedded. 17 near-duplicate historical variants
> outranked it, with no recency signal to break the tie.

Fact Store's workaround was to read the source document directly and record the fact with honest
sourcing rather than cite RAG. That is the correct call and it is not scalable.

Note the two failure modes compound: **(b) dedup** would remove the near-duplicates competing for
the slot, and **(c) versioning** would mark the 2020 edition superseded. Neither alone fixes it,
which is why this sprint pairs them.

### 3.1 DIAGNOSED 2026-08-18 — not adjudications. A CHUNKER defect.

They are not extraction failures and they are not version questions. **Extraction is healthy on
every one of them.**

| document | pages | chunks | chunks/page | avg chunk length |
|---|---|---|---|---|
| healthy 2019–2020 editions | 217–235 | 1,893–2,170 | **8.7** | **252–280 chars** |
| `…Oct_2025.pdf` | 261 | 420 | 1.6 | **1,685** |
| `…October_2025.pdf` | 255 | 300 | 1.2 | **2,326** |
| `abhfl…ltc_provider_manual.pdf` (both) | 173/174 | 193/190 | 1.1 | **2,412–2,468** |

Same generator (`B`), same threshold (`0.6`), same chunker — **9× coarser output**.

Ruled out, by measurement:
- **not thin extraction** — 2,756 chars/page, in line with healthy editions
- **not lost structure** — 54–205 newlines per page; `abhfl` has the *most* structure (205/page) and
  the *coarsest* chunks
- **not a config difference** — generator and threshold are identical

What the data does say: `count(distinct (page_number, paragraph_index)) == chunk count` in every
case, so the chunker emitted **1.2 paragraphs per page** where healthy documents got **8.7**. The
chunker's own paragraph segmentation is producing wildly different granularity on comparable input.
Mechanism unconfirmed — the semantic-merge threshold over-merging uniform contract prose is a
hypothesis, not a finding.

**Three consequences:**
1. **Versioning is unaffected by judgement here.** 0.0000 overlap is an artifact — a 252-char-chunk
   document can never hash-match a 2,400-char-chunk document however similar the text. These pairs
   must not go to a human at all.
2. **Retrieval is silently degraded.** 2,400-character chunks are far too coarse to retrieve
   precisely, and these documents are published and serving right now.
3. **Every stage reports green.** The documents have pages, have chunks, are embedded, are
   published. No count in Corpus Health catches this — which is itself a gap in the page.

**Action:** re-chunk the affected documents and re-measure, before any adjudication. Fact Store
should expect **~6, not 12**, and the 6 will be the AHCA `Attachment II` consecutive editions only.

**Open:** how widespread is this? A corpus-wide chunks-per-page sweep timed out at 90s; it needs the
missing `chunk_embeddings.document_id` index (Q7) or an offline pass. If a meaningful share of the
corpus is chunked this coarsely, it is a bigger retrieval problem than anything else in this sprint.

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
