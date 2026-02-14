# BM25 “Atomic Candidate” vs Hierarchical Vector Retrieval (Pre‑Rerank) — Sunshine Manual

**Status**: Retrieval-only evaluation (no reranking, no LLM answering).  
**Purpose**: Measure whether the *correct evidence* is retrieved in the top results, and quantify “hallucination risk” as **out‑of‑manual but confidently answerable**.

---

## 1) Executive summary

We compared two retrieval approaches on the **Sunshine Provider Manual**:

1) **BM25 Atomic Candidate Retrieval**  
   - Index unit: **sentence** (“atomic”) extracted from hierarchical chunk text  
   - Returns: top‑K sentences, each mapped back to its **parent hierarchical paragraph** (`published_rag_metadata.id`)
   - Adds: a **sigmoid-normalized** score \([0,1]\) used as a pre‑answer “confidence” proxy.

2) **Hierarchical Vector Retrieval (Vertex Vector Search)**  
   - Index unit: **hierarchical paragraph chunk**
   - Returns: top‑K paragraph chunks with cosine-distance-derived similarity.

**Key finding (before reranking):** BM25 atomics retrieve the correct evidence substantially more often in the **top 1–3** results than hierarchical vector retrieval on the same manual.

On questions with gold evidence labels (43 in-manual questions):

- **Hit@1**
  - BM25: **0.791** (34/43)
  - Hierarchical: **0.512** (22/43)
  - Δ = **+27.9 percentage points** (relative ≈ **+55%** vs hierarchical)

- **Hit@3** (captures “top 2–3 answers”)
  - BM25: **0.860** (37/43)
  - Hierarchical: **0.628** (27/43)
  - Δ = **+23.2 percentage points** (relative ≈ **+37%** vs hierarchical)

**Hallucination-risk proxy (out-of-manual probes):**

- Out-of-manual questions: 7  
- “Would answer” false positives (thresholded):
  - BM25: **0/7**
  - Hierarchical: **4/7**

This suggests BM25 atomics can improve early‑rank evidence recall and may reduce spurious “confident” retrieval events (depending on calibration thresholds).

---

## 2) What exactly was measured (and what wasn’t)

### Measured

- **Evidence retrieval accuracy**: does the correct evidence paragraph appear in the top results?
  - Hit@1, Hit@3, Miss@10
- **Candidate confidence** (proxy): a thresholded “would answer” flag per method
  - Used only to estimate hallucination risk **before** an LLM is introduced.

### Not measured

- **Answer correctness** (no LLM answering was run)
- **Reranking quality** (explicitly excluded; this is pre‑rerank)
- **Cross-document generalization** (this run is one manual; see Section 7 for validation plan)

---

## 3) Dataset

### Corpus

- Source table: **Chat Postgres** `published_rag_metadata`
- Filter token: `document_authority_level = lexicon_qa_sunshine_manual_v1`
- `source_type = hierarchical`
- Filename: `Sunshine Provider Manual.pdf`
- Rows (hierarchical paragraphs): **528**

### Question set

We used a **50-question** set `questions_generated.yaml` generated directly from the manual text:

- **In-manual**: 43 questions with gold evidence paragraph IDs
- **Out-of-manual**: 7 probe questions (gold expects abstention, i.e., `expect_in_manual=false`)

Gold format per question:

- `gold.parent_metadata_ids`: the “correct” paragraph chunk(s) (`published_rag_metadata.id`)
- For factual items: `gold.answer_contains` or `gold.answer_regex` (stable snippet)
- For canonical items: `gold.crux_contains` (2–3 lines)

---

## 4) Methods

### 4.1 BM25 atomic candidate retrieval

1) Build sentence corpus by splitting each hierarchical paragraph into sentences.
2) Retrieve top‑K sentences using BM25 (`rank-bm25`).
3) Map each sentence back to its parent paragraph ID (`parent_metadata_id`).
4) Normalize BM25 scores via sigmoid to obtain \([0,1]\) “candidate confidence”.

**Why sigmoid normalization?**  
To allow stable thresholding across queries (for abstain/answer gating), without yet introducing reranking.

### 4.2 Hierarchical vector retrieval

1) Embed user query using the same embedding model used for the index (`gemini-embedding-001`).
2) Query Vertex Vector Search endpoint, filtered by `document_authority_level`.
3) Restrict to `source_type=hierarchical` for the baseline.
4) Convert cosine distance to similarity: \( similarity = 1 - distance/2 \).

---

## 5) Metrics and decision rules

### Evidence hit metrics (primary)

Let gold paragraph IDs for question \(q\) be \(G_q\). Let retrieved paragraph IDs be \(R_q\) (ranked).

- **Hit@k**: \( \exists i \le k \; : \; R_q[i] \in G_q \)
- We report Hit@1 and Hit@3 (and show top‑10 in the report).

### Hallucination-risk proxy (secondary)

We define a “would answer” gate per method:

- **BM25 would answer**: `max_norm_score >= 0.65`
- **Hier would answer**: `top1_similarity >= 0.88`

Then for out-of-manual questions (`expect_in_manual=false`), any “would answer” is counted as a **false positive**.

> These thresholds are tunable calibration knobs; they’re not inherent properties of BM25 or vectors.

---

## 6) Results (this run)

Comparison run outputs:

- Per-question report:  
  `mobius-qa/retrieval-eval/reports/compare-bm25-eval-20260210-154340-vs-retrieval-eval-20260210-154428/report.md`
- Aggregate summary:  
  `mobius-qa/retrieval-eval/reports/compare-bm25-eval-20260210-154340-vs-retrieval-eval-20260210-154428/summary.md`

Headline numbers (questions_with_gold = 43):

- **BM25 Hit@1**: 34/43 = **0.791**
- **Hier Hit@1**: 22/43 = **0.512**
- **BM25 Hit@3**: 37/43 = **0.860**
- **Hier Hit@3**: 27/43 = **0.628**

Hallucination-risk proxy (out-of-manual = 7):

- **BM25 false positives**: **0/7**
- **Hier false positives**: **4/7**

---

## 7) How to validate elsewhere (recommended protocol)

To validate these findings on another document (or a new revision of the Sunshine manual):

1) **Ingest + publish** the document to the same schema (hierarchical chunks published to `published_rag_metadata` + Vertex).
2) Set a unique `document_authority_level` token to isolate it.
3) Generate labeled questions from that manual:
   - `generate_questions_from_manual.py` (quick bootstrap), **or**
   - replace with a hand-authored 50-question set with gold labels (best for trust).
4) Run:
   - BM25 eval: `bm25_eval.py`
   - Hierarchical eval: `retrieval_eval.py` (hier_only mode)
   - Compare: `compare_bm25_vs_hier.py`
5) Confirm:
   - Hit@1, Hit@3 improvements persist
   - Out-of-manual false positives remain low

If the goal is productionization, also do:

- **Threshold sweeps** (BM25 + hierarchical) to pick an operating point minimizing hallucination risk.
- Add a **reranker** on BM25 candidates and re-run the same report to quantify incremental gain.

---

## 8) Reproduction (sanitized commands)

Prereqs:

- Python venv with deps (`mobius-qa/retrieval-eval/requirements.txt`)
- Environment variables:
  - `CHAT_DATABASE_URL` pointing to the Chat Postgres that contains `published_rag_metadata`
  - Vertex vars for hierarchical eval:
    - `VERTEX_PROJECT`, `VERTEX_REGION`
    - `VERTEX_INDEX_ENDPOINT_ID`, `VERTEX_DEPLOYED_INDEX_ID`

Commands:

```bash
cd mobius-qa/retrieval-eval

# 1) Generate labeled 50 questions from manual
python generate_questions_from_manual.py --config config.yaml --out questions_generated.yaml --n 50 --n_out_of_manual 7 --n_canonical 8

# 2) BM25 atomic candidate eval (top-20 candidates; sigmoid normalization)
python bm25_eval.py --config config.yaml --questions questions_generated.yaml --top-k 20 --abstain-threshold 0.65 --sigmoid-mode global_max_raw

# 3) Hierarchical vector retrieval eval (top-10; hier_only mode is in config.yaml)
python retrieval_eval.py --config config.yaml --questions questions_generated.yaml

# 4) Side-by-side report
python compare_bm25_vs_hier.py \
  --questions questions_generated.yaml \
  --bm25-run-dir reports/bm25-eval-<timestamp> \
  --hier-run-dir reports/retrieval-eval-<timestamp> \
  --k 10 --hit-k 3
```

---

## 9) Caveats / interpretation notes

1) **This is pre‑rerank**: we measured candidate retrieval, not final answer correctness.
2) **Gold labels**: the “generated” question set is derived from manual text, which makes it easier than purely human-authored queries. Use hand-labeled questions for high-stakes validation.
3) **Comparability**: BM25 retrieves sentences and maps them to parent paragraphs; hierarchical retrieval retrieves paragraphs directly. We evaluate on the common denominator: **parent paragraph ID**.
4) **Calibration matters**: “Would answer” thresholds drive the hallucination-risk counts; they should be tuned per domain/index.

