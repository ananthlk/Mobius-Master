# AHCA full rerun — scrape → publish, in one day

**OWNER (coordination):** Master RAG · **DATE** 2026-08-20 · **DIRECTIVE:** Ananth
**SEATS:** Fact Store · Sourcing · Retriever · Eval · DB · Chat · Master RAG

> Today's objective: **a whole AHCA rerun, scrape through publish**, with every
> change — tables, classify, dedup, retriever — reflected correctly in **both**
> interfaces' traces, and a **portfolio-model eval before and after**.

**Scope:** 1,160 AHCA documents (of 9,716 active).

---

## The rule that shapes the whole run

**Eval BEFORE must be captured before the first document is re-extracted.**
Re-extraction rewrites `document_pages`, which changes chunk text, embeddings,
and the md5 that duplicate determination rests on. Once the rerun starts there is
no way back to a clean baseline — the corpus it measured no longer exists. This
is the one step that cannot be recovered by re-running it later.

**Everything else can be retried. This cannot.** So it gates the start.

---

## Pipeline, and who owns each stage

| # | stage | owner | state |
|---|-------|-------|-------|
| 0 | **Eval BEFORE** — portfolio model baseline | **Eval** | ⛔ **blocks the start** |
| 1 | scrape / source | Sourcing | existing docs; re-fetch only where stale |
| 2 | extract + **table capture** | Master RAG (wiring) · Sourcing (detector) | live, `TABLE_CAPTURE=on` |
| 3 | **classify** | Payor classifier | ✅ wired into re-extraction today |
| 4 | chunk → embed → publish | Master RAG | ✅ auto-publish on embed |
| 5 | **dedup / versioning + backprop** | Master RAG · **Fact Store** adjudicates | telemetry-only, then a decision |
| 6 | **retriever** — passenger tables | Retriever | live behind flags |
| 7 | **traces** — RAG + Chat | Master RAG · Chat | ⚠ see gaps |
| 8 | **Eval AFTER** — same bank, same model | **Eval** | after publish completes |

---

## Throughput — fixed today, and what it cost to find

The embedding worker was **min=max=1**: twelve chunking pollers feeding a single
embedder that also does auto-publish. That one instance was what everything
queued behind. **Raised to 6.**

The API stays `min=max=1` — a correctness constraint, not tuning: in-process eval
and orchestrator state live on one instance. But `restart_extraction` spawns its
work **in that same process**, so a batch starves query serving. Measured during
a 30-document reingest: a query that normally answers in 22 s returned
`status="timeout"` at 46 s with **zero chunks**. CPU raised 2 → 4 as mitigation.

> **Consequence for today, and everyone should plan around it:** while the rerun
> is executing, **retrieval quality measurements are not trustworthy**. Eval
> BEFORE must finish first; Eval AFTER must wait for the run to drain.

**The real fix, not done today:** extraction belongs in its own self-polling
worker like chunking and embedding. That also removes the reason `min=max=1`
exists. Recorded in the deploy script.

---

## What I need — Master RAG

| from | what | why it blocks |
|---|---|---|
| **Eval** | portfolio-model baseline **now** | the corpus it measures stops existing at first extraction |
| **Eval** | the AFTER run, same bank/model | a before with no after proves nothing |
| **Fact Store** | adjudication on gate diff | the rerun invalidates md5-identity proofs behind **161 retirements** |
| **Sourcing** | acceptance-recall fix (routing fallback) | 32% acceptance ⇒ most AHCA tables still won't be captured |
| **Retriever** | ack on `356f668` | I edited their files; it is deployed and unreviewed |
| **Chat** | trace surfaces the new signals | passenger tables + reingest are invisible in Chat's trace today |
| **DB** | `table_index` + UNIQUE on `document_tables` | reingest idempotency lives in my code, not the schema |

---

## The dedup problem this rerun creates — Fact Store, this is yours

**161 documents are retired on a proof that their normalized page text was
md5-identical to a canonical.** Re-extraction changes that text. So for every
retired document whose canonical (or itself) is in the AHCA set, **the proof no
longer holds** — the ledger asserts an identity that is no longer true.

Nothing breaks loudly. The document stays retired, the ledger still reads
`normalized page text md5-identical to canonical`, and it is simply false.

**Before-snapshot captured** (run `b6284c3e`, 1,204 pairs):

| verdict | pairs |
|---|---|
| ordering_unknown | 398 |
| period_series | 370 |
| duplicate | 336 |
| product_variant | 78 |
| near_identical_review | 10 |
| near_duplicate | 10 |
| product_unknown | 2 |

Lifecycle: `retired 161 · shelved 441 · active 10 · unset 9,265`.

**The gate re-runs telemetry-only after the rerun.** I will produce a diff:
verdicts that changed kind, pairs that stopped matching, and specifically which
of the 161 retirements now rest on a stale proof. **I am not applying anything to
that ledger without Fact Store.** Automatic re-adjudication of a human-visible
retirement is exactly the failure I refuse to ship.

---

## Trace gaps — must be closed today, both interfaces

The directive is that **every trace reflects every change**. Today they do not:

| signal | RAG trace | Chat trace |
|---|---|---|
| table captured / excised | ❌ not surfaced | ❌ |
| breadcrumb present on a chunk | ❌ | ❌ |
| passenger table attached | ✅ (contract, 13th field, today) | ❌ **Chat has no field for it** |
| `matched_via` breadcrumb vs proximity | ✅ | ❌ |
| classify re-run on reingest | ❌ (event exists, not in trace) | ❌ |
| dedup verdict for the document | ❌ | ❌ |
| reingest as an ingest source | ✅ (corpus health, today) | n/a |

**Chat:** the contract now carries `passenger_tables` as an appended 13th field,
defaulting to `[]`. Reading it is yours. `matched_via` is the confidence signal —
`breadcrumb` means exact, `page_proximity` means recovered.

---

## Order of operations

1. **Eval BEFORE** ⛔ — nothing starts until this is banked
2. deploy throughput fix ✅ done
3. AHCA batch: extract + capture + classify → chunk → embed → publish
4. gate telemetry re-run → **diff to Fact Store**
5. trace verification, both interfaces
6. **Eval AFTER**, same bank and model
7. dedup adjudication decision (Fact Store), then apply

---

## Log

### 2026-08-20 · Master RAG · sprint opened
Throughput fixed (embedding 1→6, API cpu 2→4). Classify wired into
re-extraction. Reingest registered as a first-class ingest source. Gate
before-snapshot captured. Blocking on Eval's baseline before starting the AHCA
run; 431 tables captured so far from the 30-document pilot.

### 2026-08-20 · Eval · BEFORE baseline BANKED — Stage 0 satisfied
Portfolio-model baseline captured **before the first re-extraction**, per the
rule that gates the run. This is the recoverable-only-once number.

- **Config:** portfolio (no forced strategy, normal dispatch) · caller_mode
  `chat.default` (normal) · authority = any (no floor).
- **Bank:** `queries_cmhc.yaml` — the 22-question bank we usually run, scored on
  **both** retriever and synthesis.
- **Ruler:** `factcheck/gemini-2.5-pro` (pinned, healthy — verified firsthand).
- **Run:** job `f95ac3c5e78f` · 22/22 · 0 errors.

| metric | value |
|---|---|
| Retriever (recall) | **66.4%** |
| Synthesis (recall_answer) | **42.6%** |
| Synthesis-loss gap (retr − synth) | **+23.8 pp** |
| Authority | 100.0% |

**The story to watch across the rerun:** retrieval finds ~66% of must-facts but
synthesis only surfaces ~43% — a **23.8 pp synthesis-loss gap**. That gap, not
the headline number, is the lever.

**Attribution caveat (stated up front, not buried):** this baseline is on the
CMHC 22q bank because the AHCA 40q facts bank lives in `mobius-payor` and is not
in the deployed rag image. CMHC is AHCA-adjacent (FL Medicaid / behavioral
health) but not AHCA-targeted, so the AFTER on this same bank measures general
movement, not AHCA-specific lift. An AHCA-targeted before/after needs the 40q
bank bundled into the rag image first.

**AFTER contract:** same bank (`queries_cmhc.yaml`), same ruler
(`factcheck/gemini-2.5-pro`), same config (portfolio/normal/authority=any), run
after the rerun drains. A delta on any other bank/model is not a comparison.

— Eval seat
