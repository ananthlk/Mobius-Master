# Curation — RAG sub-agent charter

**Status:** proposed 2026-07-22 (Ananth). **NEW agent.** Reports to: RAG (macro).

## Mission (one line)
Make sourced documents accessible — chunk, embed, tag, and publish them into the searchable corpus.

## Scope (leg — module detail comes in layer 2)
- Chunking.
- Embedding (embedding-workers).
- Lexicon (j/p/d tags).
- Publish → searchable corpus.

## Coordinates underneath
- **Lexicon agent** (exists) — moves underneath; owns the lexicon module.

## Non-goals
Not sourcing (that's Sourcing). Not retrieval/answering. Not corpus-integrity upkeep (that's Maintaining).

## First tasks
1. Confirm leg scope; bring the Lexicon agent underneath.
2. Layer 2 — take the assigned modules (chunking / embedding / publish); confirm `ownership.yaml` rows.
3. Define the curated-chunk contract the Retriever's pool consumes.
