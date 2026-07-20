# Instant RAG — Test Cases & Results

Self-contained test folder for the instant-RAG upload → index → retrieval → answer flow.
Pick this up any time; the API suite is re-runnable.

## Contents
- `test-plan.md` — all test cases (API-layer + chat-UX-layer), what each verifies, expected.
- `results-api.md` — automated API results (upload → searchable → retrieval, per format/size).
- `results-chat-ux.md` — chat-UX results (browser/manual), with per-case status + evidence.
- `run_api_tests.sh` — re-runnable API suite. Reads the 5 test files from `~/Downloads`,
  uploads each to RAG, polls until searchable, checks retrieval. Writes `raw/api_results.txt`.
- `raw/` — raw run output + retrieved passages per case.

## How to re-run the API suite
```bash
bash docs/instant-rag-test-results/run_api_tests.sh
cat docs/instant-rag-test-results/raw/api_results.txt
```
(The 5 test files live in `~/Downloads`: t_alpha_quickfacts.txt, t_bravo_payer.txt,
t_charlie_policy.html, t_delta_auth.pdf, t_foxtrot_large.txt.)

## Current verdict — 2026-07-13

| Layer | Status |
|-------|--------|
| **API (upload→index→retrieve)** | 🟢 **HEALTHY — all 5 cases pass.** Fresh uploads searchable in **0–2 s**, all formats + 1.6 MB large-doc, correct retrieval. Run 1 was a full outage from a 743k-row bulk-UPDATE lock on `rag_published_embeddings` (found + killed). Outage-window "zombie" docs cleaned up (orphan retry, verified searchable) and dedup hardened (RAG `5c52145`) so it can't recur. See `results-api.md`. |
| **Chat UX** | 🟢 mostly verified (single entry, foreground strip, in-turn answers, no critic contradiction, accurate retrieval, still-indexing short-circuit, duplicate re-attach). 🟡 cold auto-deliver / badge / [Retry] shipped on chat `00401`, pending one cold re-test. ⏳ background/large-doc progress untested. See `results-chat-ux.md`. |

**Bottom line:** API layer is healthy and fast again after clearing a RAG DB lock. Chat UX
is largely verified; the cold-auto-deliver + large-doc browser re-tests are now meaningful
(the lock was the blocker). One low-urgency cleanup pending on RAG (outage-window zombie docs).
