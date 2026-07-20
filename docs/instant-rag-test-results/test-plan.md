# Instant RAG — Test Plan

Date: 2026-07-13 · Owner: Instant RAG agent
Environment: dev (mobius-chat + mobius-rag on Cloud Run, us-central1)

Two layers:
- **API layer** — driven directly against `mobius-rag /upload` + `/api/query`. Automated
  and re-runnable via `run_api_tests.sh`. Results in `results-api.md`.
- **Chat-UX layer** — requires an authenticated chat session + browser (the ReAct loop,
  progress UI, fact-checker, auto-deliver). Verified manually; results in
  `results-chat-ux.md`.

## API-layer cases (automated)

| ID | File | Format | Size | What it verifies | Expected |
|----|------|--------|------|------------------|----------|
| A | t_alpha_quickfacts.txt | txt | ~0.3 KB | fast index + retrieval | searchable in ~10–20 s; retrieves "copper falcon 12", CPW-5120, 2,900 |
| B | t_bravo_payer.txt | txt | ~0.5 KB | precise multi-fact retrieval | retrieves "indigo walrus 55" + 18 days + $27.30 + 120 days |
| C | t_charlie_policy.html | html | ~0.6 KB | HTML extraction + retrieval | retrieves "bronze marmot 07" + 52 sessions + SBC-9040 |
| D | t_delta_auth.pdf | pdf | ~1.6 KB | PDF extraction + retrieval | retrieves "scarlet heron 88" + RWH-AUTH-7719 + 25 days |
| E | t_foxtrot_large.txt | txt | ~1.6 MB | large-doc chunking + retrieval of a buried fact | retrieves "cobalt lynx 91" (buried at section 3000), FOX-7788, $18.90 |

Timing note: the **first** upload after an idle period is cold (embed provider ~17 s);
subsequent uploads are warm (~9 s). The suite runs cases in sequence, so A is coldest.

## Chat-UX-layer cases (manual, browser)

| ID | Scenario | What it verifies | Status source |
|----|----------|------------------|---------------|
| U1 | Single upload entry point | only the paperclip; "⋯ → Upload file" removed | bundle grep + browser |
| U2 | Foreground progress strip | small doc shows Extracting→Chunking→Indexing→Ready | browser |
| U3 | In-turn answer (warm) | ready doc answers in the same turn | browser |
| U4 | No fact-checker contradiction | critic skipped for instant-RAG single-doc | browser |
| U5 | Retrieval accuracy in chat | answer quotes the verification phrase + facts | browser |
| U6 | Still-indexing short-circuit | plain markdown, no LLM composer, consistent wording | browser |
| U7 | Auto-deliver on ready (cold) | answer arrives on its own, no re-ask | browser |
| U8 | Pulsating indicator through wait | indicator keeps pulsing, doesn't go to DONE | browser |
| U9 | Badge Uploading→Indexing | banner flips once upload completes | browser |
| U10 | [Retry] chip on failed doc | re-processes without re-upload | browser |
| U11 | Background/large-doc UX (>1 MB) | routes to background; shows live progress (not silent) | browser |
| U12 | Duplicate re-upload | attaches existing doc to the thread, queryable | browser |
