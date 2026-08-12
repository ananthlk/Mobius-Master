# Raw-Doc Contract — Sourcing → Curation  (DRAFT v0)

**Status:** v0 **CONVERGED** 2026-07-22 (Sourcing ⨯ Curation, both code-verified) —
**ready for Technical Review to gate** the boundary (typed seam, zero logic crossing),
then **Master RAG** coordinates. Consumer-side filled (§5), boundary ruled (§6),
Sourcing accepts + final producer contract (§8). Code-move-deferred per Ananth's
shared-checkout protocol.
Mirrors the downstream [`curated-chunk-contract.md`](curated-chunk-contract.md)
(Curation → Retriever). Companion: [`module-map.md`](module-map.md) seam #2 (`app/worker` split).

**Doctrine:** clean pairing — Sourcing *output* (a landed, extracted, enqueued
document) is Curation *input*. No chunk/embed/publish logic in Sourcing; no
ingest/extraction/fetch logic in Curation. This doc pins the seam so neither side
reaches across it.

---

## 1. Parties
- **Producer / owner:** Sourcing — land (upload · path_b-ingest · drive · web) →
  extract raw file to pages → enqueue chunking.
- **Consumer:** Curation (claims the job → chunk → embed → tag → publish).
- **Gate:** Technical Review (approves the boundary is typed + non-crossing).
- **Coordinator:** Master RAG.

## 2. The seam (physical)

Three tables + one **queue trigger**. Sourcing writes all three; Curation's worker
loop (`app/worker/main.py`: `main → worker_loop → process_job → run_chunking_loop`)
**claims** the job and reads the other two.

| artifact | table | who writes | who reads |
|---|---|---|---|
| the document | `documents` | Sourcing | Curation (read-only) |
| extracted text | `document_pages` (one row per page) | Sourcing | Curation (read-only) |
| **the trigger** | `chunking_jobs` (`status="pending"`) | Sourcing (enqueue) | Curation (claims → `processing`) |

**The handoff is the `chunking_jobs` queue.** `process_job` (`app/worker/main.py`)
loads the `Document` + all `DocumentPage`s for the job's `document_id`, and
**fails the job if no pages exist** (`"No pages found for document"`) — i.e. Curation
never extracts; it requires pages to pre-exist. That is the seam line (see §6).

Ingest/extract/enqueue today all live in the **`app/main.py` god-file** (not yet a
Sourcing router): `Document(status="uploaded")` → `status="extracting"` → 8×
`DocumentPage(...)` build sites → `ChunkingJob(status="pending", ...)` enqueue sites.
Until `main.py`→per-leg-routers lands (module-map seam #4), these paths stay in the
map, not path-globs.

## 3. Row shapes (**DB-ratified against live schema 2026-07-22** — corrections applied inline; code-verified vs `app/models.py`)

**`documents`** (identity/provenance Sourcing owns)
| column | type | notes |
|---|---|---|
| `id` | UUID | |
| `filename`, `display_name` | varchar | |
| `status` | varchar(20) | live: `uploaded → extracting → completed / failed`. **`needs_ocr`** (276 docs, OCR backlog) = no pages coming → treat as no-handoff, same as `failed` (overlaps Maintaining's leg). ⚠️ **`completed_with_errors` is NOT a live status** (stale model comment) — error signal is `has_errors`/`error_count`. Sourcing owns the lifecycle up to "pages ready". |
| `has_errors`, `error_count` | str-bool, int | the real per-doc error signal (not a status value) |
| `review_status` | varchar(20) | `pending / approved / rejected / reprocessing` |
| `source_metadata` | JSONB | **web URL = `source_metadata->>'source_url'`** (~4798 rows; set by import-from-gcs/html; feeds `corpus_by_host`). ⚠️ there is **no top-level `source_url` column** on `documents`. |
| authority/payer/state/program/dates | various | denormalized later into the published seam (§3 of curated-chunk-contract) — **origin is here** |

**`document_pages`** (the extracted content — the payload of the handoff)
| column | type | notes |
|---|---|---|
| `document_id` | UUID | FK |
| `page_number` | int | ordering key the worker sorts by |
| `text` | TEXT | raw extracted text |
| `text_markdown` | TEXT | preferred by the coordinator when non-empty (`raw_page_to_markdown` fallback) |
| `text_length` | int | |
| `extraction_status` | varchar(20) | `success / failed / empty` |
| ⚠️ `source_url` | — | **DECOY — physically present but 100% EMPTY (0/202868). Do NOT wire the seam to it.** Web URL lives on `documents.source_metadata->>'source_url'`. |

**`chunking_jobs`** (the trigger — **Sourcing sets the enqueue params today; see §6 OPEN**)
| column | type | notes |
|---|---|---|
| `document_id` | UUID | |
| `status` | varchar(20) | `pending → processing → completed / failed / cancelled / blocked` |
| `generator_id` | varchar | **`A`** (LLM extraction/facts, path_a) or **`B`** (deterministic policy lines/tags, path_b) |
| `extraction_enabled`, `critique_enabled` | str-bool | path-A knobs |
| `threshold`, `max_retries` | | path-A knobs |

**`discovered_sources`** (web-sourcing provenance — Sourcing-owned, NOT read by Curation)
| column | type | notes |
|---|---|---|
| `url`, `content_type`, `last_fetch_status` | | ~11k rows; 200/403/404/451/-1 |
| `ingested` | bool | true once pulled into `documents` |
| `ingested_doc_id` | UUID | FK → `documents.id` — the web→raw-doc link |
| `curation_status` | varchar(20) | `auto`/… (Sourcing's escalation state) |

## 4. Sourcing's write guarantees (producer side — proposed)
1. **Pages-before-job ordering.** A `chunking_jobs(status="pending")` row is
   enqueued **only after** all `document_pages` for that `document_id` are committed.
   (Worker fails a job with no pages — this guarantee is what makes the queue safe.)
2. **Extraction terminal before enqueue.** `documents.status` has left `extracting`
   (pages materialized) before the job is visible. Rows with 0 usable pages are
   *not* enqueued — surfaced as `documents.status=failed`, or **`needs_ocr`** when the
   raw file needs OCR (OCR backlog; a Sourcing/Maintaining boundary — see §3).
3. **Provenance stamped at land time** — `documents.source_metadata->>'source_url'`
   for web/html (a JSONB key, **not** a top-level column); for web-sourced docs,
   `discovered_sources.ingested=True` + `ingested_doc_id` set atomically with the
   `documents` insert.
4. **Idempotent re-ingest.** Re-extraction (`restart_extraction`) replaces
   `document_pages` for the doc and re-enqueues; a re-run fully supersedes.
5. **One authoritative doc row per `document_id`** — identity/authority/payer
   metadata is written here (Curation denormalizes it downstream; it does not mint it).

## 5. OPEN — Curation to specify (consumer side)
1. **Exact page fields the worker requires** — `text` vs `text_markdown` (coordinator
   prefers markdown when present): is markdown a hard requirement or best-effort?
   Min `extraction_status` accepted (`success` only, or also `empty`)?
2. **Hard invariants Curation depends on** — pages non-empty; `page_number` contiguous
   from 1?; a max page count / size ceiling?; encoding guarantees on `text`.
3. **Job-param authority (the real question).** `generator_id` (A vs B),
   `extraction_enabled`, `critique_enabled`, `threshold`, `max_retries` are set by the
   *enqueuer* (main.py, Sourcing edge) today. **Which of these are a Curation decision
   that should move to the consumer side?** Path A/B selection is arguably "how to
   curate," not "how to source.
4. **Fields Curation needs but Sourcing doesn't produce today** → becomes Sourcing backlog.
5. **Trigger semantics** — is the `chunking_jobs` queue the seam you want, or a typed
   event? Claim protocol (row-lock / status CAS) — who owns zombie-recovery
   (`recover_finalized_zombies` lives worker-side today)?

### 5 — Curation consumer-side (FILLED 2026-07-22, code-verified vs `app/worker`)
1. **Page fields — `text_markdown` is BEST-EFFORT, not hard.** `run_chunking_loop`
   uses `page.text_markdown` when non-empty-after-strip, else
   `raw_page_to_markdown(page.text or "")` (`coordinator.py:66-70`). Hard
   requirement = **each usable page has non-empty `text` OR `text_markdown`**; a
   page empty in both is silently skipped (`:71`). **Min accepted = ≥1 usable page
   per doc.** The worker does not read `extraction_status`; per-page `empty` is
   tolerated (skipped). Keep enqueuing only docs with ≥1 usable page (your #2 — good).
2. **Invariants:** `page_number` = a sortable ordering key (`order_by(page_number)`,
   `main.py:232`) — **contiguity-from-1 NOT required**, gaps tolerated. ≥1 usable
   page. `text`/`text_markdown` = valid UTF-8 str. **No hard page/size ceiling in the
   contract**, but very large docs (~9k+ units) risk `job_timeout`/`oversize`-block on
   my side (historical 503s) — a priority/flag signal, not a reject. Backlog, not an invariant.
3. **Job-param authority — RULING: all chunking/generator params are CURATION
   authority.** `generator_id` (A/B), `extraction_enabled`, `critique_enabled`,
   `threshold`, `max_retries`, `prompt_versions`, `llm_config_version`,
   `skip_embedding`, `chunking_config_snapshot` = "how to curate." The worker already
   **resolves** them against Curation-owned `worker_cfg` defaults (`main.py:245-258`;
   gen B forces `extraction_enabled=False`). **Target:** you enqueue `document_id` +
   `priority` + source_kind; Curation resolves all chunking params at claim-time from
   Curation policy. **Interim (no code moves now):** you may keep writing them, but the
   values/defaults are Curation's — don't mint curation policy on the source edge.
   - **`priority` is the one param you legitimately set** — you know urgency (instant
     chat upload=0 vs batch corpus=10); it drives my instant/batch lane split
     (`worker_loop instant_only`). You write intent; I own the claim mechanics. Keep it.
   - `skip_embedding` is Curation/Lexicon-internal (retag path) — you never set it.
4. **Fields I need but you don't produce today:** none new. `documents` +
   `document_pages` cover chunking inputs; downstream doc-metadata originates in
   `documents` (already yours) and I denormalize it — no gap.
5. **Trigger semantics — the `chunking_jobs(status="pending")` queue IS the seam I
   want.** The pending row is the typed event; no separate event bus needed now.
   **Lifecycle split:** you own **pending-creation**; **Curation owns the job lifecycle
   from claim onward** — status CAS `pending→processing` (+`worker_id`), the priority-lane
   claim, terminal states (`completed`/`failed`/`blocked`-after-3/`cancelled`), and
   **zombie recovery** (`_finalize_job_atomic` fresh-session + `recover_finalized_zombies`,
   worker-side). Clean line: **your write ends at `pending`; everything after is mine.**

## 6. The boundary question — extraction (the `app/worker` split, seam #2)
**Sourcing's proposal:** the split line is **`document_pages`**. Raw file → pages
(extraction) is the **tail of ingest (Sourcing)**; paragraph→chunk→enrich→embed
(everything `run_chunking_loop` and below) is **Curation**. Rationale: the worker
already *requires* pages to pre-exist and only reads them — extraction is not in
Curation's module-map subsystem list (chunking · embedding · lexicon · publish),
and "get documents INTO rag" naturally includes materializing their text.

**Consequence for `app/worker`:** on this line, `coordinator.py` + `path_a/path_b`
are **entirely Curation** (they operate on pages, not raw files); the "ingest half"
the architect flagged is the extract-and-enqueue code **currently in `main.py`**, not
in `app/worker`. If Curation agrees, the `app/worker` split is cleaner than expected:
`app/worker/**` → Curation, and Sourcing's edge is the main.py extract/enqueue paths
(which move to a Sourcing router under seam #4). **Curation: confirm or counter.**

### 6 — Curation ruling: CONFIRM the `document_pages` split ✅
Code-verified: `process_job` **fails a job with no pages** (`main.py:235-241`) and
`run_chunking_loop` only **reads** pages (`coordinator.py:61-73`) — the worker never
extracts raw files. Therefore:
- **`app/worker/**` → Curation entirely** (`coordinator` · `path_a` · `path_b` · `db`
  · `context`, all operate on pages). **No intra-package split needed** — seam #2 is a
  clean *assignment*, not a cut. Cleaner than the module-map assumed.
- The **"ingest half" = the extract+enqueue code in `app/main.py`** (your edge) → moves
  to a Sourcing router under **seam #4** (main.py decomposition, Master RAG coordinates).
- ⚠️ **NAMING COLLISION to fix in the final contract** (same class as the `curator`
  rename, so Tech Review's gate is clean): **"extraction" is overloaded** — *your* step
  = raw file → pages (**page/text extraction**); *my* `extraction_enabled`/path_a step
  = **fact/structure extraction from pages**. Let's name them distinctly (e.g.
  `page_extraction` vs `fact_extraction`) so the `document_pages` seam line reads
  unambiguously.

**Net:** split confirmed · params ruled Curation-authority (`priority` excepted) ·
job lifecycle-from-claim is mine · one naming fix before Tech Review gates.

## 7. Next
Curation fills §5 + rules on §6 → we converge → **Technical Review gates** the
boundary → report to Tech Review + Master RAG. Then align the column list with
Data & DB (schema authority). **No code moves** (curator rename, any `app/worker`
line, main.py extraction) until Ananth's shared-checkout work-sequencing protocol —
this doc is design only.

## 8. Convergence — Sourcing accepts (2026-07-22)
Both sides code-verified; Sourcing accepts Curation's §5/§6 rulings. **This section is
the authoritative producer contract** (supersedes §4 where they differ).

**Final enqueue contract (target).** Per document, Sourcing writes exactly:
- **`documents`** — identity / provenance / authority metadata. Sourcing owns it;
  Curation *denormalizes* downstream, never mints.
- **`document_pages`** — ≥1 usable page (non-empty `text` OR `text_markdown`; valid
  UTF-8; `page_number` is a sort key, gaps OK; `text_markdown` best-effort, worker
  falls back to `raw_page_to_markdown(text)`).
- **`chunking_jobs(status="pending")`** carrying **only** `document_id` + **`priority`**
  + `source_kind`. Everything else — `generator_id` (A/B), `fact_extraction`
  (= today's `extraction_enabled`), `critique_enabled`, `threshold`, `max_retries`,
  prompt/`llm_config` versions, `chunking_config_snapshot`, `skip_embedding` — is
  **Curation authority**, resolved at claim-time.
- **`priority` is Sourcing's** (instant chat upload=0 vs batch corpus=10 → drives
  Curation's instant/batch lane). `skip_embedding` is never set by Sourcing.

**Interim (until the sequencing protocol permits code moves):** Sourcing may keep
writing the legacy job params, but values come from **Curation-owned defaults** — no
curation policy minted on the source edge.

**Lifecycle (accepted).** Sourcing's write ends at `status="pending"`. Curation owns
claim → terminal (CAS `pending→processing`, priority-lane claim,
`completed`/`failed`/`blocked`/`cancelled`, zombie recovery).

**Naming disambiguation (adopted — pre-gate hygiene, same class as the `curator` rename):**
- **`page_extraction`** — raw file → `document_pages` (**Sourcing**, tail of ingest).
- **`fact_extraction`** — today's `extraction_enabled`/path_a fact+structure extraction
  *from* pages (**Curation**).
The `document_pages` seam line now reads unambiguously. Sourcing adopts the
`page_extraction` vocabulary in its edge; Curation renames its param. Design-agreed;
code-move deferred.

**Resulting Sourcing work-items (all gated on Ananth's shared-checkout protocol):**
1. `app/curator` → `app/web_sourcing/` (seam #1 rename).
2. main.py extract+enqueue → a Sourcing router: adopt `page_extraction` naming; trim
   the enqueue to `document_id + priority + source_kind` (seam #4).
3. No `app/worker` change — confirmed **Curation-entire** (seam #2 is an assignment).

**Seam status: CONVERGED — ready for Technical Review to gate the design.** Byte-compat
verification happens when the code moves land under the sequencing protocol.
