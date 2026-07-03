# Lexicon

> The controlled tagging vocabulary and pipeline that classifies corpus content into p/d/j tags, driving retrieval filtering and query strategy selection.

## Purpose

The lexicon is Mobius's curated, versioned vocabulary of policy concepts. Every entry is a hand-approved tag of one of three **kinds** — `p` (payer / prescriptive / process), `d` (domain / descriptive), `j` (jurisdiction) — with a `code` and a `spec` (JSON) holding the phrases and aliases that identify it. During ingestion, Path B matches these phrases against policy text and stamps documents with `p_tags` / `d_tags` / `j_tags`. At query time the same vocabulary is matched against the user's question to expand the search query and to classify how the retrieval agent should behave.

It matters because tags are the join key between "what a document is about" and "what a query is asking for." Good tag coverage lets the retrieval agent filter the corpus to the right documents and pick a confident, precise strategy; poor coverage forces it into broad, low-precision fallbacks. The lexicon is therefore both a **filtering vocabulary** (document_tags join) and a **routing signal** (tag coverage → query classification).

## Audience

- **Primary:** developers and RAG engineers working on ingestion (Path B), retrieval (`corpus_search*`), or the candidate pipeline.
- **Secondary:** curators who review and approve candidate phrases into the vocabulary via the lexicon-maintenance service.

## Capabilities

- **Three tag kinds** — `p` (payer/prescriptive/process), `d` (domain), `j` (jurisdiction). Stored as rows in `policy_lexicon_entries (kind, code, parent_code, spec, active)`.
- **A 3-stage candidate pipeline** that cleans newly-extracted phrases before they reach a human: catalog propagation → deterministic junk rules → bounded LLM triage with a confidence gate.
- **Human review / approval** — genuinely-new phrases are queued for human decision; taxonomy *additions* (new tags / aliases) never auto-apply. Approval writes to `policy_lexicon_entries` via `approve_phrase_to_db`.
- **Versioning** — a single-row `policy_lexicon_meta` holds `revision` and `lexicon_version`; `bump_revision()` increments the revision.
- **Retag / staleness tracking** — each document's `document_tags.lexicon_revision` is compared against the current meta revision to find stale / untagged documents.
- **Query-time expansion** — the active lexicon is matched against the raw query to produce OR-joined expansion phrases for BM25 and to compute tag coverage for query classification.

## How it works (pipeline)

### Ingestion & tag application (Path B)

`mobius-rag/app/worker/path_b.py` runs during document chunking (no LLM):

1. **Per paragraph** (`process_paragraph`): builds `PolicyParagraph` + `PolicyLines`, then `apply_lexicon_to_lines` regex-matches the pre-built `phrase_map` (from `get_phrase_to_tag_map(lexicon_snapshot)`) against each line, writing `p_tags` / `d_tags` per line.
2. **Line → paragraph aggregation** (`aggregate_line_tags_to_paragraph`).
3. **Finalise** (`finalise`): aggregates paragraph tags → `document_tags` (`aggregate_paragraph_tags_to_document`), then **stamps** `document_tags.lexicon_revision` and `tagged_at` from `lexicon_snapshot.meta["revision"]`.
4. **Candidate extraction** (`extract_candidates_for_document`) writes new proposed phrases to `policy_lexicon_candidates`, then fires the cleanup pipeline via HTTP.

### The 3-stage candidate cleanup pipeline

Entry point: `POST /policy/candidates/process-document` in `mobius-qa/lexicon-maintenance/app/main.py`, calling `_process_document(document_id, conf_threshold, llm_chunks)` (~lines 2832–2977). Path B's `_trigger_lexicon_cleanup` calls it twice: a synchronous fast pass (`llm_chunks=0, sync=True`) for real counts, then a fire-and-forget LLM pass (`llm_chunks=2`).

- **Stage 1 — Catalog propagation (deterministic, 0 LLM).** Looks up this document's distinct proposed phrases against `policy_lexicon_candidate_catalog` (indexed `normalized_key`), and applies prior durable `approved` / `rejected` decisions. Reviewer stamped as `catalog`.
- **Stage 2 — Deterministic junk rules.** Runs pool-independent per-phrase rules on the residue and rejects matches: `all_stopword`, `url_email`, `struct_noise`, `mostly_punct`, `coded_single`, `common_word_single`, `foreign_lang`, `numeric_citation`, `numeric_measure`, `generic_variant`, `stopword`, `overlong` (>8 words). Rejections are also upserted back into the catalog so the decision is durable. Reviewer stamped as `deterministic`.
- **Stage 3 — LLM triage (bounded, confidence-gated).** Only the genuinely-new residue reaches the LLM. Calls `llm_triage_candidates` up to `llm_chunks` times (25 phrases/chunk). Each candidate gets an operation: `reject_candidate`, `add_alias`, or `create_tag`. **Confidence gate defaults to 0.75** (`confidence_threshold`): a verdict only auto-applies when confidence ≥ threshold; below it, the verdict is parked as a recommendation on the still-`proposed` row for human review. Per the code, **taxonomy additions (`create_tag` / `add_alias`) never auto-apply regardless of confidence** — they stay human-governed. `min_occ` defaults to 2 (drops occurrence-1 noise; override with `min_occ=1`).

### Vocabulary storage & revisions

`mobius-rag/app/services/policy_lexicon_repo.py`:

- `load_lexicon_snapshot_db(db)` — reads the newest `policy_lexicon_meta` row + all `active` `policy_lexicon_entries`, returns `.version`, `.meta` (incl. `revision`), `.p_tags`, `.d_tags`, `.j_tags` (nested dicts keyed by code).
- `approve_phrase_to_db(db, kind, normalized, target_code, tag_spec)` — upserts into `policy_lexicon_entries` on conflict `(kind, code)`; defaults `spec.phrases` to `[normalized]`.
- `bump_revision(db)` — `UPDATE policy_lexicon_meta SET revision = revision + 1` and returns the new revision.
- `update_tag_in_db(...)` — edits a tag's `spec` / `active`.

### Storage schema (migrations under `mobius-rag/app/migrations/`)

- `policy_lexicon_meta` — single row: `revision BIGINT`, `lexicon_version`, `lexicon_meta JSONB` (`add_policy_lexicon_tables.py`).
- `policy_lexicon_entries` — `kind`, `code`, `parent_code`, `spec JSONB`, `active`, `UNIQUE(kind, code)` (`add_policy_lexicon_tables.py`).
- `policy_lexicon_candidates` — proposed phrases; extended with `occurrences` (`add_policy_lexicon_candidate_occurrences.py`) and LLM columns `llm_verdict`, `llm_confidence`, `llm_reason`, `llm_suggested_parent/code/kind` (`add_policy_lexicon_candidate_llm_columns.py`). `decision_rule` is added at runtime by `_process_document`.
- `policy_lexicon_candidate_catalog` — durable per-phrase decisions; `normalized_key`, `proposed_tag_key`, `UNIQUE(candidate_type, normalized_key, proposed_tag_key)` (`add_policy_lexicon_candidate_catalog.py`).
- `document_tags` — gains `lexicon_revision BIGINT` + `tagged_at TIMESTAMP` (`add_document_tags_lexicon_revision.py`).

## Navigation & Access

### Endpoints

**Candidate pipeline (`mobius-qa/lexicon-maintenance`):**
- `POST /policy/candidates/process-document` — run the 3-stage cleanup for one document. Body: `document_id` (required), `llm_chunks` (default 1, max 4), `confidence_threshold` (default 0.75), `sync` (default false → runs in background). Poll `GET /policy/candidates/process-document/status?document_id=...`.
- `POST /policy/candidates/ensure-indexes` — one-shot to build `idx_plc_docid` / `idx_plc_normkey` required by the per-document pipeline.
- `llm_triage_candidates` (invoked internally / by the UI) — one-chunk-per-call LLM triage.

**Retag / staleness (`mobius-rag/app/main.py`):**
- `POST /documents/retag` — queues Path B (generator `B`) rechunk jobs to re-apply the latest lexicon. Accepts `document_ids` or retags all `completed` documents; skips docs with a pending/processing Path B job.
- `GET /documents/retag/status` — compares each `document_tags.lexicon_revision` against the current `policy_lexicon_meta.revision`, returning `stale` / `current` / `untagged` buckets and counts.
- There is also an in-place retag path (`/admin/retag-in-place/*`) that UPDATEs only the JSONB tag columns by PK (avoids delete+reinsert), noted in `main.py` ~line 2984.

### Retag vs. republish

Tag changes are **live**: retrieval reads `document_tags` via a `LEFT JOIN` at query time, so approving/editing a tag takes effect immediately for filtering, without re-embedding. A **retag** (rerunning Path B or the in-place path) is only needed to recompute the *stamped* tag columns and refresh `lexicon_revision`. A **republish** (re-embedding / re-extracting) is only required when the document's *text or embeddings* change — not for tag edits.

### Curator UI

`mobius-qa/lexicon-maintenance/frontend-v2/` is a Vite/React app (`<title>Mobius QA — Lexicon Maintenance</title>`) served alongside the FastAPI service. It is the curator surface for reviewing candidates and approving them into the vocabulary. [UNVERIFIED: exact screens/workflows in the UI were not inspected at the component level.]

## Integrations

- **Retrieval filtering** — `mobius-rag/app/services/corpus_search.py` builds tag filters by `LEFT JOIN document_tags dt ON dt.document_id = rag_published_embeddings.document_id`. `j` tags match inlined `document_state/payer/program` columns *or* `dt.j_tags` (JSONB `jsonb_exists`); `d`/`p` tags match `dt.d_tags` / `dt.p_tags`. Because this is a live join, tag edits filter differently on the very next query.
- **Query expansion** — `corpus_search_lexicon.py::expand_query_via_lexicon` matches the raw query against an in-process snapshot of `active` entries (5-minute TTL cache; `invalidate_cache()` forces reload). Matching is word-boundary aligned; single-word phrases >4 chars are rejected as too generic (short acronyms like NPI/DME/HCPCS pass). Returns `expansion_phrases` (OR-joined into the BM25 tsquery) and `matched_codes` split into domain/jurisdiction/process tags. Capped at 12 entries/query. An env-gated (`LEXICON_PRECISION_CSV`) experimental filter can prune noisy phrases.
- **Strategy selection** — `corpus_search_agent.py::classify_query` calls `expand_query_via_lexicon`, then computes **coverage** = (tagged + literal-anchor tokens) / meaningful tokens. Coverage + tag matches classify the query: `PRECISION_DOMINANT` (any literal anchor), `CONCEPTUAL` (coverage ≥ 0.5 and tag matches), `MIXED` (coverage ≥ 0.2 and tag matches), else `VAGUE`. This `QueryProfile` drives the adaptive strategy order and the Fail-Fast gate — i.e., higher lexicon coverage → more confident, more precise strategies.
- **Republishing / eval loop** — improving the lexicon (approve phrases → `bump_revision`) raises tag coverage, which the eval loop measures as a lift in routing/answer quality; `retag/status` surfaces which documents still need re-tagging after a revision bump.

## Doc-readiness notes

- **Primary audience tag:** dev
- **Solid (grounded in code):** the 3-stage pipeline and its rules/gate; `policy_lexicon_repo` functions; the schema/migrations; retag endpoints and stale/untagged buckets; the live `document_tags` join; query expansion + `classify_query` coverage logic; retag-vs-republish distinction.
- **Corrections vs. the brief:** the `p` kind is used in code as payer/prescriptive **and process** (`process_tags` in `LexiconExpansion`). "231 tags" appears only as a docstring example in `corpus_search_lexicon.py`; the live count is data-dependent, not a code constant. `mobius-config/lexicons/` **exists but is empty** and is referenced nowhere in `mobius-rag` or `lexicon-maintenance` code — config lexicons are not wired.
- **Ambiguous / gaps a human must fill:**
  - Exact curator UI workflow in `frontend-v2` (not inspected).
  - Whether `bump_revision` is called automatically on approval or is a manual/curator step [UNVERIFIED: no caller of `bump_revision` traced in this pass].
  - Concrete deployment URLs / auth for the lexicon-maintenance service (`LEXICON_MAINTENANCE_URL`, `ADMIN_API_KEY`) are env-driven and not documented here.

## Not yet available (planned)

- **Precision-filtered expansion** (`corpus_search_lexicon.py`) is explicitly experimental and env-gated (`LEXICON_PRECISION_CSV`); the code comments it as the prototype for an eventual `query_rewrite` JSONB column. When the env var is unset, behaviour is unchanged.
- **`mobius-config/lexicons/`** is a placeholder directory with no contents and no code references — config-file-based lexicons are not implemented.
- **YAML export** (`export_yaml_from_db`) exists but is marked optional and writes to a local `data/policy_lexicon.yaml`; not part of the live path.
