# AHCA fresh scrape → publish — plan for sign-off

**STATUS:** ⛔ **NOT STARTED — awaiting Ananth's sign-off**
**DATE** 2026-08-20 · **COORDINATION** Master RAG
**SEATS:** Crawler · Fact Store · Sourcing · Eval · Retriever · DB · Chat

---

## What changed, and why this document exists

I had been building a **reingest** — re-extracting the 1,160 AHCA documents
already in GCS. Ananth's intent is a **fresh scrape from source**. Those are
different runs with different consequences, and the difference surfaced only when
he asked for base URL, page count and depth — none of which a reingest has.

Flagging rather than proceeding on my reading of it.

---

## The decision that actually needs sign-off

A fresh scrape produces **new** documents. We already hold **1,160** AHCA
documents. Every returned document is therefore one of:

| | relationship | consequence |
|---|---|---|
| (a) | same document, unchanged at source | duplicate — which copy is canonical? |
| (b) | same document, **changed** at source | genuine new version — lineage + retire old |
| (c) | not previously held | straight ingest |

**Both failure directions are expensive:**

- treat everything as **new** → corpus roughly **doubles**, ~1,160 near-identical
  pairs, retrieval quality craters
- treat everything as **duplicate** → genuinely updated fee schedules are
  discarded, and **we serve stale rates**

### And provenance can't settle it

Of the 1,160 AHCA documents we hold, **exactly 2 carry a recorded `source_url`.**

| lane they arrived through | docs |
|---|---|
| medicaid | 497 |
| public-meetings | 246 |
| health-quality-assurance | 164 |
| web-scraper | 139 |
| agency-administration | 65 |
| icmc-program | 33 |

So **new-scrape → existing cannot be matched by URL for 99.8% of the corpus.**
Matching must fall back on content identity — the same normalized-md5 /
shingle-Jaccard instrument the dedup gate already uses.

**Which makes this the largest duplicate-determination run we have ever done:**
~1,160 new documents against a 9,716-document corpus.

**Good news, verified today:** the scrape intake path
(`POST /documents/import-scraped-pages`) records `source_url` **per page**
correctly. Everything arriving through this run is traceable. The gap is
historical only, and this run is what closes it.

---

## Open items — the plan is not signable until these land

| # | from | needed | status |
|---|---|---|---|
| 1 | **Crawler** | base URL(s), depth, page budget, expected yield + wall-clock | asked |
| 2 | **Fact Store** | matching rule, canonical policy, version threshold | asked |
| 3 | **Fact Store** | run-attribution stamp (Ananth asked directly: today the answer is **no**, nothing stamps a Fact Store run id) | asked |
| 4 | **Fact Store** | the 161 retirements — some may return from source as live | open |
| 5 | **Eval** | baseline banked ✅ | **done** |

### My recommendation on the canonical question (Fact Store's to overrule)
When old and new are byte-identical, **the incumbent survives** and we backfill
`source_url` onto it. Existing citations keep resolving, ids stay stable, and we
still gain the provenance. The alternative — fresh copy wins — invalidates every
citation to the old id for no retrieval benefit.

---

## Proposed sequence

1. **Crawler returns parameters** → this plan becomes concrete
2. **Fact Store rules** on matching / canonical / version threshold
3. **Ananth signs off** ⛔
4. **Pilot: one area, bounded** (recommend fee schedules — the codes live there;
   only 1 of 67 policy documents carried any). Verify the matching rule behaves
   on real returns before committing to the full crawl.
5. Gate the pilot **telemetry-only** → Fact Store reviews the (a)/(b)/(c) split
6. Full crawl, staged by area
7. Capture → classify → chunk → embed → publish (all live and tested)
8. Gate corpus-wide, telemetry-only → **Fact Store adjudicates**
9. **Eval AFTER**, same bank and model

**Step 4 is the one I would not skip.** The matching rule is a policy applied to
1,160 documents at once; testing it on a bounded area first is cheap, and getting
it wrong at full scale is not reversible by re-running.

---

## What is already built and proven (unchanged by the scope change)

| capability | state |
|---|---|
| table capture → `document_tables` + breadcrumb | live, 431 tables / 16,365 rows |
| classify on re-extraction | wired today |
| chunk refresh + stale-row prune | fixed today (re-chunking was a silent no-op) |
| publish min-substance guard | live — index junk holding at 0 |
| passenger tables end-to-end | **proven on a real query: 3 attached** |
| reingest as a first-class ingest source | live in corpus health |
| throughput | embedding 1 → 6, API cpu 2 → 4 |

**Passenger attachment is proven but coverage-limited** — all 3 attachments came
via `page_proximity`, none via breadcrumb, so Sourcing's acceptance recall (32%)
is still the ceiling on table quality.

⚠ **Pool latency is a live concern:** 19.7 s → 31.1 s after only 13 documents
were reingested, and Pool was already 86% of query wall-clock. Scaling that to
1,160 needs watching, and may argue for attacking Pool **before** the full run.

---

## Log

### 2026-08-20 · Master RAG · plan opened, nothing started
Scope corrected from reingest to fresh scrape. Crawler asked for parameters,
Fact Store asked for the matching/versioning ruling and run attribution. Eval's
baseline is banked. Corpus deliberately untouched.
