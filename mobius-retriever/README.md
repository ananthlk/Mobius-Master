# mobius-retriever

Reusable retrieval module for Mobius. Provides configurable, versioned retrieval paths:

- **Path B**: Vector search + limited reranking (no tags, A/B arm)
- **Path A** (future): Hybrid BM25 + Vector with tags

## Install

From Mobius root with venv active:

```bash
pip install -e ./mobius-retriever
```

## CLI

```bash
mobius-retriever path-b --question "What is prior auth for PT?" --config configs/path_b_v1.yaml
```

## Config

Configs are YAML, versioned. See `configs/path_b_v1.yaml`.
