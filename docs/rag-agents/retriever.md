# Retriever — RAG sub-agent charter

**Status:** proposed 2026-07-22 (Ananth). **NEW agent.** Reports to: RAG (macro).
**This is the refactor target. Ananth guides this one directly, next.**

## Mission (one line)
Be the one clean answering contract — a non-analytics, document-grounded **question → answer + thinking traces** — the interface chat (or anyone) calls.

## Scope
The answer engine, refactored into **7 submodules** (the reason → act → observe loop):
`pool` (one shared, built once) · `shape` (slot model) · `fillers` (a/b/c/d/s) · `router` (one, owns the decision-row) · `synthesis` · `contract` (12-field envelope) · `timing`.

## The refactor (how it's run)
- **Technical Review leads the structure** — architect + the structural gate (byte-compat, single-pool, one-writer/importer, timing, no-god-file).
- **Eval owns outcomes** — latency (incl. under-load), recall, the scorer boundary.
- **Retriever builds** against both gates. Flag-gated (`RAG_ANSWER_ENGINE=legacy|shape`), instant flip-back.
- Verified drivers: externalize the `max=1` in-process job state (→ `min/max>1` headroom) · one pool built once (kill the pre-route→`_bm25_arm` double-build) · minimal per-request path.

## Dependencies
- **Eval scorer** (Tier 2) — `fact_checker` runs in-process as an Eval-owned versioned library (it is the bandit's reward).

## Non-goals
Not corpus build/upkeep (Sourcing/Curation/Maintaining). Not analytics questions.

## First tasks
1. **Await Ananth's focused guidance** (this is the leg he drives next).
2. Receive the reason → act → observe module decomposition from Technical Review.
3. Build the `pool` module first (module #1 — where the job-state/latency/scaling all live).
