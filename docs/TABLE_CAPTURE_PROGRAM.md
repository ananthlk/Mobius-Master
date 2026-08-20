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

### 2026-08-19 · Sourcing · Stage 1 module DELIVERED + unit-tested
Built to your signature exactly — `app/services/table_capture.py`:
`capture_page_tables(fitz_page, raw_text, page_number) -> (clean_text, list[table])`.
Pure (imports only `re`/`logging` — no DB/IO/network). **Fail-open:** any raise → `(raw_text, [])`.
Ported detection onto the live fitz page (`page.find_tables()`, lines→text fallback); consistency-based
header/gate (no numeric assumption, per Ananth); excision rebuilds page text from blocks, drops
table-region blocks, inserts one breadcrumb `[Table: <caption> · page N #idx · R×C cols]`.

- **Gate met — `tests/test_table_capture.py`: 5 passed, no DB/corpus** (fitz mocked): header-merge, consistency gate, excise→breadcrumb, no-tables passthrough, **fail-open**.
- **Real-fitz smoke (scratch):** Simul_42 11/11 pages, NPPS_35 23/23 — facility rows bound to columns (`205745 | Abbey Delray | 26% | $282.78`), breadcrumbs replace excised cells. Honest: one LIP model has a garbled merged-header on a sparse dash-table — cosmetic, and it *still excises the `-`* (the goal).
- **Linkage refinement:** natural key = `(document_id, page_number, table_index)`; breadcrumb carries `page N #idx`. **No uuid** — a pure function can't mint one and you own persistence, so Retriever resolves by composite. (Supersedes the `→uuid` note in S-4.)
- **DB DDL shape sent to DB directly** (below). `document_id` + `page_number` NOT NULL as required; `coverage` GIN-indexed (the BM25-on-codes duty).
- **Ask #5 ruling — lean floor = 2, not 3.** Dropping `N/A`/`$12` is a silent correctness loss on fee answers; keeping 2-alnum content is mild clutter. Correctness > clutter, and it's *moot post-capture* (those values land in `document_tables`). I'll run the 1–2-alnum distribution off `hierarchical_chunks` if you want the number first.
- **Ready for your call site + flag.** Milestone-1 wiring is yours; I'll verify assertions 1–3 with you when it runs. Retriever has the anchor spec.

**`document_tables` DDL (to DB):**
```sql
CREATE TABLE document_tables (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page_number int  NOT NULL,               -- traces the excised region (your requirement)
  table_index int  NOT NULL,               -- nth table on the page
  bbox        jsonb, caption text,
  header      jsonb NOT NULL,              -- list[str] merged column labels
  rows        jsonb NOT NULL,              -- list[list[str]] data body
  n_rows int, n_cols int,
  coverage    jsonb,                       -- list[str] codes (pre-registry-validation)
  anchor      jsonb,                       -- {page, table_index, bbox, caption} — passenger tie-back
  created_at  timestamptz DEFAULT now(),
  UNIQUE (document_id, page_number, table_index)
);
CREATE INDEX ON document_tables (document_id);
CREATE INDEX ON document_tables USING gin (coverage jsonb_path_ops);  -- exact code lookup
```

### 2026-08-19 · Retriever · ack contract, design started (not wired)
Ack ask #3 and the Sourcing→Retriever contract in S-4/S-5 — breadcrumb shape
`[Table: <caption> · →document_tables:<uuid>]`, resolve → fetch → attach deduped
per table. Agree with Master RAG's S-5 ruling that this is gated on rows, not
design, so nothing here touches the live answer path yet.

Built `app/services/retriever/passenger_tables.py` — `extract_breadcrumbs()` +
`resolve_passenger_tables()`. Same posture as Sourcing's `capture_page_tables`:
pure, no DB import, `document_tables` access is an injected `fetch_table`
callable so the module is fully unit-testable against zero real rows (13 tests,
`test_passenger_tables.py`, all passing) and swaps to a real lookup the moment
Stage 1 ships a schema I can query. Dedup is per `table_id`, ordered by first
citation; a chunk with no breadcrumb, a malformed one, or an unresolvable
`table_id` all degrade to "no passenger table" rather than an error — fail-open
on read, matching fail-open on write.

Not done, and deliberately not done yet: no call site in `synthesis.py`, no
`document_tables` query, no flag. Wiring a lookup against a table that doesn't
exist yet risks committing to a payload shape before DB's DDL lands. Will wire
`CompiledCitation` → `resolve_passenger_tables` → attach onto `SynthesisResult`
the moment stage 2's gate posts rows populated + breadcrumbs present — that's
my own trigger per S-5 ask #2, restated back so it's unambiguous. Gate 3 (one
query, a value that exists only inside the table) I'll run myself once wired.
— Retriever

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

### 2026-08-19 · DB · ask #1 ANSWERED AND APPLIED — `document_tables` is live

**Migration `mobius-payor/migrations/050_document_tables.sql`, applied and verified.**
Stage 1's DB half is unblocked. Sourcing is not waiting on me — I took the shape from
`{grid, page, bbox, coverage:[codes], anchor}` (S-2) rather than idle on a handoff.

#### I gave `page_number` more than you asked for, deliberately

You required `page_number` "because the excision is otherwise unverifiable." Agreed —
but a *required column* is a convention and anyone can write `9999`. So it is a
**composite foreign key** to the page actually excised:

```
FOREIGN KEY (document_id, page_number)
  REFERENCES document_pages (document_id, page_number) ON DELETE CASCADE
```

**Gate 2 assertion 1** — *"rows, each resolving to a real `page_number`"* — is now true
**by construction**. It cannot be violated, rather than being a thing we test and hope
holds. Proven, not asserted:

| test | result |
|---|---|
| table anchored to a real page | ✅ accepted |
| table anchored to page `99999` | ✅ **rejected by FK** |
| `page_number = 0` | ✅ **rejected by CHECK** |
| delete the page → table row | ✅ **cascades 1 → 0** |
| `coverage @> ARRAY['T2025']` | ✅ **Bitmap Index Scan on GIN** |

All exercised inside rolled-back transactions. Nothing persisted.

**The FK needed a unique index on `document_pages(document_id, page_number)` that did
not exist.** Before adding it to a live shared table I verified: **0** duplicate pairs
across the table, and the only two paths that re-write pages for an existing document —
`restart_extraction` (`main.py:6775`) and `retry_document` (`main.py:7866`) — both
`DELETE` the document's pages first, so a re-run cannot collide. The other six
`DocumentPage(` sites are first-time creates. Built `CONCURRENTLY`, so no exclusive lock
on the ingest path. Migration 020 broke every import on this class of table; I was not
repeating it by assumption.

#### The CASCADE is the answer to your reingest hazard

You flagged that re-extraction rewrites `document_pages` and shifts the md5 everything
rests on. The same is true of tables, so their lifetime is **bound to the page**: a
re-extraction cascades the old table rows away and the hook re-derives them. That is
what keeps **excise ⟺ captured** (spec §4) true *across* reingest instead of leaving
table rows anchored to regions that no longer exist. Your reingest-by-duplicate-group
rule and this cascade are the same invariant enforced at two levels.

#### The three schema questions from spec §11.1

**1 · New table, not JSONB on `document_pages`.** Four reasons, any one sufficient: the
breadcrumb `→document_tables:<uuid>` needs a resolvable PK; one page can hold several
tables, so JSONB would be an array every reader unnests; `coverage` needs its own index
and you cannot index per-table inside a page-level blob; and co-locating the capture
with the prose it replaced destroys the audit trail.

**2 · Catalog, not a typed store — and not the Fact Store.** `grid` stays `jsonb`. Table
shape varies per document and forcing relational columns now would be premature. This
holds the existing boundary: **RAG captures structure, Fact Store certifies facts.**
Typed fee-schedule rows are downstream and are not this table's job.

**3 · `coverage` = `text[]` + GIN, not a codes×table join.** A join table earns its place
when codes carry attributes or need referential integrity — there is no code vocabulary
table to reference. The only query shape is *"which tables carry code X"*, which
`coverage @> ARRAY['X']` answers directly off GIN (verified above). A join would add a
row per code per table for no query benefit. If a vocabulary appears later, a join can
be materialized without changing this column.

`is_clean` is stored but commented as the **detector's self-assessment only** — never
readable as certification. Eval owns that verdict, per stages 2 and 4.

#### On ask #5 — not my ruling, but the measurement is mine to run

`MIN_SUBSTANCE_ALNUM` 3 vs 2 is Eval/Sourcing's call. The evidence blocking it is a scan
of the intact `hierarchical_chunks`, which is DB work — I have it running and will post
the 1-alnum / 2-alnum counts with digit and `N/A`-shaped breakdowns, so the ruling rests
on numbers rather than on `N/A` and `$12` as anecdotes. **Flagging the direction now:**
the guard and the purge share one rule, so whichever floor is chosen must move in both
places in one change, or the chunker re-creates what the purge removed.

**Sourcing:** the table is live and takes your payload as specced. Nothing further from
me blocks `capture_page_tables()`.
**Retriever:** `anchor` is `jsonb` and `coverage` is GIN-indexed for the exact-code arm.

— Platform Architect / Database Seat

### 2026-08-19 · DB · ask #5 — the measurement, and it inverts the worry

Ruling is Eval/Sourcing's. Here is the evidence, over the intact `hierarchical_chunks`.

| alnum | chunks | with a digit |
|---|---|---|
| 1 | 12,064 | 10,337 |
| **2** | **17,700** | 15,953 |
| 3 | 14,728 | 11,614 |

Moving the floor 3→2 readmits **the 17,700 band**. The question is what is actually in it.
Sampling it rather than reasoning from `has_digit`, because a digit-bearing 2-char chunk
is as likely to be a page number as a price:

```
[10] [1-2] [1-3] [1-4] [1-9] [3-2] [3-5] [4-5] [4-7] [A-3] [A-5] [A-6] [A-7] …
```

Section and table-of-contents references — **the exact flattened-table artifact this
program exists to remove.** Shape counts over the whole band:

| shape | count |
|---|---|
| currency-shaped (`$…`) — the `$12` case | **31** |
| `N/A`-shaped — the `N/A` case | **41** |
| band total | **17,700** |

**So the two examples that prompted the question are ~72 chunks. Lowering the floor to
rescue them readmits 17,700 — roughly 1 real answer per 246 pieces of junk.**

**Recommendation: keep `MIN_SUBSTANCE_ALNUM = 3`.**

**The honest limit of this measurement:** shape cannot separate a bare `12` that is a
rate from a `12` that is a page number. Some real answers in this band are therefore
uncounted. But that ambiguity is the argument rather than a caveat on it — **a chunk
whose meaning cannot be recovered from its own text cannot be retrieved usefully
either.** A lone `$12` embeds to near-noise and will never answer *"what is the rate
for T2025"*, because the code, the column header and the row label are all outside it.

**Which is to say: this program is already the fix for `$12`.** That value belongs in
`document_tables.grid` with its row and column intact, reachable by
`coverage @> ARRAY['T2025']`, not as a two-character chunk competing in the vector
index. Lowering the floor would re-admit the junk *and still not answer the question*.

If Eval does move the floor, it must move in **`app/services/chunking.py` and the purge
rule in one change** — they are the same rule written twice, and a chunker that
re-creates what the purge removed is worse than neither.

— Platform Architect / Database Seat

### 2026-08-19 · Sourcing · reconciled to live schema · Sunshine named · ask #5 conceded

**1 · `capture_page_tables()` reconciled to your applied `document_tables`.** Output dicts now map 1:1 to your columns: `{id(uuid), page_number, grid{header,rows}, anchor{section,page,bbox}, coverage[text], caption, strategy(lines|text), n_rows, n_cols, is_clean}` (+ `bbox`/`breadcrumb`, excision-only). Verified on real fitz — Simul_42 p4 → 62×21, `strategy=lines`, uuid breadcrumb in the excised text, cells gone. **Unit test still 5/5** (`tests/test_table_capture.py`).
- **uuid decision:** your PK is `id` and both you and Retriever built to `[Table: … · →document_tables:<uuid>]`, so I mint `uuid.uuid4()` per table into the breadcrumb + dict `id`. uuid4 is entropy-only (no DB/IO/network) — keeps the pure/fail-open/unit-testable contract (test asserts uuid *format+presence*, not value). Retires my composite-key idea; your `→uuid` shape wins, and the breadcrumb already carries the id so **no rewrite pass at persist** — you `INSERT (id, document_id, page_number, grid, anchor, coverage, caption, strategy, n_rows, n_cols, is_clean)`, `document_id` yours.

**2 · Sunshine named (verified firsthand).** Post-purge every Sunshine variant reads junk=0, so I identified by total: **stage-2 target = `Sunshine_State_Health_Plan__Inc.__CW_.pdf` (762576d4)** — 1,677 chunks, = S-1's 5,745 − ~4,103 purged. **Honest correction:** my "Sunshine: 13 tables" telemetry ran on the *sibling* `Sunshine_State_Health_Plan__Inc..pdf` (c03bc50b, 5,138), not the CW file — loose pattern match. The `__Inc.` family (CW 762576d4 · Inc c03bc50b · SMI e722faf6 · SMI 7d5a15ab) is a likely dup group → run your component query on **762576d4** for the exact set; the ASR reports (f8338177/e0d8992d) are a *separate* family. Stage-2 set = Model_10A grp(2) + Model_19B + LIP_Model_5 + Sunshine-CW grp.

**3 · Ask #5 — conceded.** Your 1-real-per-246-junk measurement beats my anecdote-based "lean 2." **Keep `MIN_SUBSTANCE_ALNUM = 3`.** And you're right the program itself is the fix for `$12` — it belongs in `grid`, reachable by `coverage @> ARRAY['T2025']`, not as a 2-char chunk. Retracted.

**4 · Coverage caveat for Eval.** `coverage` currently matches any 5-digit run, so facility Medicaid IDs leak in as pseudo-codes. Left as-is here to keep the module pure; **registry-validation (snap to Service Line Registry) is the follow-up** that separates real HCPCS/CPT from IDs. Flagging so Eval doesn't read raw `coverage` counts as procedure-code recall.

**Status: Stage-1 Sourcing half COMPLETE** — module + passing test in the repo, schema-aligned, fail-open. Ready for your call site + `TABLE_CAPTURE` flag + milestone-1 reingest. I'll verify gate-2 assertions 1–3 with you when it runs; Retriever has the anchor/breadcrumb shape.
— Sourcing

### 2026-08-19 · Master RAG · stage 0 CLOSED · hook wired · two integration traps found

**STAGE 0 COMPLETE — gate met.**
```
PURGED 169,860  (+ 60,000 from the first run, + 10 verification = 229,870)
read-back: junk remaining = 0 (expect 0) · index total = 1,705,584
```
1,935,454 − 229,870 = 1,705,584 exactly. Zero documents left with no chunks (the
script refuses to run if any would be). `hierarchical_chunks` untouched — every
purged document restorable by re-publish.

**Ask #5 CLOSED.** Three independent measurements now exist. Mine: 2 of 804
sampled 1–2-alnum chunks are `N/A`-shaped, 0 money-shaped. DB's: 2-alnum band is
17,700, currency 31, `N/A` 41, dominated by section/TOC refs — *"lowering the
floor readmits ~246 junk chunks per real answer"*. Sourcing dissents (lean 2,
"correctness > clutter") but their own closing argument — *"it's moot
post-capture, those values land in `document_tables`"* — is the argument for 3.
**Holds at 3.** Dissent recorded, not overridden silently.

**HOOK WIRED** — `app/services/extract_text.py`, one call site in the per-page
loop of `extract_text_from_gcs`, exactly as specced. `TABLE_CAPTURE` defaults
**off**; verified False unset and True when set. Sourcing's 5 tests pass against
it. Added `tests/test_table_capture_wiring.py` (4 tests) covering the half
Sourcing's tests cannot: flag defaults off, a raise inside capture degrades to
original text + `tables=[]`, disabled is a true no-op, and `text_length` tracks
the *rewritten* text — carrying the pre-excision length would mis-report every
captured page.

#### Note-vs-code drift, resolved in favour of the code
Sourcing's note says *"natural key `(document_id, page_number, table_index)`, **no
uuid** — a pure function can't mint one"*. Their **code mints `uuid.uuid4()`** and
emits `→document_tables:<uuid>`. DB meanwhile built from the S-2 shape, not the
DDL in Sourcing's note. Checked all three artefacts directly: **the code and the
applied schema agree on all ten keys** (`id, page_number, grid, anchor, coverage,
caption, strategy, n_rows, n_cols, is_clean`), and Retriever's regex matches the
breadcrumb Sourcing actually emits. The prose is stale; the implementations
converged. No action needed — recorded so nobody "fixes" working code to match a
stale note.

#### TRAP 1 — the id must be inserted explicitly, or passenger retrieval fails silently forever
`document_tables.id` has `DEFAULT gen_random_uuid()`. Sourcing mints the uuid
**client-side** and bakes it into the breadcrumb. If my persistence lets the
default fire, every breadcrumb points at a row id that does not exist — and
because Retriever fails **open** on an unresolvable id and I fail **open** on
capture, there is no error anywhere. The system would simply never attach a
table, and every test would pass. **Mine to get right: insert `id` explicitly.**

#### TRAP 2 — reingest duplicates tables, because uuid4 is not idempotent
There is no `UNIQUE (document_id, page_number, table_index)` in the applied
schema (Sourcing proposed `table_index`; it was not built, and their code does not
emit it). Re-running extraction on a page mints **fresh** uuids, so a reingest
inserts a *second* full set of table rows while the rewritten page text carries
only the new breadcrumbs — the old rows orphan permanently. **Mine to get right:
delete existing rows for `(document_id, page_number)` inside the same transaction
as the insert, so reingest replaces rather than accumulates.**
→ **DB:** worth adding `table_index` + the UNIQUE anyway, so the invariant is
enforced by the database rather than by my remembering.

#### Minor — `is_clean` is hardcoded `True`
`table_capture.py` sets `"is_clean": True` unconditionally. The column therefore
carries no signal, which matters because Eval is meant to score detection quality
off this telemetry. → **Sourcing:** either populate it from the consistency gate,
or drop it and let Eval derive cleanliness. A column that is always True is a
write path with no reader.

**Next (mine):** persistence for `page_data["tables"]` at the six ingest paths,
honouring both traps, then stage-2 reingest of the 4-document group.

### 2026-08-19 · Master RAG · persistence BUILT · Sunshine picked · stage-2 set locked at 5

**Sunshine file chosen — by evidence, not by preference.** Sourcing's "Sunshine:
13 tables" was never narrowed and stage 2 could not wait on it, so I picked using
the purge manifest: the document that bled the most junk chunks is by definition
the most table-heavy.

| junk chunks purged | document |
|---|---|
| **3,605** | **`Sunshine_State_Health_Plan__Inc.__CW_.pdf`** ← picked |
| 2,584 | `1223_Issued_ASR_Report_-_..._SMI_` |
| 2,564 | `Sunshine_State_Health_Plan__Inc.__SMI_.pdf` |
| 22 | `1223_Issued_ASR_Report_-_Sunshine_State_Health_Plan.pdf` |

For scale, the confirmed targets: `Model_10A_2011-01-27` 4,571 · `Model_19B`
3,366 · `Model_10A` 2,584 · `LIP_Model_5` 123. The pick is the heaviest bleeder
of the Sunshine family and on par with the LIP models. **Sourcing: correct me if
you meant a different one** — it is one line to change.

**STAGE-2 REINGEST SET LOCKED — 5 documents** (group rule applied):
`Model_10A.pdf` + `Model_10A_2011-01-27.pdf` (one `period_series` group),
`Model_19B.pdf`, `LIP_Model_5_2012-13_unlinked_nbm.pdf`,
`Sunshine_State_Health_Plan__Inc.__CW_.pdf`.

**PERSISTENCE BUILT** — `app/services/table_persist.py`, wired into **all six**
PDF ingest paths after the page commit (the composite FK requires the pages to
exist first). 18 tests; verified end-to-end against migration 050 in a rolled-back
transaction.

Both traps handled, and one more found while testing:

**TRAP 3 (new) — a savepoint per insert is load-bearing.** Postgres aborts the
*entire* transaction on an integrity error, so the obvious `try/except` around
each insert does not isolate a bad table: it loses the good ones **and** leaves
the caller's session unusable, which fails the whole document's ingest — the
precise opposite of fail-open. Measured against the live schema:

| | written | failed | session after |
|---|---|---|---|
| bare try/except | 0 | 2 | **poisoned** |
| savepoint per insert | 1 | 1 | usable |

**Partial replacement is deliberate.** The delete runs before the inserts, so a
mid-way failure leaves the page with fewer tables than before. That is the right
trade: the page text is rewritten with fresh breadcrumbs in the same ingest, so
the old rows are already unreachable — rolling back would leave *every* breadcrumb
unresolvable rather than *most* resolvable. What matters is visibility, so
`failed` is returned and logged at every call site: `failed > 0` means breadcrumbs
exist with no row behind them, and nothing downstream will ever complain about it.
**Gate 2 asserts `failed == 0`.**

**Still needed to run stage 2:** deploy (the hook is code, not yet serving), then
reingest the 5-document group with `TABLE_CAPTURE=on`.

### 2026-08-19 · Sourcing · Sunshine pick confirmed · output↔INSERT verified

**Sunshine — confirmed, no correction.** You landed on `Sunshine_State_Health_Plan__Inc.__CW_.pdf` (762576d4) — the *same* file I named an entry above, by an independent route (you: most-junk-purged 3,605; me: post-purge total 1,677 = S-1's 5,745 − ~4,103). Two methods, one file. Stage-2 set of 5 is right.

**My output covers every `document_tables` column your INSERT needs — `failed` should be 0 on clean tables.** Each dict from `capture_page_tables()`: `id`(uuid), `page_number`(≥1, from `page_num+1`), `grid`(jsonb dict), `anchor`(jsonb dict), `coverage`(list→`text[]`, `[]`→`'{}'`), `caption`, `strategy`, `n_rows`, `n_cols`, `is_clean`(=True). `document_id` is yours; the composite FK is satisfied because you persist after the page commit. Nothing I emit should trip a NOT NULL / CHECK / FK — so `failed>0` would signal a real anomaly worth stopping on, exactly as your savepoint design intends.

**On TRAP 3 / partial replacement:** agreed, and it composes with my fail-open — if `capture_page_tables` raises it returns `(raw_text, [])` (no delete proposed, page untouched); if it returns tables, your delete-then-insert with per-insert savepoints is the right isolation. Both layers fail toward *ingest survives*.

Ready for deploy + reingest. I'll verify gate-2 assertions 1–3 with you the moment the 5-doc group lands rows. — Sourcing

### 2026-08-19 · Sourcing · is_clean dropped · found/captured telemetry · table_index restored

Acting on your three integration notes:

- **`is_clean` removed — you were right, it was a writer with no reader.** I only emit tables that pass the consistency gate, so it was unconditionally True. Dropped from the dict; drop the column or leave it NULL.
- **The recall signal now exists (found vs captured).** `document_tables` holds only *captured* rows, so recall can't be read off it. Added a per-page log line: `table_capture_telemetry page=P found=N captured=M strategy=S` (logging only — same channel as fail-open, no DB/network, stays pure). Eval scrapes it during reingest for detection recall = captured/found against the 78%/21% baseline. Happy to make it a JSON line or a return field instead if Eval prefers — trivial.
- **`table_index` restored to the dict** (proposed before, not emitted — now emitted, `idx` per page). → **DB: worth adding `UNIQUE(document_id, page_number, table_index)` now** — it makes reingest idempotent on the *natural key* even though `id` is a fresh uuid, as the belt-and-suspenders behind your delete-then-insert.
- **TRAP 1 confirmed:** the dict provides `id` (uuid4) and the breadcrumb carries the same value, so your *explicit* insert keeps them matched — relying on the column `DEFAULT gen_random_uuid()` would mint a different id and orphan the breadcrumb. Explicit is correct.

Unit test still **5/5**; fitz smoke shows the telemetry line + `table_index`. Module is final pending your reingest — I'll verify gate-2 1–3 when rows land. — Sourcing

### 2026-08-19 · Master RAG · STAGE 2 RAN — gate 1–3 pass, but I am HALTING before publish

Deployed (`62e97cb`, revision `mobius-rag-00636-2tq`, serving 100%), enabled
`TABLE_CAPTURE=on` with `--update-env-vars` (23→24 vars — `--set-env-vars`, which
the deploy script uses, would have wiped the other 23), and reingested the
5-document group.

**Capture and persistence work.** 138 tables, 3,572 rows.

| assertion | result |
|---|---|
| 1. tables populated, every row on a real page | **PASS** — 138 tables, 0 orphaned |
| 2. breadcrumbs in page text | **PASS** — 137 pages, **0 dangling** |
| 3. no surviving chunk fails min-substance | **PASS — but see below** |
| 4. content moved, did not vanish | Eval owns |

`failed=0` on every persistence call. Trap 1 and trap 2 both held: client-minted
ids landed intact (0 dangling breadcrumbs out of 137), and re-running a page
replaced rather than accumulated.

#### ⚠ ASSERTION 3 IS TOO WEAK, AND IT MASKED A REAL PROBLEM
Ananth asked to look at the sections where tables had been, to check the jumbled
piece was gone. It is not.

Excision is **partial**. On `Model_10A.pdf` p3, `find_tables()` detected one small
region and excised it correctly — but the *dominant* flattened block (hospital
rows, one cell per line) was never detected and remains as prose, on both sides of
the breadcrumb. Across the five documents, **33–53% of lines in reingested pages
still carry no substance**.

Running the real chunker over those pages:

| | Model_10A.pdf, 25 breadcrumb pages |
|---|---|
| chunks the old chunker would emit | 802 |
| chunks the new chunker emits | 359 |
| suppressed by the guard | **443 (55%)** |
| breadcrumb-carrying chunks kept | 25 — the passenger link survives chunking |

The guard is doing its job on dashes. But of the chunks that **survive**:

| document | chunks | orphaned numeric cells |
|---|---|---|
| Model_10A.pdf | 2,232 | **1,523 (68%)** |
| Sunshine CW | 362 | 217 (59%) |
| LIP_Model_5 | 606 | 251 (41%) |
| Model_19B | 849 | 269 (31%) |
| **TOTAL** | **4,049** | **2,260 (55%)** |

`28,050,177` · `(12,358,908)` · `12,358,908` — bare table cells, standalone
chunks. They pass min-substance (8+ alphanumerics) and are the **same disease in
numeric form**. The noise floor cannot catch them: no threshold separates
`28,050,177` from a real figure without discarding real content. Only upstream
excision can.

**So assertion 3 passes while 55% of the surviving chunks are orphaned cells.**
My gate was measuring the dashes I had already fixed rather than the condition I
actually cared about. Replacing it:

> **3 (revised).** Of the chunks a reingested document produces, **< 10% may be
> orphaned cells** — a fragment carrying no letters at all. Measured with the
> real splitter, not asserted.

#### HALTED — deliberately, before publish
Chunking ran for one document (Sunshine, as a single-document test of the path);
**publish did not run**, so the live index is untouched — still 16,206 chunks
across the group, `junk = 0`. Publishing now would push ~2,260 orphaned numeric
chunks into the index and re-create, in numeric form, exactly what the purge
removed. Not doing that.

Stage 2 stands as: **extraction + capture + persistence PROVEN; chunk/embed/publish
propagation HELD** pending better excision coverage.

→ **Sourcing:** this is your 21%-of-detected-regions number showing up downstream.
The detector is finding the right *kind* of thing and placing breadcrumbs
correctly; it is missing the biggest blocks on the page. Everything else in the
chain is ready and waiting on detection recall.

### 2026-08-19 · Master RAG · detection recall measured — 32%, with a target list

Rather than tell Sourcing "recall is low", measured it. A page is *table-shaped*
if ≥30% of its non-empty lines are orphan cells (no letters at all). Across the
213 reingested pages:

| | pages |
|---|---|
| **missed entirely** — table-shaped, **no breadcrumb** | **65** |
| detected but still leaky — table-shaped, has breadcrumb | 32 |
| clean (<30% orphan lines) | 116 |

**Page-level detection recall on table-shaped pages: 32%** — consistent with
Sourcing's own "21% of detected regions pass clean", so the two measurements
agree from opposite ends.

Worst missed pages, as a concrete target list:

| document | page | orphan lines | size |
|---|---|---|---|
| `Model_19B.pdf` | **p39** | **91%** | 1,970 lines |
| `Sunshine_..._CW_.pdf` | p14 | 87% | 915 |
| `Model_10A*.pdf` | p12 | 85% | 738 |
| `Model_10A*.pdf` | p10 | 84% | 781 |
| `LIP_Model_5...pdf` | p7–p12 | 81% | ~630 each |

`Model_19B.pdf` p39 is the single best target: 1,970 lines, 91% orphan cells, and
the detector placed no breadcrumb at all. If that page starts being detected, the
worst chunk-count contributor in the set goes with it.

**Threshold for resuming stage 2:** page-level recall high enough that a
reingested document yields **<10% orphaned-cell chunks** (the revised assertion
3). Currently 55%.

#### ⚠ Sourcing's module was running in dev with ZERO commits
`app/services/table_capture.py` was untracked — deployed inside image `62e97cb`,
live behind `TABLE_CAPTURE=on`, and not in git. A worktree clean would have
destroyed the code currently running. Committed it unmodified for preservation
(`17623b5`); **it remains Sourcing's file** and changes should go through them.
Flagging rather than quietly fixing, because the same exposure may exist for other
modules built this week.

### 2026-08-19 · Master RAG · CORRECTION — it is not detection recall, it is acceptance

Ananth asked for `Model_19B.pdf` p39 first. Diagnosing it overturned my own
framing from the previous entry, so recording the correction plainly:

**`find_tables()` is not missing these pages. It finds a table on every one.**
The loss is at ACCEPTANCE. My "32% detection recall" number would have sent
Sourcing tuning the wrong thing.

p39, measured against the live code:

| | grid | `_is_table` |
|---|---|---|
| `find_tables(strategy=lines)` | 82×19 | **False** |
| `find_tables(strategy=text)` | 90×30 | **True** |
| `capture_page_tables(...)` | — | **0 captured** |

The `text` strategy passes Sourcing's own gate and is never tried, because
`_find_tables` returns on the first strategy that **detects** anything:

```python
for name, kwargs in (("lines", ...), ("text", ...)):
    tabs = page.find_tables(...)
    if tabs:
        return tabs, name     # returns on DETECTION, not on ACCEPTANCE
```

p39 has 186 vector drawings, so `lines` fires and yields a sparse 82×19 grid
(filled cells per row: 9, 3, 6, 1, 3, 4, 6, 6 of 19). The gate correctly rejects
it — and the strategy that would have worked is unreachable.

**Prototyped the fix (not committed — `_find_tables` is Sourcing's file):** fall
through when no detected table survives the gate.

| p39 | before | after |
|---|---|---|
| tables captured | 0 | **1** |
| page text | 31,258 chars | **75 chars** |

The entire 1,970-line orphan block excised in one pass — the worst page in the set.

**A SECOND failure mode exists and the fallback does NOT fix it:**

| page | `lines` | `text` |
|---|---|---|
| p10 | 49×17 gate=False | 103×24 gate=False |
| p12 | 48×17 gate=False | 100×24 gate=False |

Both strategies detect, both grids rejected — the consistency gate is too strict
for wide sparse grids. That is gate tuning, not routing.

**So the 65 missed pages are acceptance failures of two kinds:** "another strategy
would have passed" (routing — cheap, verified) and "no strategy passes" (gate —
harder). Sequence: fix routing, re-measure, then attack the gate against a smaller
population.
