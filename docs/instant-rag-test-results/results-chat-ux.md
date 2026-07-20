# Instant RAG — Chat-UX Results (manual / browser)

Observed across the 2026-07-13 testing session on the deployed dev app.
Legend: ✅ verified · 🟡 shipped, re-verify pending · 🔴 open bug · ⏳ not yet tested

| ID | Scenario | Status | Evidence / notes | Rev |
|----|----------|--------|------------------|-----|
| U1 | Single upload entry point | ✅ | "⋯ → Upload file" was still live (saw the "Attach a file" modal in-browser; confirmed via bundle grep). Chat removed it; live bundle grep = 0 matches. Paperclip is the only entry now. | chat 00398 |
| U2 | Foreground progress strip | ✅ | Small doc showed the strip: "Extracting pages…" with the violet bar. | chat 00393+ |
| U3 | In-turn answer (warm) | ✅ | `instantrag_test_3.html` answered in the same turn — clean summary, no holding message. | chat 00400 |
| U4 | No fact-checker contradiction | ✅ | Was 🔴 (critic falsely said "source doesn't contain this / upload the correct document" on a correct summary). Root cause: `should_run_critic` fired on numeric content → critic false-positived vs the retrieved passages. Fixed: gate skips critic for instant-RAG single-doc (`skip:instant_rag_single_doc_retrieval_is_ground_truth`). Re-test clean. | chat fix |
| U5 | Retrieval accuracy in chat | ✅ | Answers quoted the verification phrases exactly ("amber lantern 63", "purple lighthouse 92") + specific facts (client counts, rates, windows). | — |
| U6 | Still-indexing short-circuit | ✅ | Was 🔴 (still-indexing detected at Round 1 went through the full LLM composer, ~27 s, inconsistent wording). Fixed: poll always fires (old guard `_known_row_count==0` was always −1 on fresh uploads); short-circuit now emits "bypassing integrator for status reply" + fixed wording, no LLM composer. | chat 00400 |
| U7 | Auto-deliver on ready (cold) | 🟡 | Was 🔴 — short-circuit fired but the **turn went to DONE**, so "I'll answer automatically, no need to ask again" was an empty promise (nothing re-answered). Fixed: on 18 s poll timeout the turn stays open, polls pgvector in-band every 3 s up to 4 min (keepalive ~12 s), re-runs the original query when the doc lands and streams the answer. **Needs a fresh cold-doc re-test to confirm.** | chat 00401 |
| U8 | Pulsating indicator through wait | 🟡 | Was 🔴 (indicator went quiet / DONE after the first try). Fixed with U7 (SSE stays open + keepalive). Re-verify with cold doc. | chat 00401 |
| U9 | Badge Uploading→Indexing | 🟡 | Was 🔴 (banner stuck on "⏳ Uploading…" after upload completed). Fixed: `stopComposerUploadPhaseEmits()` → `hideChatStatusBanner()`. Re-verify in browser. | chat 00400 |
| U10 | [Retry] chip on failed doc | 🟡 | Wired: `POST /documents/{id}/retry` (RAG-confirmed endpoint), reconnects the progress strip. Needs a genuinely-failed doc to exercise. | chat 00400 |
| U11 | Background/large-doc UX (>1 MB) | 🟡 | **413 bug FIXED + verified.** Was: all large uploads 413 because `/chat/upload` (renamed) wasn't in `_LARGE_BODY_PREFIXES`, so it hit the 1 MB body-cap middleware before the 100 MB handler. Chat added it (rev **00403**). Verified: a 1.5 MB body to `/chat/upload` now returns 422 (handler) instead of 413 (middleware cap) — large requests reach the handler. **Remaining:** browser re-test of the actual 1.4 MB PDF — confirm it uploads, routes to background, and shows live progress (not silent). | chat 00403 |
| U12 | Duplicate re-upload attaches to thread | ✅ | Was 🔴 (duplicate returned "already in corpus" but wasn't queryable → "please specify which document"). Fixed: duplicate path now writes the thread `uploaded_files` record. Re-test queryable. | chat 00395 |

## Summary

- **Verified working:** single entry point, foreground strip, warm in-turn answers,
  accurate retrieval, no critic contradiction, still-indexing short-circuit, duplicate
  re-attach.
- **Shipped, pending one cold re-test:** the cold-doc **auto-deliver** (U7/U8), the
  **badge flip** (U9), and the **[Retry] chip** (U10) — all on chat rev 00401.
- **Not yet tested:** the **background/large-doc** progress experience (U11).

The single most important remaining verification is **U7 (auto-deliver)** — upload a
fresh file when the instance is cold and confirm the answer arrives on its own with the
indicator pulsing, no re-ask.
