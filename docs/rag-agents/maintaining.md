# Maintaining — RAG sub-agent charter

**Status:** proposed 2026-07-22 (Ananth). **NEW agent.** Reports to: RAG (macro).

## Mission (one line)
Keep the corpus's data integrity over time — nightly sweeps, freshness, coherence.

## Scope (leg — module detail comes in layer 2)
- Nightly engine (doc + lexicon integrity sweeps).
- Content-less gate · freshness · corpus coherence.

## Coordinates underneath / dependencies
- **Nightly agent** (exists) — moves underneath; owns the nightly engine.
- **Payor agent** (dependency) — owns the fact-base; Maintaining relies on it, does not own it.

## Non-goals
Not sourcing or curation of new docs. Not answering.

## First tasks
1. Confirm leg scope; bring the Nightly agent underneath.
2. Layer 2 — confirm the assigned modules + `ownership.yaml` rows.
3. Define the integrity signals the corpus exposes (what "healthy corpus" means, measurably).
