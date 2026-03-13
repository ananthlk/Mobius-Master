# Reranker Planned Changes

~~Tabs from clarification session.~~ **Implemented** — re-run dev retrieval report to compare.

---

## 1. decay_from_top → Post-rerank cutoff

**Current:** `decay_from_top` uses retrieval score (sigmoid BM25 / vector sim) as input to reranker.

**Change:** Remove from reranker signals. Add post-rerank step: compute `decay_from_rerank_top = rerank_score[i] / rerank_score[top]`. Use configurable threshold (e.g. 0.6) to decide how many chunks to send. Dynamically determines "send top N" per query.

---

## 2. source_type_hierarchy → authority_level

**Current:** Uses `source_type` (policy, section, chunk, hierarchical, fact).

**Change:** Replace with `authority_level` signal using `document_authority_level`:

| authority_level          | Weight (example) |
|--------------------------|------------------|
| contract_source_of_truth | 1.0              |
| operational_suggested    | 0.6–0.7          |
| fyi_not_citable          | 0.3–0.4          |
| unknown / empty          | 0.0              |

Chunks need `document_authority_level` (from metadata). Add to BM25/vector chunk payload if missing.

---

## 3. length_completeness → length + homogeneity

**Length:**
- Floor-only: below min_chars (e.g. 50) → 0, else 1. No penalty for long chunks.
- Intent: wean out small fragments.

**Homogeneity:**
- J/D tag pollution: chunk with many extra J/D tags (pharmacy + daycare + prior_auth + …) = polluted = lower score.
- Metric options: `matched / total_doc_tags` or `1 / (1 + num_extra)`.
- Intent: single-topic chunks rank higher than multi-topic.

---

## 4. tag_match → Direct + Context buckets

**Direct (chunk-level):**
- Source: line-level tags for this chunk.
- Signals: completeness (coverage), intensity (match strength), homogeneity (J/D pollution).
- Full weight.

**Context (propagation):**
- Source: paragraph-level tags (higher weight) + document-level tags (lower weight).
- Role: incremental boost when line missed but neighbors (paragraph, doc) have the tags.
- Lighter weight than direct. Paragraph > document.

---

## Implementation order

1. authority_level signal (replace source_type_hierarchy)
2. tag_match refactor (direct + context, add homogeneity)
3. length (floor-only) + homogeneity as separate signal
4. decay_from_top removal + post-rerank cutoff
5. Re-run dev retrieval report, compare before/after
