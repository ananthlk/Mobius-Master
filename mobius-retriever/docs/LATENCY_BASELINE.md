# BM25 vs Vector Latency Baseline

**Question:** "What is the prior authorization requirement for physical therapy?"

## Baseline (before adding more docs)

| Metric | Value |
|--------|-------|
| BM25 corpus | 729 hierarchical paragraphs → 9,105 sentences |
| Vector latency | 5,219 ms |
| BM25 latency | 862 ms (includes corpus fetch + build + search) |

**Date:** Recorded before bulk-publish and DBT pipeline run.

## Actions taken

1. **Bulk-publish script** ([mobius-rag/scripts/publish_unpublished_documents.py](mobius-rag/scripts/publish_unpublished_documents.py)): Published 20 documents with embeddings but not in `rag_published_embeddings` → 1,914 rows written.
2. **DBT pipeline** (`land_and_dbt_run.sh`): Ingest 1,914 rows → BigQuery mart → sync to Chat Postgres (1,914 rows written). Vertex upsert failed (1000 datapoints/request limit).
3. **Re-measure:** Ran compare CLI again.

## After pipeline: Re-measure results

| Metric | Before | After |
|--------|--------|-------|
| BM25 corpus | 729 paragraphs, 9,105 sentences | 729 paragraphs, 9,105 sentences |
| Vector latency | 5,219 ms | 5,157 ms |
| BM25 latency | 862 ms | 931 ms |

**Note:** BM25 corpus size unchanged; retriever may use a different Chat Postgres (CHAT_RAG_DATABASE_URL) than the DBT sync target (CHAT_DATABASE_URL), or authority_level filter may exclude new docs. Vector search unchanged; Vertex upsert partially failed.

## BM25 with question tags (narrow scope)

Tag the question (payer, program, state), filter corpus by tag matches, run BM25. Faster and scalable.

```bash
# Benchmark: tagged vs untagged (time + overlap)
python -m mobius_retriever.cli benchmark-tagged -q "What is Molina's prior auth for PT in Florida?" -n 3

# Single run with tags (e.g. in compare)
python -m mobius_retriever.cli benchmark -q "..." --tagged
```

Results written to `benchmark_tagged_<ts>.json` for comparison with previous runs.

## BM25 Latency Benchmark (scope vs speed)

To test whether BM25 should use a narrower scope (hierarchical only) or full corpus:

```bash
# Hierarchical only (narrow scope) – default
PYTHONPATH=mobius-retriever/src python -m mobius_retriever.cli benchmark \
  -q "What is the prior authorization requirement for physical therapy?" -n 10

# Full corpus (hierarchical + fact) – heavier load
PYTHONPATH=mobius-retriever/src python -m mobius_retriever.cli benchmark \
  -q "What is the prior authorization requirement for physical therapy?" -n 10 --all-source-types

# With latency plot (requires matplotlib)
python -m mobius_retriever.cli benchmark -q "..." -n 10 --all-source-types --plot
```

Output: min/max/mean/median (and stdev) latency in ms. Use `--all-source-types` to remove the hierarchical restriction and search the full corpus for latency comparison.

## Verify BM25 database

Ensure the retriever and DBT sync use the same Postgres. Run:

```bash
PYTHONPATH=mobius-retriever/src python -m mobius_retriever.cli db-check -c mobius-retriever/configs/path_b_v1.yaml
```

This prints:
- `postgres_url` (password masked) — DB BM25 and Vector metadata read from
- Whether it matches `CHAT_DATABASE_URL` (mobius-dbt sync target)
- `published_rag_metadata` row counts: total, hierarchical (BM25 corpus), and with authority_level filter when set

BM25 corpus size = hierarchical rows matching the config filters. If corpus is smaller than expected, check that `CHAT_RAG_DATABASE_URL` (retriever) and `CHAT_DATABASE_URL` (mobius-dbt) point to the same DB.

## Commands

```bash
# Publish unpublished docs (run from mobius-rag)
.venv/bin/python scripts/publish_unpublished_documents.py
# Optional: --dry-run, --limit N

# Run DBT pipeline (run from mobius-dbt)
PATH="/path/to/.venv/bin:$PATH" ./scripts/land_and_dbt_run.sh

# Re-measure latency
PYTHONPATH=mobius-retriever/src python -m mobius_retriever.cli compare \
  -q "What is the prior authorization requirement for physical therapy?" \
  -c mobius-retriever/configs/path_b_v1.yaml
```
