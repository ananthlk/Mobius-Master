# Curated-Chunk Contract — Curation → Retriever pool  (DRAFT v0)

**Status:** DRAFT v0, proposed by **Curation** 2026-07-22. Pending, in order:
Retriever fills the read-side (§5) → **Technical Review gates the boundary**
(typed seam, zero logic crossing) → **Master RAG** coordinates. **NOT final.**

**Progress (2026-07-22):** seam FACTS aligned with Retriever ✅. Tag JSONB shape
**PINNED** (§3a). **Binding §5 fill HELD** — Tech Review reserved the Retriever leg
(pool/consumer design included) for **Ananth to drive himself**; Retriever is
confirming with Tech Review whether this contract is carved out of that hold.
Retriever posted a **non-binding** read (§5a) meanwhile.

**Doctrine:** clean pairing — Curation *output* is Retriever pool *input* as a
**typed seam**. No retrieval logic in Curation; no curation/publish logic in the
Retriever pool. This doc pins the seam so neither side reaches across it.

---

## 1. Parties
- **Producer / owner:** Curation (chunk → embed → tag → **publish**).
- **Consumer:** Retriever (the "ONE shared timed pool" its fillers read).
- **Gate:** Technical Review (approves the boundary is typed + non-crossing).
- **Coordinator:** Master RAG.

## 2. The seam (physical)
One table: **`public.rag_published_embeddings`** — *"one row per published
embedding, written on user Publish"* (`app/migrations/add_publish_tables.py`,
`app/services/publish.py`). The code already calls it the **"dbt contract
table."** This document promotes it to a *typed, owned* seam.

Secondary/legacy read stores written best-effort by `publish_sync.py` — **Chroma**
and chat-PG **`published_rag_metadata`** — are NOT the primary seam. Retriever's
primary read is **pgvector on this table**. (Chroma dual-write is legacy cleanup —
flag to Maintaining, not part of this contract.)

## 3. Row shape (current, code-verified — authoritative column list to be
confirmed against live DB with Data & DB)

**Identity / provenance**
| column | type | notes |
|---|---|---|
| `id` | UUID | reuses `chunk_embeddings.id` |
| `document_id` | UUID | |
| `source_type` | varchar(20) | `hierarchical` (chunk) or fact-derived |
| `source_id` | UUID | FK to hierarchical_chunk / extracted_fact |
| `content_sha` | varchar(64) | `sha256(document_id + source_id + text)` — integrity/dedup key |

**Vector (live read path = pgvector)**
| column | type | notes |
|---|---|---|
| `embedding_vec` | **vector(1536)** | **LIVE** — queried by `PgVectorStore.search()`; HNSW cosine index `rag_published_embeddings_vec_hnsw`. **Rows with NULL `embedding_vec` are excluded from retrieval.** |
| `embedding` | JSONB | legacy dual-write (raw list[1536]); not the search path |
| `model` | varchar(100) | embedding model id (1536-d: text-embedding-3-small / gemini-embedding-001) |

**Chunk text + position**
| `text` | TEXT | embedded text: `summary\ntext` (hierarchical) or fact_text+extras (fact) |
| `page_number`, `paragraph_index` | int | |
| `section_path`, `chapter_path` | varchar(500) | |
| `summary` | TEXT | |

**Chunk tags (lexicon arm — Plan B)**
| `chunk_d_tags`, `chunk_p_tags`, `chunk_j_tags` | JSONB | j/p/d tags per chunk; **object keyed by tag_code, value = int `count`** (§3a); sourced from `policy_paragraphs.{d,p,j}_tags` joined by `(page_number, order_index==paragraph_index)`, DISTINCT ON latest. Three no-tags states (SQL `NULL`, JSON `null` 47,626 rows, absent) all → `{}` via consumer `... or {}`. **Silent NULL on join miss** — now observable per-doc (d5c1fb3). |

**FTS (BM25 arm)**
| `search_vec` | tsvector | **LIVE** — weighted multi-field GIN: A=filename+display_name, B=summary, C=section/chapter paths, D=text |

**Denormalized document metadata** (contract convention: **empty string when
null**, not NULL): `document_filename`, `document_display_name`,
`document_authority_level`, `document_effective_date`,
`document_termination_date`, `document_payer`, `document_state`(2),
`document_program`, `document_status`, `document_created_at`,
`document_review_status`, `document_reviewed_at`, `document_reviewed_by`.

**State:** `created_at`, `updated_at`, `source_verification_status`.

### 3a. Tag JSONB shape — PINNED (Curation, DB-RATIFIED 2026-07-22)
`chunk_{d,p,j}_tags` is a **JSONB object (map), keyed by tag code** (e.g.
`claims.timely_filing`) — **not a list**. **Value = a bare int `count`** (the
line-hit count for that tag in the source paragraph), copied from
`policy_paragraphs.{d,p,j}_tags` at publish. **Absent / NULL / JSON-`null` ⇒ no tags.**
- ⚠️ **CORRECTION (DB ratification):** my earlier pin said the value was a
  `{count, lines_total, avg_weight}` stats object — that is the **document-level**
  rollup (`document_tags`, `models.py:535`), NOT what lands on `rpe.chunk_*_tags`.
  Only `count` is persisted per chunk.
- **Object-not-list + key = tag_code: DB-RATIFIED, firm, safe to depend on.**
- **Load-bearing part = key existence.** The live arm matches via the JSONB `?`
  operator (`chunk_d_tags ? :tag_code`, `app/services/corpus_search.py:1638`) and
  defaults missing to `{}` (`... or {}`, :1691/:2128) — it asks *"does this chunk
  carry tag X?"*, not the value.
- **Three no-tags states** — SQL `NULL`, JSON `null` (47,626 rows), key-absent — all
  deserialize to `{}` via `... or {}` and are false under `?`. Uniform.
- **tag-IDF / selectivity lever — scope corrected:** the lever is **pool-size IDF**
  (corpus-wide *row counts* per tag, computed from the index — fully available,
  independent of the per-chunk value). What is **not** available is per-chunk match
  *strength* (`avg_weight`) — that richness isn't persisted on the chunk. Inverse-
  pool-size weighting stands; per-chunk-strength weighting does not. (I over-promised
  the `{count, lines_total, avg_weight}` per-chunk value to Retriever — corrected.)
- **Perf flag (→ Maintaining / Data & DB):** no GIN index on `rpe.chunk_*_tags`
  across 1.94M rows — needed before the `?`-operator tag arm goes live at scale
  (there IS a GIN on `document_tags` @ HEAD 9fe495f, but not on the published table).

## 4. Curation's write guarantees (producer side — proposed)
1. **Atomic per-document replace** — publish DELETEs all rows for `document_id`,
   then INSERTs the fresh set. A republish fully supersedes; no partial merges.
2. **`content_sha`** stamped on every row (integrity + dedup).
3. **`corpus_state.corpus_version += 1`** on every publish (corpus version bump).
4. **`embedding_vec`** dual-written post-flush (batched). **Best-effort**: a row
   whose vec write fails is kept with NULL vec and sits out of retrieval until the
   next publish. → guarantee is "*retrievable rows have a non-NULL 1536-d vec*",
   not "*every row has a vec*".
5. **Integrity check** post-write: row-count match + 5-row spot-check
   (exists, content_sha matches, embedding non-null). Surfaced as `verification_passed`.
6. **Tags** are best-effort (see §3): present when the position join hits, else NULL.

## 5. OPEN — Retriever to specify (consumer side)
> **⛔ CONSUMER-SIDE BINDS AT RETRIEVER UN-PARK.** Ananth ruled the Retriever leg
> (pool design included) on **full hold** until P1 proves out + his focused guidance
> (via Tech Review, 2026-07-22). Retriever will NOT ratify binding §5 invariants while
> parked. Producer side (§1–§4, §3a) stands and is final-ready; §5 stays open and binds
> when Retriever un-parks. Retriever's non-binding directional read is recorded in §5a.
1. **Exact columns the pool reads.** Confirm the live set: `embedding_vec`,
   `search_vec`, `text`, `chunk_{d,p,j}_tags`, and which doc-metadata fields.
2. **Typed row/DTO** the pool wants (the shape fillers consume) — so we can name
   the seam type, not just the table.
3. **Hard invariants the pool depends on** — e.g. `embedding_vec` NOT NULL,
   `content_sha` uniqueness, both `source_type`s present, tag JSONB shape.
4. **Fields needed but NOT produced today** → becomes Curation backlog.
5. **Freshness / versioning** — how the pool detects a republish; is
   `corpus_version` the signal, and at what granularity (corpus vs document)?
6. **Read topology** — pool reads this table directly, or a view/mart? (matters
   for the "ONE shared timed pool, every segment timed" refactor.)

### 5a. Retriever non-binding read (2026-07-22) — subject to Ananth's go + TECH gate
Retriever affirmed seam facts and split §5 into what spec/code already fix vs what
is genuine pool-design (which it is holding):

**Fixed by spec/code (Retriever affirms directionally, not a design choice):**
- Columns the pool needs: `embedding_vec`, `search_vec`, `text`/`summary`,
  `chunk_{d,p,j}_tags`, **+ payer-authority doc-metadata** (`document_payer`,
  `document_authority_level`, `document_effective_date`,
  `document_termination_date`, `document_state`, `document_program`,
  `document_status`), `content_sha` + `document_id` for identity/dedup. Spec
  mandate: *"vector + keyword + payer-authority feed ONE pool, single embed pass."*
- Invariant (follows from producer guarantee #4 + spec exclusion): retrievable rows
  have non-NULL `embedding_vec`.
- Keep the empty-string-not-NULL convention on doc-metadata (lets fillers skip
  null-checks).
- Tag JSONB shape: **pinned by Curation, §3a** (Retriever's explicit ask; safe to
  depend on regardless of the hold).

**Held (pool-design → Retriever defers to Ananth's go):** the named seam DTO type;
full ratified invariant set; freshness GRAIN (Retriever leans *document* for
incremental invalidation — leg-build call); read topology (direct vs view/mart);
any field-not-produced-today.

## 6. Next
Retriever fills §5 → we converge → **Technical Review gates** the boundary →
report back to Tech Review + Master RAG. Then align column-list with Data & DB
(schema authority) and, where relevant, the Lexicon module (tag production).
