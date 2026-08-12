# RAG — Layer-2 Module Map (leg → modules)

**Status:** draft 2026-07-22 (Technical Review, structural lead / owns `ownership.yaml`).
**Companion:** the agent tree (layer 1) · `ownership.yaml` · `docs/rag-target-structure-spec.md`.

## The ownership-representation decision (read this first)

`mobius-rag` is **one undecomposed repo** — today `mobius-rag/**` resolves to a single "RAG agent," and the four legs are sub-trees of that monolith. **You cannot express clean leg ownership as fleet `ownership.yaml` path-globs yet**, because the boundaries don't exist as clean paths (god-file routes, a shared `app/worker`, a name-colliding `app/curator`).

**So: layer-2 ownership is tracked HERE — a RAG-internal module map by subsystem — NOT as path-globs in the fleet `ownership.yaml`.** Path-globs materialize *per leg* only **as the decomposition lands** (§ Seams below) and I verify each cut is non-overlapping. Until a leg's paths are clean, `ownership.yaml` keeps ONE row (`mobius-rag/** → Master RAG agent`) and this map is the source of truth for who owns what.

**Do not flip `ownership.yaml` path-glob rows yet.** Own your subsystem here; flip to path-globs when your decomposition cut is verified.

## Leg → subsystems (provisional, verified where noted)

| Leg | Subsystems (RAG-internal) | Notes |
|---|---|---|
| **Sourcing** | document ingestion (upload · path_b-ingest · drive) · **web sourcing** (`app/curator` → to be renamed) | hands raw docs to Curation |
| **Curation** | chunking · embedding-workers · **lexicon-build/tagging** · publish → searchable | Lexicon agent underneath; hands curated chunks to Retriever's pool |
| **Maintaining** | nightly engine (integrity sweeps) · content-less gate · freshness / coherence | Nightly agent underneath; reads Curation's lexicon module (dependency, not ownership) |
| **Retriever** | the `corpus_search_*` answer engine → 7 modules (pool · shape · fillers a/b/s · router · synthesis · contract · timing) · `retriever_backend` · query-time `corpus_search_lexicon` **lookup** | the refactor; I lead structure |

## Seams — the decomposition work that turns subsystems into clean path-globs

These are the boundaries a repo-glob can't split today. Each is a structural work item; owners propose the cut, **I gate** it (byte-compat + single-owner + no-god-file):

1. **`app/curator` → rename (Sourcing).** The web-sourcing code is literally `curator` and collides head-on with the *Curation* leg (item #9/#26 trips on two legs reading "curator"). Target: **`app/web_sourcing/`** (proposed). Sourcing owns the rename; I track it as a structural item.
2. **~~`app/worker` split~~ → RESOLVED to a clean ASSIGNMENT (Tech Review gated 2026-07-22).** Code-verified: `app/worker` requires pre-existing pages (`process_job` fails with none, `main.py:235`), only *reads* them (`coordinator.py:61-73`), and contains **zero raw-file extraction** (grep-confirmed). ⇒ **`app/worker/**` → Curation ENTIRELY** — not a cut. The "ingest half" is the extract+enqueue code in `app/main.py` (Sourcing's edge) → moves to a Sourcing router under seam #4. Naming disambiguated: **`page_extraction`** (Sourcing, raw→pages) vs **`fact_extraction`** (Curation, path_a). Contract: `docs/rag-agents/raw-doc-contract.md` §8.
3. **Lexicon build vs lookup (Curation ⟷ Retriever).** Lexicon-**build/tagging** = Curation; query-time `corpus_search_lexicon` **lookup** inside the engine = Retriever. Clean dependency: Retriever's engine *reads* Curation's lexicon; the module isn't double-owned.
4. **`main.py` god-file → per-leg routers (Master RAG coordinates).** Upload/drive routes → Sourcing router; etc. Until this decomposition lands, leg ownership stays in this map, not path-globs.

## Cross-agent (dependencies, not RAG legs)
- **Lexicon agent** → under Curation · **Nightly agent** → under Maintaining (both: Ananth points them in).
- **Payor** owns the fact-base (Maintaining depends). **Eval** owns the scorer (Tier-2, in-process) + the harness (Tier-1, extracts). **Instant-RAG / Org / DB** — Sourcing dependencies.

## How each leg proceeds now
1. Own your subsystem **here** (this map). Do **not** flip `ownership.yaml` path-globs.
2. Propose your decomposition cut (your seam above); I gate it.
3. When your cut is verified + merged, I add your clean path-glob rows to `ownership.yaml` and you flip them `confirmed`.
4. Define your cross-leg hand-off contract (Sourcing→Curation raw-doc; Curation→Retriever curated-chunk) directly with the sibling; I gate the seam.
