## Retrieval Eval (Vertex) — Sunshine Manual Bake-off

This module runs a **retrieval-only** evaluation (no chat) against the **dev Vertex Vector Search** published RAG index.

It compares two retrieval strategies on the same question set:
- **hier_only**: restrict to hierarchical chunks (`source_type=hierarchical`)
- **atomic_plus_hier**: allow both hierarchical + atomic facts (`source_type in {hierarchical,fact}`)

It outputs:
- `results.csv` + `results.jsonl` (top-k per question per mode)
- `summary.md`
- similarity/confidence distribution plots (hist + ECDF)

### Prerequisites
- You have the Sunshine provider manual **ingested, chunked, embedded, published**, and **synced** into dev Vertex.
- Google creds available (ADC or `GOOGLE_APPLICATION_CREDENTIALS`).
- Dev Vertex index endpoint + deployed index id.

### Quick start
1) Create/activate a venv and install deps:

```bash
cd mobius-qa/retrieval-eval
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Set env vars (or fill `config.yaml`):

```bash
export VERTEX_PROJECT="mobius-os-dev"
export VERTEX_REGION="us-central1"
export VERTEX_INDEX_ENDPOINT_ID="projects/.../locations/us-central1/indexEndpoints/..."
export VERTEX_DEPLOYED_INDEX_ID="mobius_chat_dev_stream"

# Optional (for richer output: chunk text/page/section):
export CHAT_RAG_DATABASE_URL="postgresql://.../mobius_chat"
```

3) Run the eval:

```bash
python retrieval_eval.py --config config.yaml --questions questions.yaml
```

Results are written under `reports/retrieval-eval-<timestamp>/`.

### BM25 "atomic candidate" eval (pre-rerank)

This matches the **atomic RAG candidate generation** logic you described:

- **BM25** retrieves top-K **sentences** from the Sunshine manual
- BM25 scores are converted to \([0,1]\) via a **sigmoid normalization**
- We evaluate **where the gold evidence lands** (rank / Recall@K)
- We heavily penalize **confident retrieval on out-of-manual** questions (hallucination risk)

Prereqs:
- `CHAT_DATABASE_URL` (or `CHAT_RAG_DATABASE_URL`) set so the script can read `published_rag_metadata`
- `config.yaml` has `filters.document_authority_level` set (Sunshine isolation token)
- Add gold labels into `questions.yaml` under `gold:` (see header comment in that file)

Run:

```bash
export CHAT_DATABASE_URL="postgresql://.../mobius_chat"
python bm25_eval.py --config config.yaml --questions questions.yaml --top-k 20 --abstain-threshold 0.65
```

Outputs are written under `reports/bm25-eval-<timestamp>/`.

### Ingest + publish helper (RAG side)
If you’re starting from a local PDF and a running `mobius-rag` server, use:

```bash
python ingest_publish_manual.py --pdf "/path/to/Sunshine Provider Manual.pdf" --authority-level "lexicon_qa_sunshine_manual_v1"
```

That script:
1) uploads the PDF via `mobius-rag` `/upload`
2) patches the document to set `authority_level` (used as a filter token)
3) queues chunking, waits for embed to complete, and publishes to `rag_published_embeddings`

After publish, run the dbt sync pipeline to push into dev Vertex.
