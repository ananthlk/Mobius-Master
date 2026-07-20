# Instant-RAG → Fully-Working: execution + verification plan

Owner: Instant RAG agent (integrator). Status: coordinating RAG + Chat to a shared bar.
Created 2026-07-15 after two live failures (card-miss on background path; zombie-doc
retrieval failure on `cardtest_phi_0715b.txt` / doc `b855e5b0`).

## 1. Definition of Done (the single bar, shared verbatim with all agents)

For **any** doc — small/large, fresh/duplicate, PHI/clean, fast/slow (>12s escape) —
1. It indexes **and publishes embeddings reliably**. Zero zombie docs (a `documents`
   row with extracted text but **0** rows in `rag_published_embeddings`).
2. The user's question **retrieves the content**. Never "could not access the content"
   for a doc that classified successfully.
3. The **PHI recommendation card renders** (correct verdict styling + evidence chips).
4. The **classification verdict is correct** (PHI→private, clean→public). ✅ already solid
   (classifier 6/6, hardened 4Gi/conc-4/maxScale-10).
5. The doc + verdict surface in **My Vault**.

## 2. Root cause (updated after RAG's count came back)

Two SEPARATE issues, not one seam:

**(a) Card — the 12s escape-to-background** skipped the card trigger. FIXED via chat's
single unconditional trigger (00476), regressed on 00479 (branch instability), re-fixed
on 00483. Watch for further regressions until vault-page→main is reconciled.

**(b) Retrieval "could not access content" — NOT a zombie.** RAG confirmed b855e5b0 is
fully published (1 embedding = correct for a ~300-byte single-chunk doc, status=completed).
So publish is clean even on the escape path. The real cause is **chat-side retrieval
scoping on the DUPLICATE re-upload path**: the scoped instant-RAG search
(`search_uploaded_document` → `lazy_rag_search(include_document_ids)`) depends on
`active.uploaded_files[]` carrying the `document_id` (resolved by
`_resolve_upload_document_id`, react_loop.py:318). If the duplicate path doesn't populate
that, the scoped tool can't fire → ReAct falls back to open-corpus ANN → a 1-chunk PRIVATE
doc + generic query misses top-k → empty. Likely a regression of the rev-00395
duplicate-attach fix. **Design fix:** instant-RAG "what does THIS doc say" must retrieve by
deterministic `document_id` filter, not ANN ranking.

## 3. Fix assignments + dependency order

| # | Agent | Fix | Status |
|---|-------|-----|--------|
| 1 | **RAG** | Confirm `b855e5b0` count. | ✅ DONE — count=1, NOT a zombie, publish clean. RAG RELEASED. |
| 2 | **Chat** | Architectural card fix: single unconditional `_showPhiRecommendationCard` trigger. | ✅ DONE (00476), regressed (00479), re-fixed (00483, refs=2). |
| 3 | **Chat** | Retrieval scoping: duplicate/escape path must populate `active.uploaded_files[].document_id` so `search_uploaded_document` fires; retrieve the uploaded doc by DETERMINISTIC document_id filter, not ANN. | ⏳ OPEN — handed to chat with precise pointer (react_loop.py:318 chain). THE remaining functional blocker. |
| 4 | **Me** | Run verification matrix, iterate, close. | ⏳ waits on #3. |
| 5 | **Chat** | Reconcile vault-page→main so deploys stop regressing shipped fixes. | ⏳ tracked (durability). |

## 4. Verification matrix (I run this end-to-end after they land)

Fresh unique files each run (avoid dedup false-negatives). Watch classifier logs live.

| Case | File shape | Expect: retrieval | Expect: card |
|------|-----------|-------------------|--------------|
| A | small clean, inline (<12s) | answers content | ✓ safe-to-share |
| B | small PHI, inline (<12s) | answers content | ⚠ private + chips |
| C | doc that crosses 12s (escape→bg) | answers content (no zombie) | card renders |
| D | large doc (>1MB, redirect path) | RAG-standalone or bg | card or documented n/a |
| E | duplicate re-upload (PHI) | answers content | card surfaces stored verdict |
| F | duplicate re-upload (clean) | answers content | card surfaces stored verdict |

Pass = every row green + classifier error rate ~0 + zero zombies in a post-run sweep.

## 5. Cadence + escalation

- RAG is heads-down on another major request; Chat may be intermittent. Be patient.
- Periodic nudge ~every 25–30 min; do NOT spam. Each nudge = a status check, not a re-ask.
- When a piece lands, verify that slice immediately (don't wait for both).
- Return to Ananth only when the matrix passes end-to-end, or on a decision genuinely his.
