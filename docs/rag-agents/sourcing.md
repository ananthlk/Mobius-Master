# Sourcing — RAG sub-agent charter

**Status:** proposed 2026-07-22 (Ananth). **NEW agent.** Reports to: RAG (macro).

## Mission (one line)
Get documents into RAG — from upload, drive, and the web — and hand raw docs to Curation.

## Scope (leg — module detail comes in layer 2)
- Document ingestion: upload · path_b · drive.
- Web sourcing (the code's `app/curator`, renamed to end the collision with the Curation leg): discovered_sources (~11k URLs), source escalation, web downloads.

## Coordinates underneath / dependencies
- **Instant-RAG agent** (dependency) — instant upload is its own agent.
- **Org / DB agent** (dependency) — org uploads / the org doc-store.

## Non-goals
Not chunk/embed/publish (that's Curation). Not the answering path.

## First tasks
1. Confirm leg scope.
2. Layer 2 — take the assigned module list; confirm rows in `ownership.yaml`.
3. Define the clean hand-off contract to Curation (raw doc in → curated).
