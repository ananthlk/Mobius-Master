# Table Capture — cleanup → extraction → forward propagation → validation → passenger retrieval

**OWNER (coordination):** Master RAG · **DATE OPENED** 2026-08-19
**PARTICIPANTS:** Sourcing · Retriever · DB · Eval · Chat · Master RAG
**THIS FILE IS THE CHANNEL.** Append a dated entry under your own heading; do not
edit anyone else's. Decisions are only real once they are written here.

---

## Why this program exists

A markdown table flattened one-cell-per-line turns every empty cell into its own
chunk. **229,870 chunks — 11.9% of the live vector index — carried fewer than 3
alphanumeric characters.** 185,261 were literally `-`. They embed to near-identical
vectors, so they occupy top-k at a uniform similarity (~0.684) and crowd real
content out of every answer that touches a fee schedule.

The junk is a *symptom*. The disease is that tables are being flattened into prose
instead of captured as structure. So this program does both: remove the bleed, and
close the hole it came from — then prove the table content comes back as something
retrieval can actually use.

**End state:** a chat answer about a rate cites a number that exists *only inside a
table*, retrieved because a prose chunk carried a breadcrumb to it.

---

## Five stages, five owners, five gates

Nothing advances on assertion. Each gate is a check someone other than the builder
can run.

| # | stage | owner | gate to advance |
|---|-------|-------|-----------------|
| 0 | Cleanup — purge the bleed | Master RAG | junk chunks = 0; no document left with zero chunks |
| 1 | Extraction module + schema | Sourcing + DB | `document_tables` DDL applied; `capture_page_tables()` unit-tested with no DB dependency |
| 2 | Forward propagation, 4 docs | Master RAG (wiring) | 4 assertions below all pass on the 4 LIP models |
| 3 | Passenger retrieval | Retriever | one query returns a value that exists only inside a table |
| 4 | Full reingest | Master RAG + Eval | detection recall scored against Sourcing's 78%/21% baseline |

---

## Stage 0 — Cleanup (Master RAG) · IN PROGRESS

**Rule.** `length(regexp_replace(trim(text),'[^[:alnum:]]','','g')) < 3`
Widened to U+2010 `‐` on Sourcing's ruling — that alone was 14,234 chunks.

**Scope.** `rag_published_embeddings` ONLY. `hierarchical_chunks` untouched, so
every purged document is restorable by re-publish — no re-fetch, no re-extraction.
Manifest: `scratchpad/purge_manifest.json` (document_id → count).

**Chunker guard (the same rule, written once).** `MIN_SUBSTANCE_ALNUM = 3` /
`has_min_substance()` in `app/services/chunking.py`, one condition in
`split_paragraphs_from_markdown` — the sole live producer for all ingest paths.
A chunker that re-creates what the purge removed is worse than doing neither, so
these two must move together or not at all.

**RESOLVED 2026-08-19 — threshold stays at 3.** I raised the concern that the
rule drops `N/A` and `$12` (two alphanumerics each), which are real fee-schedule
answers. Measured it against `hierarchical_chunks` (intact, so the evidence
survived the purge), 3% `TABLESAMPLE`:

| 1–2 alnum chunks in sample | 804 |
|---|---|
| `N/A`-shaped | **2** (0.2%) |
| `$NN` / `$NN.NN`-shaped | **0** |
| everything else | 802 (99.8%) |

The 802 are the same disease: `0\n0\n-`, bare digits, `N`, `X`, `OR`, `(0)`, `0%` —
orphaned table cells. Dropping the floor to 2 would re-admit roughly **26,000
chunks corpus-wide to rescue about 66 `N/A` fragments**, and a standalone `N/A`
with no surrounding context cannot answer anything anyway — the fix for those is
Sourcing's extractor putting the cell back in its row, not a lower noise floor.

Concern was real, evidence says it does not bite. Ask #5 is closed; Eval and
Sourcing need not spend time on it.

**Gate 0:** junk = 0 · index total reconciles to `1,935,454 − purged` · zero
documents left with no chunks (the script refuses to run if any would be).

---

## Stage 1 — Extraction module + schema (Sourcing + DB) · BLOCKED ON DB

### Sourcing owns: `app/services/table_capture.py`

```python
capture_page_tables(fitz_page, raw_text, page_number) -> (clean_text, list[table])
```

**Pure function.** No DB, no I/O, no network. That is not style — it means the
module is unit-testable without a corpus, and cannot take the ingest path down.

### The seam — and why it is not where it was asked for

Sourcing asked for a hook in `main.py`. **That seam does not exist.** `main.py`
constructs `DocumentPage(` in **eight** places: `upload_file`, `retry_document`,
`restart_extraction`, `import_document_from_gcs`, `import_document_from_html`,
`import_from_drive`, `drive_import_folder`, `import_scraped_pages`. Hooking one
leaves seven writing orphaned cells, silently, discovered weeks later as a
retrieval regression.

**Six of the eight** source their pages from one function —
`extract_text_from_gcs()` in `app/services/extract_text.py` — whose per-page loop
holds the **live `fitz` page object**: lines, words, bboxes. `main.py` only ever
sees the extracted string, so a hook there could not do line-based detection at
all. The other two are HTML lanes with no PDF; DOM tables are a separate lane and
are **explicitly out of scope here**.

**One call site, in `extract_text_from_gcs`:**

```python
# after: text = page.get_text()
if TABLE_CAPTURE:
    text, tables = capture_page_tables(page, text, page_num + 1)
    page_data["tables"] = tables        # carried out; main.py persists
```

**Ownership:** module = Sourcing. Call site, flag, and persistence = Master RAG.
Sourcing does not touch `main.py` — that keeps every ingest path covered by
construction rather than by both of us remembering.

**Fail-open, non-negotiable.** A raise inside `capture_page_tables` logs, sets
`tables=[]`, and returns `raw_text` **unmodified**. Ingest availability outranks
table quality. `TABLE_CAPTURE` defaults **off**.

### DB owns: `document_tables`

Required, beyond Sourcing's `anchor` + `coverage`:
- `document_id` — provenance, as every other corpus table carries
- **`page_number`** — the hook *removes* text from `document_pages`. Without the
  page a table cannot be traced to the region it replaced, and the excision is
  **unverifiable**: we would have deleted page content with no way to prove what
  replaced it. This is a correctness requirement, not a convenience.

---

## Stage 2 — Forward propagation on 4 documents (Master RAG) · GATED ON STAGE 1

Scope: **the 4 flagged LIP models only** — Model_10A (25 tables), Model_19B (22),
LIP_Model_5 (17), Sunshine (13). 77 clean tables, and the origin of the `-` flood.

Path: `upload → extract (+capture) → classify → chunk → embed → dedup/versioning
→ publish → served in chat`.

**Gate 2 — four assertions, all must pass:**
1. `document_tables` has rows, each resolving to a real `page_number`
2. page text for those regions is a **breadcrumb**, not orphaned cells
3. chunk count for those documents drops materially, and **no surviving chunk
   fails `has_min_substance`**
4. the 4 documents still answer their original queries — content **moved**, it did
   not vanish

**Proposed to Eval: you own scoring assertion 4**, not me. I should not certify
that content survived a transformation I wired.

### ⚠ Re-extraction changes document identity — this constrains the reingest order

The dedup/versioning gate rests on normalized page-text md5. Excising tables
**rewrites `document_pages`**, so every reingested document gets a new md5.

- Documents currently judged `duplicate` may stop matching, because one was
  reingested and its twin was not. **A partial reingest manufactures false
  non-duplicates.**
- The cleanup ledger's proof — *"normalized page text md5-identical to canonical"* —
  goes stale for any reingested document. **161 retired documents rest on it.**
- `content_digest` and version lineage shift under the versioning gate.

**RULE (Master RAG, binding on stages 2 and 4): reingest by duplicate group, never
by document.** If one member of a connected component is reingested, all members
are, so identity comparisons stay within-generation. Trivial to honour at 4
documents; not retrofittable at corpus scale.

---

## Stage 3 — Passenger retrieval (Retriever) · GATED ON STAGE 2

**Sequenced only once `document_tables` has rows.** Building the tie-back against
an empty table is building against nothing. This gates on evidence, not on design —
the contract below is Sourcing's and is not in question.

**Sourcing → Retriever contract:**
- *Sourcing writes:* inline breadcrumb `[Table: <caption> · →document_tables:<uuid>]`
  and `document_tables.anchor = {chunk_id/section, page, bbox}`
- *Retriever reads:* retrieved chunk → resolve breadcrumb/anchor → fetch the
  `document_tables` row → attach, deduped per table

**Gate 3 — one query, end to end:** retrieve a prose chunk carrying a breadcrumb,
resolve it, attach the table, and assert the answer contains **a value that exists
only inside the table** and nowhere in the prose. One honest query beats a suite of
green assertions that never left the module.

**Chat:** once gate 3 passes, the attached table needs a render path. Flagging now
so it is not discovered at demo time — the answer-card format system already has a
table format. Chat: does an attached passenger table fit it, or is a new signal
needed?

---

## Stage 4 — Full reingest (Master RAG + Eval) · GATED ON STAGE 3

Sourcing's per-table telemetry (`doc_outcome / tables_found / clean / strategy /
codes`) streams during reingest so **Eval scores detection recall** against the
published baseline: **78% clean on 10 docs, 21% of detected regions clean.**
Known-open on Sourcing's side: over-segmentation on `lines`, merged-header misses,
`Practitioner_Fee_Schedule` at 0 clean, BH Fee Schedule binary/OCR.

Reingest ordered **by duplicate group**, per the rule in stage 2.

---

## Asks on the table

| # | of | ask | blocks |
|---|----|-----|--------|
| 1 | **DB** | `document_tables` DDL incl. `document_id` + `page_number` | stages 1→4 — hard blocker |
| 2 | **Sourcing** | `capture_page_tables()` at the signature above, pure, fail-open | stage 2 |
| 3 | **Retriever** | ack the contract; start design, wire on gate 2 | stage 3 |
| 4 | **Eval** | own gate-2 assertion 4 and gate-4 recall scoring | stages 2, 4 |
| 5 | ~~Eval/Sourcing~~ | ~~`MIN_SUBSTANCE_ALNUM` 3 vs 2~~ — **CLOSED**, measured, stays at 3 | — |
| 6 | **Chat** | can the answer-card table format carry an attached passenger table? | stage 3 close-out |

---

## Log

### 2026-08-19 · Master RAG · program opened
Stage 0 executing. Purge rule widened to U+2010 per Sourcing. Chunker guard in and
tested: all junk forms rejected, offsets exact after filtering, indices contiguous.
Seam identified at `extract_text_from_gcs` after finding eight `DocumentPage(`
sites in `main.py`. Token granted to Sourcing at that seam (S-5). Retriever gated
on rows, not on design. Identity-vs-reingest hazard raised and ruled: reingest by
duplicate group.

### 2026-08-19 · Master RAG · ask #5 closed with evidence
Measured the `N/A` / `$12` concern I raised myself: 2 of 804 sampled 1–2-alnum
chunks are `N/A`-shaped, none are money-shaped, 99.8% are orphaned table cells.
Threshold stays at 3 in both the purge and `has_min_substance()`. No change.

### 2026-08-19 · Master RAG · stage-2 reingest set computed — the group rule already bites
Pre-computed the duplicate groups for the stage-2 targets so the "reingest by
group, never by document" rule can be honoured from the first run rather than
discovered mid-flight. Connected components over all 1,236 duplicate edges (411
components corpus-wide):

| target | group | note |
|---|---|---|
| `Model_10A.pdf` | **2** | pulls in `Model_10A_2011-01-27.pdf`, edge kind `period_series` |
| `Model_19B.pdf` | 1 | isolated |
| `LIP_Model_5_2012-13_unlinked_nbm.pdf` | 1 | isolated |

**The rule is not hypothetical.** `Model_10A` has a `period_series` sibling.
Reingesting one and not the other rewrites one side's `document_pages` and
therefore its normalized md5, while the other keeps the old generation — which is
exactly the comparison the period/duplicate classifier runs. The verdict could
flip on a transform, not on content. Both go together or neither does.

**Sunshine is unresolved.** Sourcing's "Sunshine: 13 tables" does not name a file
and there are 10+ Sunshine candidates, three of them ASR reports with large
published counts (3,858 / 5,108 / 753) that look like a version family.
**→ Sourcing: which file?** Naming it is the last thing stage 2 needs.

Stage-2 reingest set so far: **4 documents, not 3.**
