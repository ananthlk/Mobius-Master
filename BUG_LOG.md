# Bug Log — Mobius Platform
## File-Backed Issue Tracker (Persists in Git)

**Purpose:** Track known bugs and quality issues that can be picked up during slower periods. This lives in git so issues never evaporate to message-channel drops.

**How to use:**
- Add new issues at the bottom with `## Bug [ID]` format
- Update status as work progresses (OPEN → IN PROGRESS → FIXED → VERIFIED)
- Link to commits/PRs in fixes
- Never delete; mark as FIXED + move to VERIFIED section when confidence is high

---

## 🔴 OPEN BUGS (Active, Unassigned)

### Bug #1: Irrelevant Jurisdiction Prompt When Context Exists
**Component:** Chat RAG reasoning  
**Severity:** MEDIUM (UX failure, but system recovers after retry)  
**Reporter:** Ananth (2026-08-12)  
**Repro:**

User asks: *"Can you review this page https://www.sunshinehealth.com/providers/Billing-manual.html and tell me the key billing rules for behavioral health providers?"*

Expected: Recognize Sunshine Health (payer) is already specified → search corpus for SH billing rules  
Actual: System asks "Which state or jurisdiction did you mean?" even though payer context is present  
Error in logs: `Cannot read properties of undefined (reading 'toLowerCase')`

**Impact:**
- User sees "Request failed" + irrelevant prompt
- Forces retry (user must re-submit same query)
- After retry, system works correctly (contradiction suggests state loss mid-turn)

**Root cause hypothesis:** 
- Router or Shape step loses payer context when escalating to external search (Filler-d)
- Likely in `AnswerShapeResult` → payer field not being threaded through to Router/Filler decision
- Or: PHI classifier / jurisdiction gate running on partial context

**Next steps:**
1. Reproduce in dev with payer-specific query
2. Check Shape output for payer field presence
3. Verify Router receives payer in `AnswerShapeResult`
4. Trace Filler-d context loss

**Owner:** (unassigned — Router or Chat agent)

---

### Bug #2: Web Scrape Tool Output Not Verified in RAG Answers
**Component:** Filler-d (Web Search) + Synthesis  
**Severity:** MEDIUM (accuracy risk — claims without source verification)  
**Reporter:** Ananth (2026-08-12), observed in Bug #1 investigation  
**Repro:**

User asks: *"Can you review this page [URL] and tell me the key billing rules?"*  
Force RAG through mode-d (web search).

Expected: Answer includes only claims that can be traced to provided RAG chunks  
Actual: Final answer includes detailed tables + claims with audit note: "The final answer is almost entirely based on information from a `web_scrape` tool output which was not provided for verification. The provided RAG chunks support almost none of the claims."

**Impact:**
- Answers appear authoritative but lack verifiable source
- "Clean claim requirements" table has no supporting doc link
- Violates core promise: "grounded, not general — comes with citations you can check"

**Root cause:**
- Synthesis step not enforcing source-citation linkage
- Web scrape results may not be saved to `documents` table before synthesis runs
- Or: Synthesis allowed to use tool output as implicit source without doc_id

**Related:**
- Phase 13.3c: `web-scraper → POST /sources/upsert` has zero callers (unbuilt)
- Filler-d workflow may bypass document ingestion entirely

**Next steps:**
1. Verify Filler-d web scrape saves to `documents` before answering
2. Check Synthesis contract: does it require `source_document_id` for every claim?
3. Audit a mode-d answer end-to-end (tool → doc → chunk → answer)
4. Consider gating mode-d until Phase 13.3c lands (or make docs explicit in output)

**Owner:** (unassigned — Retriever/Filler-d or Synthesis agent)

---

### Bug #3: Router Loses Carry-Forward Context on Escalation
**Component:** Router / Query state threading  
**Severity:** MEDIUM (causes unnecessary rework; affects latency + cost)  
**Reporter:** Ananth (2026-08-12), inferred from Bug #1  
**Repro:**

1. User provides payer + specific URL (rich context)
2. Router's first allocation (pool-based search) doesn't meet confidence bar
3. Router escalates to Filler-d (external search)
4. Filler-d doesn't know payer or original URL context
5. Filler-d prompts for disambiguation instead of reusing carry-forward

**Expected:** Context (payer, URL, original query) threads through entire chain  
**Actual:** State loss between Router decision and Filler execution

**Impact:**
- Forces user rework
- Wastes latency on re-clarification
- Confidence signal lost (Router's "need external evidence" doesn't transfer reasoning to external source)

**Root cause:**
- `AnswerShapeResult` or `RoutingLadder` may not include full carry-forward fields
- Or: Filler-d initialization doesn't unpack context from Shape/Router outputs

**Next steps:**
1. Map carry-forward fields: original_query, payer, url, user_context, confidence_bar
2. Verify Router writes these to `rag_query_decisions`
3. Verify Filler-d reads + uses them on execute
4. Add test: escalation query should not re-prompt for info already provided

**Owner:** (unassigned — Router or Filler-d agent)

---

### Bug #4: Document Retry Endpoint Fails — GCS Bucket Billing Disabled + Bucket Mismatch
**Component:** mobius-rag `POST /documents/{document_id}/retry` + GCS config
**Severity:** HIGH (blocks recovery of any failed document — the one mechanism meant to fix ingestion failures doesn't work)
**Reporter:** Payor Platform agent (2026-08-13), first real customer of this endpoint (mobius-payor's Repository redesign wires a "🔄 retrigger" action to it for failed pipeline stages)
**Repro:**

```
curl -X POST https://mobius-rag-ortabkknqa-uc.a.run.app/documents/bddd379b-6243-4c19-bfa2-d793b6e0be15/retry
```
(real document: `sse_test.txt`, `documents.status='failed'`, `file_path='gs://mobius-rag-uploads-dev/sse_test.txt'`)

**Expected:** Re-runs extraction → chunk → embed → publish for the document (per the endpoint's own docstring).
**Actual:** HTTP 500 —
```json
{"detail":"Extraction failed: 403 GET https://storage.googleapis.com/download/storage/v1/b/mobius-uploads-mobiusos-new/o/sse_test.txt?alt=media: The billing account for the owning project is disabled in state absent: ..."}
```

**Two distinct real issues, both confirmed:**
1. **Billing disabled** — the GCP project backing bucket `mobius-uploads-mobiusos-new` has its billing account disabled → hard 403 on every fetch from that bucket. Ops-level fix (re-enable billing), not a code bug.
2. **Bucket mismatch** — this document's `file_path` says bucket `mobius-rag-uploads-dev`, but the deployed Cloud Run service fetched from `mobius-uploads-mobiusos-new` instead. `app/config.py` defaults `GCS_BUCKET` to `mobius-rag-uploads-mobiosos` locally; the deployed service's env value has clearly drifted from what's actually recorded in documents' `file_path`. The retry endpoint's prefix-strip logic (`app/main.py` `retry_document`) assumes a single global `GCS_BUCKET` matches every document's real bucket — it doesn't, at least for older/migrated documents.

**Impact:** The one recovery mechanism for a failed document (11 real documents currently sit at `status='failed'` fleet-wide) doesn't work reliably. Good news: the endpoint's own error handling is solid — `documents.status` correctly reverts to `'failed'` on failure, no zombie `'extracting'` state left behind.

**Next steps:**
1. Re-enable billing on the GCP project backing `mobius-uploads-mobiusos-new`, or confirm that bucket should be fully retired.
2. Fix `retry_document`'s GCS bucket resolution to respect the bucket actually embedded in each document's `file_path`, not just the env-configured `GCS_BUCKET`.
3. Once fixed, mobius-payor's Repository "🔄 retrigger" button (already wired, tested against this exact failure) should be re-verified against a real failed document.

**Owner:** (unassigned — mobius-rag / whoever owns GCS deploy config)

---

### Bug #5: `published_rag_metadata.document_display_name` Never Refreshes, Even on Republish — Breaks `fetch_document` Disambiguation
**Component:** mobius-rag `app/services/publish_sync.py` (`_INSERT_SQL`) + mobius-chat `fetch_document` skill
**Severity:** HIGH (root cause of a real, user-visible bad fetch_document result)
**Reporter:** Payor Platform agent (2026-08-13), investigating why `fetch_document` returned 3 ambiguous candidates for "the sunshine health provider manual" instead of the right one (Ananth pasted a real chat screenshot showing this)
**Status:** **CODE FIXED, NOT YET DEPLOYED** (2026-08-13) — Ananth: "you fix but let mobius rag know so that they can deploy." Payor Platform agent added `document_display_name = EXCLUDED.document_display_name` to the `ON CONFLICT DO UPDATE SET` list in `mobius-rag/app/services/publish_sync.py` (line ~359), syntax-verified. **mobius-rag's owner still needs to: review the change, and deploy it** — this session did not deploy mobius-rag. No dedicated test file exists for `publish_sync.py` to run as a regression check; worth a manual publish/republish smoke test post-deploy (set a `documents.display_name`, republish, confirm `published_rag_metadata.document_display_name` picks it up).

**Repro / trace (code inspection, not yet reproduced live):**

`mobius-chat/app/skills/builtin/fetch_document.py` (`_score_doc`, `_fetch_candidates`) resolves a document purely by token-overlap against `published_rag_metadata.document_display_name` (falling back to `document_filename`/`document_payer`). No `asset_type` or tag signal is used at all — see Bug/finding (b) below.

Tracing where `document_display_name` comes from: `mobius-rag/app/services/publish_sync.py`'s `_INSERT_SQL` writes to `published_rag_metadata` with:
```sql
ON CONFLICT (id) DO UPDATE SET
    text = EXCLUDED.text,
    document_payer = EXCLUDED.document_payer,
    document_state = EXCLUDED.document_state,
    document_program = EXCLUDED.document_program,
    document_authority_level = EXCLUDED.document_authority_level,
    document_status = EXCLUDED.document_status,
    source_type = EXCLUDED.source_type,
    content_sha = EXCLUDED.content_sha,
    updated_at = EXCLUDED.updated_at
```
**`document_display_name` is not in the `DO UPDATE SET` list.** So even a full republish of an already-published document (e.g. via `POST /documents/{id}/retry`, which does re-run publish) will NOT refresh a stale/empty display name in `published_rag_metadata` — only the very first publish of a fresh row ever sets it. A separate admin endpoint, `POST /admin/patch-doc-display-name`, exists to fix this "without a full republish" — but it only patches `rag_published_embeddings.document_display_name`, a **different** denormalized table from the one `fetch_document` actually queries (`published_rag_metadata`). Neither path currently reaches the table that matters.

**Impact:** `documents.display_name` is real, exists, and is meant to be the primary signal for fetch_document to disambiguate ("User-friendly name; when set, UI shows this instead of filename" per its own column comment) — but there is currently **no working path** to get a corrected display name into the table fetch_document reads, for a document that's already been published once. This is the direct root cause of the 3-way "which one did you mean" screenshot Ananth shared, and it will keep happening even after names are fixed at the source, until this is patched.

**Next steps:**
1. ~~Add `document_display_name = EXCLUDED.document_display_name` to `_INSERT_SQL`'s `ON CONFLICT DO UPDATE SET` list~~ — DONE (2026-08-13, Payor Platform agent).
2. mobius-rag owner: review + deploy the fix.
3. Optional/separate: `/admin/patch-doc-display-name` still only patches `rag_published_embeddings`, not `published_rag_metadata` — not touched by this fix, low priority now that the real sync path works, but worth a note if that endpoint is relied on elsewhere.
4. Once deployed, mobius-payor's Repository "display name" edit (already wired) should reach fetch_document on the next republish — worth a live end-to-end re-check after deploy.

**Owner:** mobius-rag (unassigned individual — whoever owns `publish_sync.py` — needs to review/deploy the fix already made)

---

### Bug #6: `rag_query_traces.correlation_id` Never Populated — Blocks Per-Document Feedback Attribution
**Component:** mobius-rag query pipeline (whatever writes `rag_query_traces`) + mobius-chat feedback capture
**Severity:** HIGH (real user feedback data exists but can't be attributed to a document)
**Reporter:** Payor Platform agent (2026-08-13), building per-document Usage history — real likes/dislikes data was found (`mobius_chat.chat_source_feedback`: `correlation_id`, `source_index`, `rating` — a real per-source thumbs up/down table with real rows), but couldn't be joined to a specific document.
**Status:** **CODE FIX MADE (2026-08-13), semantic equivalence NOT fully verified.** Payor Platform agent added `correlation_id` to the `rag_query_traces` INSERT in `mobius-rag/app/services/corpus_search_agent.py` (~line 3737), reusing the same `agent_id` value already written to the sibling `rag_query_decisions` INSERT a few lines above it in the same function (consistent with existing, already-shipped design — not a guess). Syntax-checked, wrapped in the same fail-open try/except that already guards this insert. **What's NOT verified:** whether `agent_id` in this function is actually the same value as mobius-chat's request-level `correlation_id` (the UUID `chat.py` generates per chat turn, which `chat_source_feedback.correlation_id` is keyed on) — tracing that fully requires following the call chain across chat.py → the queue/worker → the corpus_search skill → the HTTP call into RAG → this function's `agent_id` parameter, which spans multiple files in both repos and wasn't completed. mobius-rag's owner should confirm this before relying on it, and ideally add a real test asserting `chat_source_feedback.correlation_id` values actually appear in `rag_query_traces.correlation_id` after a real chat turn + thumbs-up.

**Repro:**
```sql
-- mobius_rag database
SELECT count(*) AS total, count(correlation_id) AS with_correlation_id FROM rag_query_traces;
--  total | with_correlation_id
-- -------+---------------------
--   1233 |                   0
```
Every one of `chat_source_feedback`'s 4 real (non-test) `correlation_id` values was checked against `rag_query_traces.correlation_id` — zero matches, because the column is never written to in the first place (0/1233 rows), not because of a mismatch in values.

**Impact:** `chat_source_feedback` records *which source slot* (`source_index`) got a thumbs up/down, and `rag_query_traces.full_response->chunks[source_index]` would tell you which `document_id` that slot pointed to — but only if the two rows can be joined via `correlation_id`. Today they can't. Real per-document like/dislike data exists but is stranded — can't be surfaced anywhere per-document (including mobius-payor's new Usage history) until this is wired.

**Next steps:**
1. Whoever writes `rag_query_traces` (mobius-rag's query/retrieval pipeline) needs to populate `correlation_id` on write — it's already a column, just unused.
2. Once populated, per-document likes/dislikes becomes: join `chat_source_feedback` (mobius_chat DB) → `rag_query_traces` (mobius_rag DB) on `correlation_id` → `full_response->chunks[source_index]->document_id`. Cross-database (different Postgres DBs on the same instance), so needs app-code correlation, not a single SQL join.

**Owner:** (unassigned — mobius-rag pipeline / whoever emits query traces)

---

### Bug #7: Repeated `chunking_jobs` Runs May Not Supersede Prior Published Chunks — Possible Retrieval Over-Weighting
**Component:** mobius-rag ingestion/publish pipeline (whatever writes `rag_published_embeddings` on a `chunking_jobs` completion)
**Severity:** HIGH (hypothesis, unverified against actual pipeline code — but if true, silently biases retrieval fleet-wide, not just for this one document)
**Reporter:** Payor Platform agent (2026-08-13), surfaced while investigating a real duplicate pair found by the new PDF-metadata duplicate scan (Sunshine Health corpus)

**Repro / real data (mobius_rag DB, checked directly):**

Two documents, same underlying content (`title="Provider Manual"`, `page_count=139`, `creation_date` identical — a confirmed version pair per the duplicate-scan logic):

| | `Sunshine Provider Manual.pdf` (`d9721756-…`) | `Provider_Manual.pdf` (`8fba1cb5-…`) |
|---|---|---|
| extracted `document_pages` | 139 | 139 |
| `chunking_jobs` (status=`completed`, `failure_count=0`) | **6** (Feb–Jul 2026) | **2** (Apr, Jul 2026) |
| `rag_published_embeddings` count | **1,434** | **524** |

Chunks-per-job is nearly identical for both docs (1434÷6 ≈ 239, 524÷2 ≈ 262) — each individual chunking run produces a normal, consistent output. The 2.7× disparity in total published chunks tracks almost exactly with re-chunk *count*, not content or extraction differences (identical page counts, no failed jobs).

**Hypothesis (NOT verified against the actual publish code — flagging, not asserting):** each `chunking_jobs` completion may be *appending* a fresh full set of chunk rows to `rag_published_embeddings` rather than superseding/deleting the previous run's chunks for that `document_id`. If true, any document that's been re-chunked multiple times (re-triggered ingestion, repeated crawl re-detects, manual retry, etc.) accumulates redundant near-duplicate chunk rows over time — over-representing it in retrieval purely due to processing history, independent of actual relevance or content change.

**Impact if confirmed:** silently biases retrieval weighting fleet-wide for any doc re-chunked more than once — not just this pair. Also means `rag_published_embeddings` counts (which mobius-payor's new Usage history and duplicate-scan tooling both read) don't cleanly represent "how much content this doc has," complicating any chunk-count-based integrity check.

**Next steps:**
1. Whoever owns the chunking→publish path: confirm whether a new `chunking_jobs` completion for an already-published `document_id` deletes/supersedes the prior chunk set in `rag_published_embeddings`, or purely appends.
2. If it appends: decide whether to backfill-dedupe existing bloated documents, and fix the publish path to supersede going forward.
3. Worth an audit query fleet-wide: `count(chunking_jobs completed) per document_id` vs `count(rag_published_embeddings) per document_id` — outlier ratios flag other bloated docs beyond this one pair.

**Owner:** (unassigned — mobius-rag / whoever owns the chunk→publish write path)

---

### Bug #8: Classifier Refinement Backlog — Density Model, Match Precedence, Active-Learning Loop
**Component:** mobius-payor `app/classifier.py` / `app/source_run.py`
**Severity:** LOW (deliberately deferred, not urgent — logged per Ananth 2026-08-14: "keep refinement of this in log and we will come back to this")
**Reporter:** Payor Platform agent (2026-08-14), end of a real classifier-quality session on AHCA (5,257 docs) + Sunshine Health (529 docs)

**Context:** Built and validated a real train/test-split word-density model (TF-IDF + logistic regression, sklearn) as a scored signal for "is this a real payor governing document" — 95.4% held-out accuracy, 99.2% precision. This is a parked research direction, not wired into `classify()` — the free keyword layer + LLM fallback remain the live path. Four concrete follow-ups surfaced, none started:

1. **Match precedence for `_admin_exclude_match`:** it only runs when no taxonomy rule matched (`if not hits:` in `classify()`), so it structurally can't catch a taxonomy rule that matched *wrong*. Real confirmed instances sitting in the DB right now: `SH-PRO-PE-MFC-Training.pdf` → `state_contract`/high confidence (a staff training deck labeled a state Medicaid contract), `Training_Flyer_and_Registration_FL_DSH.pdf` → `useful_forms`/medium, `PHR Toolkit` → `benefits_summary`/medium, plus 2 more Opioid-Summit clinical-guidance docs → `benefits_summary`/`useful_forms`. Open question: should the admin-exclude filename check run *before* taxonomy matching so it can override a wrong hit? That changes precedence for every rule in `_RULES`, not just this list — needs a real decision, not a unilateral change.
2. **Payor as a model feature:** tested empirically (not just reasoned about) — adding a payor one-hot feature to the density model changed nothing on held-out accuracy (0.954 either way) but the payor coefficient did real work (AHCA -1.23, Sunshine +1.42), and known Sunshine false-positives got *worse* (CRAFFT screening tool 0.90→0.99). Root cause: AHCA is currently the *only* source of confirmed negative examples in the training pool, so "payor" became a leak for "which payor has negatives," not real payor-specific vocabulary. Revisit once Sunshine (or a third payor) has its own confirmed negative set.
3. **Forced-reason capture on manual reclassification (new idea, 2026-08-14):** when a user manually corrects a document's classification in the UI, require a reason, and mine those reasons back into the classifier the same way this session mined AHCA/Sunshine's unresolved buckets by hand. Ananth's framing: "this one thing about our job minimizes dependence, improves the latency, and can allow users to inherently import docs at speed." Not designed or scoped yet — needs a UI force-reason field, a storage location for the reason (`source_run_item.stages.classify` has a `method` field already; would need a `human_override_reason` alongside it or similar), and a periodic mining job to turn accumulated reasons into new rules/training data.
4. **Density model → Fact Store connection:** the explicit end goal named for all of this ("the classification is not the end game... use the good docs to feed the fact store") — not scoped. See [[project_payor_fact_store]] / [[project_payer_reference_data_store]].

**Next steps:** none scheduled — explicitly parked. Pick up when there's a slower day or once real Sunshine negative examples exist (unblocks #2).

**Owner:** (unassigned — Payor Platform agent, when resumed)

---

### Bug #9: `repopulate_corpus` LLM Classify Batch Freezes the Entire Server, Not Just the Request
**Component:** mobius-payor `app/llm_manager_client.py` (Vertex dev-fallback path) + `app/source_run.py::repopulate_corpus`
**Severity:** HIGH (confirmed live — any large keyword-fallback-to-LLM classify batch makes the whole app unusable for its full duration, not just slow)
**Reporter:** Payor Platform agent (2026-08-14), dispatched a real 2,786-doc LLM classify batch for AHCA (Ananth: "move to classify the first corpus entirely even if there are lot of fallouts")

**Repro:**
1. `POST /runs/{run_id}/repopulate` with `use_llm_fallback: true` for ~2,786 AHCA docs (sequential, one `classify_llm` call at a time by design).
2. ~1 minute in, `curl -m 25 http://localhost:8091/health` — a route with zero DB/LLM code — timed out with no response at all (`HTTP:000`).
3. Confirmed not a fluke: retried twice, same result. The running batch itself was still making real progress server-side (source_run_item rows updating every ~6s) — the server wasn't crashed, just completely unresponsive to any other request.

**Expected:** `classify_llm` → `llm.generate()` wraps the blocking Vertex SDK call in `loop.run_in_executor(None, ...)` (`app/llm_manager_client.py` line ~173) — this should let the event loop keep serving other requests (like `/health`) while one thread blocks on the Vertex network call.

**Actual:** It didn't. The whole event loop stalled for the batch's duration. `run_in_executor` is present in the code and looks correct on inspection — the mechanism SHOULD work, so the real cause wasn't identified live before this had to be killed. Leading suspects, none confirmed:
1. Something in the Vertex/gRPC client (`vertexai.generative_models.GenerativeModel`) doesn't release the GIL properly during its call, starving the loop even from inside the executor thread.
2. `uvicorn --reload`'s dev-mode process model (a watcher process + one worker) may only ever run one real worker handling all connections, with less isolation than assumed.
3. Something else in the request path (not yet located) makes a genuinely blocking call outside the `run_in_executor` wrap.

**Impact:** Confirmed real, not hypothetical — this happened live. Running any classify batch large enough to need real LLM fallback time (which is exactly what "classify the first corpus entirely" needs) currently means the whole mobius-payor app is unusable to anyone for the batch's full duration (would have been hours for 2,786 docs). The batch itself is safe to kill mid-run (each doc's `UPDATE` commits independently — killed at 120/2,786 done, zero corruption, real results preserved) but that's not a fix, just a safe abort.

**Next steps:**
1. Reproduce deliberately with a small batch (~10 docs) while watching `/health` and server CPU/thread state, to isolate which of the three suspects above is real.
2. Strongly consider not fixing this by hardening the in-process wrap at all — running a multi-hour LLM batch inside the API server's own request/response cycle is fragile by nature even if this specific freeze gets fixed. Moving large classify batches to a genuinely separate process (a standalone script, or a real job queue) would make this class of bug structurally impossible, not just rarer.
3. Until fixed, treat any `use_llm_fallback: true` batch above single-digit doc counts as something that will freeze the app for its duration — don't dispatch one without warning whoever might be using the UI at the same time.

**Owner:** (unassigned — Payor Platform agent, next time this is picked up)

---

### Bug #10: `documents.program` Doesn't Reliably Separate Product Lines Within a Payer
**Component:** mobius-payor `documents` table / classify pipeline (`program` column)
**Severity:** MEDIUM (silent, not a crash — a query can resolve against the wrong regulatory regime's document with no error)
**Reporter:** Payor Platform agent (2026-08-15), surfaced while building the Payor Fact Store's atomic layer with Appeals Agent, whose spec requires the fact key to include `product_line` (`docs/appeals/payor-store-handoff/06_ATOMIC_LAYER_SPEC.md` §2c — "the key is not `payer`, it's a tuple").

**Repro:** `SELECT DISTINCT payer, program FROM documents WHERE payer ILIKE '%wellcare%' OR filename ILIKE '%medicare%'` — several genuinely Medicare-branded documents (e.g. filename `"Medicare Advantage Plans"`, `payer='WellCare'`) are tagged `program='Medicaid'`. Distinct `program` values that exist in the corpus overall: `BehavioralHealth`, `Medicaid`, `Medicaid Behavioral Health`, `Medicare`, `NULL` — so the taxonomy has a real `Medicare` value, it's just not being applied consistently at classify time.

**Context (not itself the bug, but why this matters now):** Confirmed separately tonight that Sunshine Health (Centene's FL Medicaid MCO brand) and WellCare (Centene's FL Medicare Advantage brand) are stored as two distinct `payer` values, not one payer with two `program`s — so the specific "one payer's manual silently serves the wrong product line" failure Appeals hypothesized doesn't apply to this Sunshine/WellCare pair the way they assumed. But `program` tagging is still unreliable in general, which matters for any single payer that genuinely does carry multiple product lines under one `payer` value (ASO/self-funded plans in particular — per Appeals' catalog, these inherit the plan document's terms, not the payer's, and have neither a clean `product_line` nor `network_status`).

**Impact:** The Payor Fact Store's 7-dimension key (`payer, product_line, state, network_status, audience, appeal_level, predicate`) can't safely filter or dedupe by `program`/`product_line` metadata alone until this is fixed — eval_questions have to spell out the product line in the query text itself as a workaround (see the query template adopted 2026-08-15) rather than relying on corpus filtering.

**Next steps:**
1. Audit `program` classification rules against the real value set (`BehavioralHealth`, `Medicaid`, `Medicaid Behavioral Health`, `Medicare`) — find why Medicare-branded docs under `payer='WellCare'` are landing in `Medicaid`.
2. Decide whether ASO/self-funded needs its own dimension separate from `program`, per Appeals' catalog note.
3. Not urgent to fix before the Sunshine-only appeals pilot (query-text workaround holds), but blocks trusting `program` as a real filter for any payer with genuine multi-product-line documents.

**Owner:** (unassigned — Payor Platform agent, next time this is picked up)

---

### Bug #11: Corpus Contamination — Garbled Document Titles + Off-Payer Third-Party Content in Payer-Scoped RAG Results
**Component:** mobius-rag corpus (ingestion/naming + retrieval scoping) — not mobius-payor's own code, flagging for the owning team
**Severity:** MEDIUM (silent — no error, but wrong-payer content entering the evidence pool for a payer-scoped query is exactly the failure class the Payor Fact Store exists to prevent)
**Reporter:** Payor Platform agent (2026-08-16), surfaced while manually testing a Sunshine-Health-scoped question in mobius-chat's agentic mode and reviewing its cited sources list.

**Repro:** Ask mobius-chat (agentic mode) a Sunshine-Health-scoped question (e.g. "Sunshine Health provider complaint acknowledgment/resolution SLA") and inspect the `rag` tool's cited sources. Two distinct problems observed in one real result set:

1. **Garbled/hashed document titles.** Multiple cited sources have titles that read as base64/hash strings, not real document names — e.g. `"Auziyqffai57aluxrb7gzyjlpffegbjkd0k1cirqjizi1i8egkv4mvhzpqzmfj Pezvqqbwq0mbhkqouh Ksfxlvkuwm 1carj7w2..."`. Looks like a URL or encoded payload got used as the document title at ingestion time instead of a real, human-readable one. At least 4 distinct instances in one 15-source result set.
2. **Off-payer, third-party content retrieved for a payer-scoped query.** Two cited sources are generic third-party web content with no connection to Sunshine Health specifically: an "Insurance Timely Filing Calculator" tool page, and an "Insurance Appeal Deadlines 2026" blog post whose visible snippet explicitly discusses **UnitedHealthcare, Aetna, Blue Cross Blue Shield, Cigna, and Humana** deadlines — none of them Sunshine Health. Both were retrieved and presented as candidate evidence for a query scoped to Sunshine Health.

**Impact:** (1) is a real data-quality/UX problem (unreadable citations) but not directly dangerous by itself. (2) is more serious: if an LLM answer ever draws from the wrong-payer blog content without catching the mismatch, a Sunshine-scoped fact could silently cite (or be influenced by) another payer's real number — the exact "wrong counterparty, silently" failure class Appeals' own incident report described for the audience dimension, here showing up on the payer dimension instead. In the specific case observed, the final answer's actual number (3 business days / 60 days) traced to a genuine Sunshine Provider Manual source, not the off-payer blog — but the contaminating source was still in the evidence pool the model had to correctly discard, which it did this time, not by any structural guarantee.

**Next steps:**
1. Whoever owns crawl/ingestion: find why some documents got a hash/URL-string title instead of a real one — likely a crawler naming bug on a specific source type.
2. Whoever owns retrieval/gating: check whether payer-scoping (the same j-tag gate `facts.payor_fact` already uses) is being applied consistently to `corpus_search_agent`'s general RAG search, or whether ungated generic web content can enter the pool for a payer-scoped query.
3. Not urgent to fix before continuing Fact Store testing (this specific case resolved correctly), but worth fixing before trusting `citable: true`/high-confidence outputs from chat-mediated sourcing without a human spot-check.

**Owner:** (unassigned — flagging for RAG/Sourcing/Crawler, whoever owns corpus ingestion + retrieval scoping)

---

### Bug #12: No Document-Version Currency Signal — 18 Superseded Contract Versions Compete Equally With the Current One in Retrieval
**Component:** mobius-rag corpus (`documents.effective_date`/`termination_date` population) — not mobius-payor's own code, flagging for the owning team
**Severity:** MEDIUM-HIGH (silent — no error, but a stale contract version can win retrieval over the current one with no signal that anything is wrong)
**Reporter:** Payor Platform agent (2026-08-16), surfaced while sourcing AHCA's (FL Medicaid's regulatory authority) real appeal-deadline facts for the Payor Fact Store.

**Repro:** `SELECT filename, effective_date, termination_date FROM documents WHERE payer='AHCA' AND filename ILIKE '%core_contract%' OR filename ILIKE '%core contract%'` — 18 rows, one per historical version of AHCA's "Attachment II Core Contract Provisions" going back to 2019, including the current Oct 2025 version. Every single row has `effective_date` NULL and the exact same `termination_date` (2026-10-28, evidently a placeholder) — including versions explicitly superseded years ago (2019-02-01, 2020-02-01, 2020-07-01, 2020-10-01, 2021-10-01, 2022-02-01, 2022-10-01, April 1 2023). There is no data in the corpus distinguishing "this is the current contract" from "this was replaced 5 years ago."

**Impact:** Directly observed: a `corpus_search_agent` call asking about the real, current enrollee plan-appeal deadline (Attachment II Section VI.F, Oct 2025 version, confirmed present and fully embedded — 300 chunk_embeddings) returned 10 chunks, **zero of them from the correct Oct 2025 document**. One chunk came from the *2020-02-01* version of the same contract, at the wrong page, alongside unrelated STCs and provider manuals. The right answer (60-calendar-day enrollee appeal deadline, 5-business-day acknowledgment, 30-calendar-day resolution, citing 42 CFR 438.402/.406/.408) exists in the corpus and is fully searchable, but 17 near-duplicate historical variants of the same document dilute/outrank it with no recency signal to break the tie. This is a distinct failure mode from Bug #11 (off-payer contamination) — here every competing chunk is legitimately AHCA content, just from the wrong year.

**Workaround applied today:** For this round of AHCA appeal-domain facts, read the current document directly (not via RAG) and persisted the values with `basis='regulatory'` and honest sourcing noting the value was verified firsthand against the primary document, not RAG-retrieved. Not a scalable substitute for fixing retrieval.

**Next steps:**
1. Whoever owns ingestion: backfill `effective_date` for existing AHCA contract-family documents (the actual date is typically in the document's own title/first page — e.g. "UPDATE: OCTOBER 1, 2025").
2. Whoever owns retrieval: apply a recency boost or supersession filter (e.g. only the most-recent `effective_date` per document family/`authority_level='contract_source_of_truth'` group) — or at minimum surface `effective_date` to the LLM shaping the answer so it can prefer the newer citation when multiple versions appear in the same result set.
3. Likely affects every payer with a multi-year contract history, not just AHCA — worth checking whether other `contract_source_of_truth` documents have the same NULL/placeholder pattern before scoping the fix.

**Owner:** (unassigned — flagging for RAG/Sourcing, whoever owns corpus ingestion metadata + retrieval ranking)

**Corroborating datapoint (2026-08-16, via Fact Store §9 + Download agent):** independent of the 18-row
`documents`-table finding above, the *page-level* impact was confirmed on two specific rows. Two live
corpus documents with near-identical "Attachment II Core Contract Provisions Oct 2025" filenames:
`b5e32506-26d5-4d42-a8b8-4561bc788027` (261 pages — page 80 holds the correct current text, "sixty (60)
calendar days…") vs `ab0ba693-f020-4184-a4c9-ea1ce420ff6e` (255 pages — page 80 is unrelated Dental
Health Program content; the equivalent text lives on p75/p228 in this one). Same page number → different
content across the two, indistinguishable by filename. Downstream effect this bug enables: any
`source_ref`/citation pinned to `(filename, page)` without a `document_id` is silently ambiguous. Fact
Store has pinned its affected `payor_fact` row to `document_id=b5e32506…` as the interim fix; the durable
fix is still ingestion backfilling `effective_date` (+ dedup of the superseded family). Filed so the
ingestion owner has the exact two ids to reconcile.

---

## 🟡 IN PROGRESS BUGS

(None currently assigned)

---

## 🟢 FIXED BUGS (Verified Working)

### Bug: Pool Column Reference (`authority_level` → `document_authority_level`)
**Fixed:** 2026-07-24  
**Commit:** [retriever pool fixes](https://github.com/ananthlk/Mobius-Master/search?q=authority_level)  
**Verified:** 2026-08-11 (Retriever agent, live query traces)

### Bug: Tag-Coverage False Positive (4 → interpreted as 1.0)
**Fixed:** 2026-07-24  
**Details:** Raw tag count was being interpreted as [0,1] confidence score  
**Verified:** 2026-08-11 (live query calibration)

### Bug: Content Dedup Unreliable (content_sha mismatch)
**Fixed:** 2026-07-24  
**Details:** Switched from content_sha to normalized-text grouping  
**Verified:** 2026-08-11 (dedup accuracy spot-check)

---

## 📋 Bug Triage Template

When adding a new bug, use this format:

```markdown
### Bug #[N]: [One-line title]
**Component:** [which agent/service]
**Severity:** [CRITICAL/HIGH/MEDIUM/LOW]
**Reporter:** [who found it] ([date])
**Repro:** [steps to reproduce]
**Expected:** [what should happen]
**Actual:** [what happens instead]
**Impact:** [why it matters]
**Root cause hypothesis:** [best guess at why]
**Next steps:** [investigation checklist]
**Owner:** [who's taking it]
```

---

## 📊 Stats

| Status | Count |
|--------|-------|
| Open | 8 |
| In Progress | 0 |
| Fixed | 3 |
| **Total** | **11** |

---

**Last updated:** 2026-08-14 by Payor Platform agent
**Next review:** When new bugs reported or weekly triage pass
