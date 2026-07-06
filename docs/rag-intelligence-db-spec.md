# RAG Intelligence DB — Module Spec v0.1

Nightly batch indexing of prior conversation threads. Semantic retrieval of prior answers. Standalone module.

---

## Purpose

A nightly batch job reads completed conversation threads, extracts resolved Q&A exchanges, embeds them, and stores them in a vector DB. At query time a pre-React lookup checks this store — a high-similarity match returns the prior answer directly, bypassing LLM rounds and tool calls. Miss or low confidence falls through to the standard pipeline unchanged.

---

## Scope

**In scope**
- Nightly ingestion of threads
- Per-org scoped vector store
- Quality gate on population
- Similarity-based retrieval API
- TTL / staleness rules
- Bypass threshold configuration

**Out of scope**
- Chat orchestrator integration (separate spec)
- Real-time / per-turn writes
- User feedback loop
- A/B testing framework
- Answer correction / override UI

**Consumers**

Initially: the chat orchestrator (pre-React stage) via `POST /intelligence/match`. Later: any pipeline that benefits from prior-answer context (agentic mode, report generation). The module is read-only at query time. Writes happen only from the nightly batch job.

---

## Data Model

### Table: `intelligence_entries`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | uuid | PK | gen_random_uuid() |
| `org_slug` | text | NOT NULL, IDX | Isolation boundary — every query scoped here |
| `thread_id` | uuid | NOT NULL, IDX | Source thread; FK to chat.threads |
| `turn_index` | int | NOT NULL | Which turn in thread this exchange covers |
| `question_text` | text | NOT NULL | Pronoun-resolved canonical question text |
| `question_vec` | vector(768) | NOT NULL, HNSW | Embedding of question_text; ANN search target |
| `answer_text` | text | NOT NULL | Final integrator output (not raw tool results) |
| `sources` | jsonb | | Source citations from the original turn |
| `jurisdiction` | text | IDX | FL, GA, etc. — optional scope narrowing |
| `payer` | text | IDX | Payer slug if thread was payer-scoped |
| `quality_score` | float | NOT NULL | 0.0–1.0; computed by batch job quality gate |
| `tool_path` | text[] | | Tools fired to produce this answer (audit trail) |
| `created_at` | timestamptz | NOT NULL | When this entry was indexed |
| `expires_at` | timestamptz | IDX | NULL = no expiry; set by content-type rules |
| `source_doc_ids` | uuid[] | | RAG document IDs cited; used for invalidation on doc update |

One row per resolvable Q&A exchange extracted from a thread. A single thread may produce 1–N rows if it covers multiple distinct questions. Rows from the same thread share `thread_id` and incremental `turn_index`.

### Indexes

| Index | Type | Purpose |
|-------|------|---------|
| `ix_intel_org_vec` | HNSW (question_vec) WHERE org_slug = :org | Primary ANN search path |
| `ix_intel_org_jur` | btree (org_slug, jurisdiction) | Scope narrowing before vector search |
| `ix_intel_expires` | btree (expires_at) partial WHERE expires_at IS NOT NULL | Cleanup cron |
| `ix_intel_thread` | btree (thread_id) | Invalidation: delete all entries from a thread |
| `ix_intel_src_docs` | GIN (source_doc_ids) | Invalidation: find entries that cited an updated document |

---

## Ingestion Pipeline

Runs nightly as a batch job. Steps are sequential per thread; threads are processed in parallel up to batch size.

### Step 1 — Select eligible threads

Query chat DB for threads completed since last run and not already indexed.

- Completed = final integrator turn exists, no open tool calls
- Filter: `last_updated_at > last_run_at` (stored in job metadata)
- Exclude: threads flagged `do_not_index`, threads with no successful turns
- Batch size: configurable, default 500 threads per run

### Step 2 — Extract Q&A exchanges

For each thread, identify discrete question → answer pairs.

- Unit = one user turn + its corresponding integrator answer turn
- Apply pronoun resolution: expand "it", "that", "the previous one" using prior thread context before embedding
- Strip thinking/tool intermediate turns — store only final integrator output
- If thread has correction turns (user says "that's wrong"), mark prior exchange as low quality

### Step 3 — Quality gate

Score each exchange. Only score ≥ 0.6 proceeds to embedding.

| Signal | Score |
|--------|-------|
| Answer is not a refusal and not a hedge | +0.4 |
| Answer cites at least one RAG corpus source (not web-only) | +0.3 |
| User did not re-ask the same question in a subsequent turn | +0.2 |
| Turn count from question to answer was ≤ 2 (confident, no loops) | +0.1 |
| A correction turn follows this exchange in the thread | −0.4 |
| Answer used web search only (no corpus sources) | −0.2 |

Score clamped to [0.0, 1.0]; stored as `quality_score`.

### Step 4 — Embed question text

Generate embedding for the resolved question only (not the answer).

- Model: same embedding model used by RAG corpus (consistency = comparable similarity scores at retrieval time)
- Input: pronoun-resolved `question_text` from step 2
- Batch: embed in groups of 64 to minimise API calls
- On failure: log and skip entry, do not block rest of batch

### Step 5 — Deduplication

Before writing, check if a near-identical entry already exists for this org.

- ANN search: find existing entry with cosine similarity > 0.97 AND same `org_slug`
- If found AND new `quality_score` > existing: replace (upsert)
- If found AND new `quality_score` ≤ existing: skip
- If not found: insert new row

### Step 6 — Write to `intelligence_entries`

Persist entry with metadata, TTL, and source document references.

- Set `expires_at` based on content-type rules (see Freshness Rules below)
- Populate `source_doc_ids` from the turn's sources array
- Record `tool_path` (which tools were called to produce the answer)

### Step 7 — Invalidation sweep

After writes, run two cleanup passes.

- **TTL cleanup:** `DELETE WHERE expires_at < now()`
- **Doc invalidation:** for each RAG document updated/re-indexed since last run, `DELETE FROM intelligence_entries WHERE source_doc_ids @> ARRAY[:doc_id]`

---

## Query API

### `POST /intelligence/match`

Check for a prior answer that matches an incoming question.

**Request**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | Pronoun-resolved incoming question text |
| `org_slug` | string | yes | Scopes ANN search — required for isolation |
| `k` | int | no | Max candidates to return (default 3) |
| `jurisdiction` | string | no | If set, restrict search to matching jurisdiction |
| `payer` | string | no | If set, prefer entries scoped to this payer |
| `min_quality` | float | no | Min quality_score to include (default 0.6) |
| `freshness_override` | bool | no | If true, always return recommendation=miss regardless of similarity |

**Response**

```json
{
  "matches": [
    {
      "id": "uuid",
      "similarity": 0.965,
      "quality_score": 0.9,
      "question_text": "...",
      "answer_text": "...",
      "sources": [...],
      "jurisdiction": "FL",
      "payer": "sunshine-health",
      "created_at": "2026-06-28T02:00:00Z",
      "expires_at": null
    }
  ],
  "top_similarity": 0.965,
  "recommendation": "bypass" | "inject" | "miss"
}
```

**`recommendation` logic**

| Value | Condition | Caller behaviour |
|-------|-----------|-----------------|
| `bypass` | top_similarity ≥ 0.94 AND quality_score ≥ 0.7 | Return prior answer directly; skip React loop |
| `inject` | top_similarity ≥ 0.86 | Pass matches as context into React loop; still runs but primed |
| `miss` | Below both thresholds | Caller ignores matches; full pipeline as normal |

Thresholds are per-org configurable (see Bypass Rules below).

---

### `POST /intelligence/invalidate`

Called by the RAG document pipeline when a document is re-indexed or deleted. Removes all intelligence entries that cited that document.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `document_id` | uuid | yes | RAG document that was updated |
| `org_slug` | string | no | If set, scope deletion to this org only |

---

### `GET /intelligence/stats`

Returns entry count by org, average quality score, last run time, and estimated hit rate based on similarity distribution. Admin / observability only.

---

## Quality Rules

**Never index refusals or hedges**
Answers containing "I'm not sure", "I cannot", "I don't have information" are excluded regardless of other scores.

**Never index web-only answers**
Answers that cite only web search results (no RAG corpus sources) are excluded. Web content goes stale too fast and bypassing to it is high risk.

**Down-score corrected exchanges**
If the user sent a correction message after an answer turn ("that's wrong", "actually it's X"), the prior answer's `quality_score` is reduced by 0.4. If score falls below 0.6 it is not indexed.

**Prefer corpus-sourced, short-path answers**
Answers that cite RAG corpus sources and required ≤ 2 React rounds get the highest quality scores and are most likely to be indexed and matched.

---

## Freshness / TTL Rules

| Content type | Detection | `expires_at` |
|---|---|---|
| Policy / regulatory | `tool_path` includes `search_corpus` AND sources cite policy documents | 90 days |
| Provider / NPI lookups | `tool_path` includes `healthcare_query` | 30 days |
| General knowledge / stable | Definitional questions, workflow explanations, stable process descriptions | NULL (no expiry) |

Source document update triggers immediate invalidation regardless of `expires_at`. When a RAG document is re-indexed, all `intelligence_entries` with that `document_id` in `source_doc_ids` are deleted. Caller uses `/intelligence/invalidate`.

---

## Bypass / Threshold Configuration

**Thresholds are per-org configurable**
Default bypass = 0.94, inject = 0.86. An org can raise bypass to 0.97 for conservative behaviour or lower inject to 0.80 for more aggressive context injection. Set in org config, not hardcoded.

**Bypass rate cap for A/B testing**
Optional `bypass_rate` (0.0–1.0) per org. Set to 0.8 to route 20% of bypass-eligible queries through the full pipeline for quality comparison. Default 1.0 (always bypass when eligible).

**Freshness override via query flag**
If the incoming question contains temporal markers ("as of today", "current", "latest") the caller should set `freshness_override=true` in the `/intelligence/match` request, causing the endpoint to return `recommendation=miss` regardless of similarity.

---

## Open Decisions for Implementer

- Whether this lives as a new table in mobius-rag's existing Postgres DB or as a separate service
- Exact embedding model (must match whatever RAG corpus uses for similarity scores to be comparable)
- Cron schedule and batch size (start conservative — 500 threads/night — tune based on volume)
- Whether `min_quality` default (0.6) is the right floor after initial data is available
