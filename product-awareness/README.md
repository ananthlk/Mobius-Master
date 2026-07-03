# product-awareness

An independent, ownable module that answers **"how do I use Mobius?"** from the
product documentation, and turns every unanswerable question into tracked
documentation debt (the feedback loop).

- **Own corpus** (`product_docs`), **own embedder**, **own vector store** — nothing
  here imports another Mobius module's internals.
- The only cross-module touch is a best-effort `docs_gap` write to the feedback
  agent's `product_feedback` table. See `docs/product-awareness-feedback-contract.md`.

## Design decisions

| decision | choice | why |
|---|---|---|
| Retrieval | **lazy / vector-only** | product docs are small + curated; no BM25/rerank/strategy/lexicon needed |
| Store (prod) | **pgvector**, our own `product_docs_embeddings` table | durable + already on Cloud SQL; the platform is migrating *off* Chroma (GCE VM, outage 2026-04-27). Own table ⇒ own columns, zero policy-corpus contamination |
| Store (offline/test) | **numpy** cosine | runs with numpy alone, no creds |
| Embedder (prod) | Vertex **gemini-embedding-001** (1536, dim-pinned) | the platform's own embedder — no new credential |
| Embedder (offline/test) | local **TF-hash** | deterministic, offline — proves *plumbing*, not semantic quality |
| Chunking | by `##` H2 section | manuals are clean markdown; section = natural unit |
| `status` flag | chunks under `## Not yet available (planned)` → `planned` | the reality-gate that splits `docs_gap` from `feature_request` |
| `τ_gap` | ONE constant (`PRODUCT_HELP_TAU_GAP`) | same threshold for "can't answer" AND gap-fire → cannot drift |

## Layout

```
product_awareness/
  config.py     paths, collection, τ_gap, module↔doc map
  chunker.py    markdown → chunks (+ status flag; drops Doc-readiness notes)
  embedder.py   OpenAI | local TF-hash (pluggable)
  store.py      PgVectorStore | NumpyStore | ChromaStore (pluggable)
  ingest.py     manuals → chunks/*.jsonl → embeddings → store
  search.py     product_help_search + the 3-outcome disambiguation
  gapwriter.py  best-effort docs_gap/feature_request write (the seam)
  skill.py      chat-invocable handler + registration notes
  cli.py        ingest | search | stats
corpus/
  chunks/       <module>.jsonl — the chunked manuals (inspectable)
  index/        built vectors (numpy .npz here; pgvector in Cloud SQL in prod)
```

## Run (offline)

```bash
PYTHONPATH=. python3 -m product_awareness.cli ingest
PYTHONPATH=. python3 -m product_awareness.cli search "how do I sign in with google"
python3 tests/test_pipeline.py
```

## Run (production)

```bash
export PRODUCT_DOCS_STORE=pgvector PRODUCT_DOCS_EMBEDDER=vertex
export PRODUCT_DOCS_DATABASE_URL=...        # the Cloud SQL Postgres
export VERTEX_PROJECT_ID=... VERTEX_LOCATION=us-central1
PYTHONPATH=. python3 -m product_awareness.cli ingest      # build corpus into pgvector
PYTHONPATH=. python3 -m product_awareness.cli calibrate   # pin τ_gap (two-sided probe)
PYTHONPATH=. uvicorn product_awareness.service:app --port 8070   # retrieval service
```

The chat side calls this service via `CHAT_SKILLS_PRODUCT_HELP_URL` (see the
`product_help_search` builtin in mobius-chat) and files any docs_gap in-process.

## Status

- Pipeline, chunking, and the 3-outcome disambiguation logic: **built + tested**.
- `τ_gap` value and retrieval quality: **must be calibrated on the OpenAI embedder** —
  the offline TF stand-in has no reliable semantic separation (in/out score
  distributions overlap), so it validates plumbing only. The 0.35 default is a
  provisional OpenAI-cosine start; calibrate two-sided per the contract.
- Chat registration (`SkillSpec` + manifest `_registry_block`) and the `status=planned`
  metadata are wired in code; live wiring into mobius-chat is the next step.
