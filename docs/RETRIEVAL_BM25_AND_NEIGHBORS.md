# Retrieval: BM25 and Paragraph/Neighbor Context

## Summary

- **BM25 is working** in both retrieval paths (RAG API and inline).
- **Paragraph/neighbor expansion** is now **enabled**: the retriever pipeline and chat inline path both expand each retrieved chunk with ±2 sibling paragraphs from the same document when a database URL is available. Chunks include `paragraph_index` so the correct window is fetched.

---

## 1. BM25 — How it works and where it runs

### Where BM25 runs

| Path | When | Code |
|------|------|------|
| **RAG API** | `RAG_API_URL` set, `path=mobius` | `mobius-retriever` `run_rag_pipeline()` → `retrieve_bm25()` → `bm25_search()` |
| **Inline** | No RAG API or API returns empty | `mobius-chat` `retrieve_for_chat()` → `retrieve_bm25()` → `bm25_search()` |

### What BM25 does

- **Corpus:** Paragraphs from `published_rag_metadata` (hierarchical), with optional filters (authority, payer, state, program, document_ids from J/P/D tagger).
- **Scoring:** `rank_bm25.BM25Okapi` on tokenized text. When `include_paragraphs=True` (default):
  - Runs on **full paragraphs** → top-k paragraph matches (`provision_type: "paragraph"`).
  - Builds a **sentence corpus** from those paragraphs and runs BM25 on **sentences** → top-k sentence matches (`provision_type: "sentence"`).
- **Output:** List of chunk dicts with `id`, `text`, `document_id`, `document_name`, `page_number`, `paragraph_index`, `raw_score`, `provision_type` (`"paragraph"` or `"sentence"`).

### RAG API “mobius” path (full pipeline)

1. `retrieve_bm25()` + `vector_search()` → merge + dedupe (with BM25 sigmoid normalization).
2. Rerank (optional JPD/doc/line tags).
3. **Assemble** via `mobius_retriever.assemble.assemble_docs()`: **neighbor expansion** (when `database_url` set), then blend selection, content dedup, confidence labels, optional Google fallback.

So when chat uses the RAG API, BM25 is used upstream and the returned docs are already assembled (with neighbors); chat does not run its own assembly.

---

## 2. BM25 neighbors logic (paragraph_index + context window / dropoff)

We **do** use **paragraph identity and a context dropoff**. Here’s the exact behavior.

### What we key off

- **document_id** — So we only pull neighbors from the same document.
- **paragraph_index** — The **ordinal position** of the paragraph within that document (0, 1, 2, …) in `published_rag_metadata`. This is what we use for “which paragraph” and for the context window; we do **not** use a separate “paragraph id” for the range (we use the row **id** only to exclude the current chunk).
- **chunk id** — The row `id` of the retrieved chunk. We exclude it in the neighbor query so we don’t duplicate the hit.

### Context window (“dropoff”)

- **Window** = number of paragraphs **before and after** the hit. Default **window = 2**.
- For a chunk at **paragraph_index = P** we fetch all rows in `published_rag_metadata` where:
  - `document_id` = same document
  - `paragraph_index` **BETWEEN** `P - window` **AND** `P + window`  
  i.e. **±2 paragraphs** (indexes P−2, P−1, P, P+1, P+2).
- We then exclude the current chunk with `id::text != %s` (chunk_id), so the result is only **sibling paragraphs** (the “neighbors”), not the hit again.
- **Lower bound** is clamped so we don’t go negative: `lo = max(0, (paragraph_index or 0) - window)`.

So: **paragraph_index** defines both “which paragraph” and the **dropoff of context** (±2 paragraphs). If `paragraph_index` is missing we fall back to `0`, so we fetch paragraphs 0–2 (we fixed BM25/vector to supply `paragraph_index` so the correct window is used).

### Where the logic lives

- **`_fetch_sibling_paragraphs(database_url, document_id, paragraph_index, chunk_id, window=2)`**  
  - Runs the SQL above and returns list of neighbor dicts (`is_neighbor: True`).
- **`assemble_with_neighbors(chunks, database_url, window=2)`**  
  - For each chunk with `document_id`, calls `_fetch_sibling_paragraphs(..., para_idx if para_idx is not None else 0, c.get("id"), window=window)` and appends those siblings after the chunk.
- **`assemble_docs(..., expand_neighbors=..., database_url=..., neighbor_window=2)`**  
  - When `expand_neighbors and database_url`, runs `assemble_with_neighbors(..., window=neighbor_window)` before blend/dedup/confidence.

### Current behavior (after fix)

1. **mobius-retriever**
   - BM25 and vector fetch/include `paragraph_index`. Pipeline passes it into `chunks_for_assembly`.
   - `assemble.assemble_docs()` has `expand_neighbors`, `database_url`, and `neighbor_window=2`. When `database_url` is set, assembly calls `assemble_with_neighbors()` before blend/dedup/confidence.
   - `_fetch_sibling_paragraphs` and `assemble_with_neighbors` live in `mobius_retriever.assemble`.

2. **mobius-chat**
   - Inline path: `_raw_to_chat_chunk` preserves `paragraph_index`; `assemble_docs()` is called with `expand_neighbors=True` and `database_url=rag.database_url`.
   - RAG API path: docs are already assembled (with neighbors) by the retriever; chat uses them as returned.

---

## 3. References

- BM25: `mobius-retriever/src/mobius_retriever/bm25_search.py`, `retriever.py` (`retrieve_bm25`).
- Pipeline: `mobius-retriever/src/mobius_retriever/pipeline.py` (`run_rag_pipeline`).
- Retriever backend (RAG API vs inline): `mobius-chat/app/services/retriever_backend.py` (`retrieve_for_chat`, `retrieve_via_rag_api`).
- Neighbor assembly: `mobius-retriever/src/mobius_retriever/assemble.py` and `mobius-chat/app/services/doc_assembly.py` (`_fetch_sibling_paragraphs`, `assemble_with_neighbors`, `assemble_docs`).
- Chat RAG flow: `mobius-chat/app/services/non_patient_rag.py` (`answer_non_patient`).
