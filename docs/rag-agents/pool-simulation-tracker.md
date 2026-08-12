# POOL — Calibration & Sign-Off Tracker

**Live status, updated in real time** — same discipline as Gate/Reformat/Structure.
**Spec under review:** `pool-schematic-spec.md`

---

## EVAL Sign-Off (2026-07-23)

**✅ POOL SCHEMATIC IS SOUND.** All three calibration asks addressed.

### Ask 1: BM25 before/after calibration frame

**Verdict:** YES, "legacy strategy-a BM25 numbers" is the right baseline. But expand to answer the full question:

**Calibration frame:**
- **Before:** Legacy strategy-a (BM25 ranking on narrowed doc pool) on cmhc bank (26 queries, same as Gate/Reformat/Structure) → recall, precision, latency
- **After:** Pool's new strategy-1 (tag-coverage-maximizing selection on same pool) → same metrics
- **Union test (critical):** Does Pool's union (tag-select + vector + inherited, deduped, neighbors) **exceed** legacy strategy-a baseline?

**Acceptance criteria:** 
- Union >= strategy-a baseline - 0.01 → PASS
- Baseline - 0.02 <= union < baseline - 0.01 → INVESTIGATE
- Union < baseline - 0.02 → REGRESSION, requires fix

---

### Ask 2: Tag-only v1 (no literal-anchors/untagged-tokens)

**Verdict:** ✅ **Option (a) — tag-only v1 is CORRECT.**

**Reasoning:**
- Literal anchors are important but rare (most queries don't have them)
- Untagged meaningful tokens are a precision boost, not a recall blocker
- Re-deriving legacy regex/heuristics risks inheriting bugs in a new context
- Gate never computed these, so Pool v1 shouldn't invent them — honest gap, fast-follow enhancement
- Matches Shape's pattern: UNCLEAR handling deferred, literal/untagged now deferred

**Eval gate:** Once v1 ships, measure queries where literal anchors or untagged tokens are the deciding factor. 
- If recall lift >5% → prioritize option (b)
- If <2% signal → leave as backlog

---

### Ask 3: NUMBER-MOVING calibration plan for whole Pool

**Verdict:** ✅ **Pool is entirely new code; use cmhc contour bank (26 queries) as baseline.**

**Frame:** Pool is the first entirely-new module in the pipeline (Gate/Reformat/Structure refactored existing logic; Pool builds new code). Baseline must reflect this: measure Pool's union-based approach against legacy single-strategy strategy-a, both consuming Gate's structured output.

**Calibration bank:** cmhc contour bank (26 queries)
- Same queries as Gate/Reformat/Structure calibration (consistent dataset)
- Exercises all postures (PRECISE/FAN_OUT/RELY_ON_EXTERNAL)

**Per-query measurements:**
- `pool_recall`: How many golden answers are in the pool? (aim high: >0.85+)
- `pool_precision`: What % of pool candidates are relevant/on-topic? (expect low: 0.30-0.50, acceptable by design — Fillers' job to extract precision)
- `strategy_1_only_recall`: tag-coverage selection alone
- `strategy_2_only_recall`: vector search alone
- `strategy_3_only_recall`: inherited authority alone
- `union_before_neighbors`: deduped union
- `union_after_neighbors`: final (what Fillers receives)
- `baseline_strategy_a`: legacy numbers
- `neighbor_delta`: recall gain from neighbor expansion

**Forced-arm discipline (NUMBER-MOVING mandatory):**
- Run WITHOUT routing optimization (Router doesn't exist yet)
- Measure raw "recall availability from Pool" signal
- **Pool's job: maximize recall (get all potential answers), accept low precision (include noise)**
- **Fillers' job: find precision within the noisy pool (figure out which candidates fill slots well)**
- Acceptance criteria:
  - Pool recall >= baseline - 0.02 (aim high: >0.85+)
  - Pool precision expected low (0.30-0.50 acceptable by design)
  - No regression from legacy baseline in recall coverage

**Build-phase calibration (NOT pre-locked):**
- Per-strategy width multipliers (`breadth × N`): Measure during build, find knee (diminishing returns), lock there
- Gate (i) impact: Measure chunk-level tag filtering recall lift if/when DB resolves it (>3% = prioritize)
- Neighbor-expand validation: % duplicates caught, % recall gain, provenance dict round-trip

---

## Cross-agent sign-off status (Gate/Reformat/Structure precedent)

| Collaborator | Status | Notes |
|---|---|---|
| Chat | ✅ **Signed off** 2026-07-23 | PUBLIC-only-v1-via-`SourceAdapter`-seam confirmed correct against real corpus_search→Pool path. `PoolCandidate` shape confirmed sufficient (Chat's own normalizer decouples vocab). |
| UX | ✅ **Signed off** 2026-07-23 (4/5) | All 3 items cleared, including escalating the seam ARCHITECTURE to Ananth directly (confirmed, plug-and-play requirement now spec §3.0). |
| DB | ✅ **Signed off** 2026-07-23 | Gate (i) resolved: GIN-index `chunk_{d,p,j}_tags`. Migration not yet landed as of build; built to the pattern per DB's own instruction, verified live the bounded query never seq-scans regardless (see Build status below). |
| Eval | ✅ **Signed off** 2026-07-23 | All three calibration asks addressed above. Tag-only v1 correct, BM25 before/after against strategy-a is right frame, NUMBER-MOVING on cmhc bank is right discipline. |
| TECH | ⏳ Pending | Was holding full close on Eval's tag-only-v1 answer — that dependency is now cleared (Eval's verdict above). `segment_ms` split (`doc_narrow_ms`/`tag_select_ms`) applied per their earlier clarification. Structural review of the actual build (gates b/d/e/i) still outstanding. |

**4/5 signed off. TECH's one stated dependency (Eval's tag-only-v1 read) is now resolved — expecting TECH to close on structural review of the real build below.**

---

**Build phase underway — see "Build status" below for real files/tests/bugs-found, not just spec status.**

---

## CRITICAL MEASUREMENT GATE: Pool as ceiling for downstream

Once Pool ships, its `oracle_recall` becomes the **ceiling for all downstream modules** (Fillers, Synthesis, final answer). This is Eval's way to measure pipeline losses:

**Pool oracle_recall** → Fillers → Synthesis/final answer

**What this tells us:**
- **Pool recall/precision split (by design):** Pool intentionally maximizes recall (get all candidates, accept noise); Fillers extracts precision (figures out which candidates fill slots)
- **Path-specific signal:** Which retrieval paths (tag-select vs vector vs inherited) contribute most to recall? Which introduce most noise?
- **Fillers effectiveness:** Given Pool's noisy candidate set, how well does Fillers find the good candidates?
- **Fillers→final delta:** Is synthesis/formatting degrading the filled answer?

**Calibration implication:** cmhc bank runs should measure:
1. `pool_recall`: How many golden answers are in the selected pool? (acceptance: >0.85+, or >= baseline - 0.02)
2. `pool_precision`: What % of pool candidates are relevant? (expect low: 0.30-0.50, acceptable by design)
3. `pool_noise_ratio`: How much junk is Fillers inheriting? (strategy-specific — which paths are noisier?)

**This is the real test:** Pool's union should be big enough, diverse enough, that Fillers has all the pieces to fill slots. High recall + accepted low precision is the design:
- If pool_recall < 0.85 on cmhc → Pool's retrieval needs work or corpus has gaps
- If pool_recall is high but Fillers can't fill slots → Fillers design needs work, not retrieval
- If pool_precision is extremely low (< 0.20) → too much noise; may need to tune strategy weights or filtering thresholds before Fillers



**Also noted:** Stale citation fix in `retriever-meet-old-plan.md` (neighbor-expand is `_expand_with_neighbors() :3079` now, not `:2560`/`:2210`/`:2553`). Any eval-bank line references will use current anchors during build.

---

## Build status — 2026-07-23

**Files:**
- `app/services/retriever/pool/contracts.py` — `ScopeContext`, `PoolCandidate`, `PoolResult`, `SourceAdapter` ABC (4 methods: `tag_select`/`vector_search`/`inherited`/`neighbors`, each returns `(candidates, segment_ms)`).
- `app/services/retriever/pool/dedup.py` — pure union/dedup (id then content-hash), Pool's actual novel contribution.
- `app/services/retriever/pool/public_adapter.py` — `PublicSourceAdapter`, the only adapter built in v1. Reuses `partition_terms`-equivalent tag classification (tag-only, §4.1), `build_candidate_pool()`'s cascade, `_inherited_authority_doc_ids()`, `_expand_with_neighbors()` — all imported from legacy, not reimplemented.
- `app/services/retriever/pool/pool.py` — orchestrator: `run_pool_for_query()` (one rewritten_query) + `run_pool_fanout()` (up to 4, concurrent via `asyncio.gather`).
- `tests/test_pool_dedup.py` — 9/9 passing, pure unit, zero DB.
- `tests/test_pool.py` — DB-integration against live dev data, real `run_gate()` + real `PublicSourceAdapter`. 9/9 pass individually (added a 9th, see below); 3 fail only when run in the same pytest session as other suites, on a **pre-existing** `asyncpg`/pytest-asyncio event-loop-sharing artifact — confirmed the same failure independently reproduces on `test_shape_reformat.py`'s existing DB-integration tests too when run back-to-back, not something Pool introduced; flagging for whoever owns test infra rather than fixing shared `pytest.ini`/`conftest.py` unilaterally.

**Additive `bm25_score` field, 2026-07-23 (Filler a request, Retriever-confirmed):** Fillers can't make DB calls (gate b), so Filler a (BM25, session "4d - BM25") asked Pool to supply `ts_rank_cd(search_vec, plainto_tsquery('english', :query), 32) AS bm25_score` on every `PoolCandidate`. Caught and corrected a technical error in their initial ask before implementing: raw `to_tsquery(...)` throws on real user text (strict parser, chokes on punctuation) — `plainto_tsquery` is what legacy's actual production BM25 path uses, confirmed against `corpus_search.py`. Computed for every match candidate regardless of source arm (tag_select/vector/inherited all now select it); `None` for neighbors per Retriever's explicit decision (they weren't retrieved by any term match, same "None = no signal" convention `score` already established). Threaded `query` into `tag_select()`/`inherited()` ABC signatures (previously didn't need it). New regression test `test_bm25_score_present_on_matches_none_on_neighbors` — passes.

**Additive `query_embedding` field, 2026-07-23 (Filler s / Payor Platform request, Retriever-relayed):** claim was that `gemini-embedding-001 @ output_dimensionality=1536` exactly matches the Payor Fact Store's own schema, so Filler s should reuse Pool's already-computed query embedding instead of a second redundant embed call. **Independently verified before implementing, not taken on trust** — checked `mobius-payor/migrations/006_payor_fact_store.sql` (`vector(1536)`) and `mobius-payor/app/fact_embed.py` (`output_dimensionality=1536 (explicit; model default 3072 — the gotcha)`) directly, then confirmed live that Pool's own embed path (`EMBEDDING_DIMENSIONS` config, default 1536) actually produces a 1536-length vector matching `rag_published_embeddings.embedding_vec`'s real column typmod. Claim checked out. `SourceAdapter.vector_search()` now returns a 3-tuple (`candidates, segment_ms, query_embedding`) instead of 2; `PoolResult.query_embedding` populated from it, `None` when the vector arm never ran (zero-breadth postures) or embed failed. New tests `test_query_embedding_exposed_for_reuse` + `test_none_when_vector_arm_never_runs` — pass; full orchestrator chain re-verified live end-to-end after the signature change (602 candidates, 1536-length embedding, no regressions).

**Status update, same day: DEPRIORITIZED on the consumer side, not reverted here.** Filler s found reuse isn't a monotone fix — the Payor blend formula rescales entirely once `query_embedding` is present, risking silently dropping currently-good fact-store serves below threshold. Needs to ship bundled with an α/β/τ re-sweep, not independently. Filler s is proceeding v1 tags-only (matches legacy's calibrated behavior exactly) and will consume this field in a later fast-follow bundle. **Pool's side stays as-built** — the field is additive and `None`-safe, nothing forces consumption, no code change needed here; just noting it's currently unused downstream.

**Two real bugs found verifying against live data, both fixed:**
1. **`jsonb_object_keys()` crash on JSON-null literals.** `chunk_{d,p,j}_tags` stores an actual JSON `null` value (not SQL NULL) on ~55k rows (verified via `jsonb_typeof` grouping) — `COALESCE(col, '{}'::jsonb)` doesn't catch it, `jsonb_object_keys('null'::jsonb)` throws `InvalidParameterValueError`. Fixed with `COALESCE(NULLIF(col, 'null'::jsonb), '{}'::jsonb)`.
2. **`_expand_with_neighbors()` silently truncates seeds, not just skips neighbors, when seed count exceeds its shared `_NEIGHBOR_TOTAL_CAP=50`.** Live run on a real cmhc query produced 378 unioned candidates; passing all 378 as "seeds" returned `kept=-328` — 328 of Pool's own real matches were silently dropped, not just denied neighbor context. That function was built for legacy's small post-rerank result set, not Pool's wide over-fetched union. Fixed in `pool.py` — only a bounded, per-arm-interleaved top-N (`_NEIGHBOR_EXPANSION_CAP=24`, comfortably under the shared cap) goes to neighbor expansion; the rest of the union survives untouched (still counts for recall, just without sibling context). Reused `_expand_with_neighbors()` itself verbatim, per the no-restructure decision — the fix is entirely in how Pool calls it, not inside the shared function.
   - Also caught and fixed a related second-order dup: a neighbor of the bounded seed set can collide with a chunk already present in the untouched remainder (independently matched by another arm) — `_expand_with_neighbors()` only dedupes against the seeds it was given, not Pool's full union. Added a final `dedup_candidates()` pass after combining `expanded + remainder`.

**Verified live (EXPLAIN ANALYZE):** the chunk-level tag query (`document_id = ANY(:doc_ids) AND chunk_d_tags ?| :codes`) uses `Bitmap Index Scan on idx_rpe_document_id_para_page` — bounded, 0.277ms execution — confirmed NOT a blind scan of the 1.94M-row table even though the GIN migration on `chunk_*_tags` hasn't landed yet, because document-id narrowing (step 2, cheap/GIN'd `document_tags`) always bounds it first.

**Sample real run** (cmhc001, "timely filing deadline for Sunshine Health FL Medicaid claims"): 403 candidates (tag_select=86, vector=191, inherited=100, neighbor=26), all three strategies contributing, `pool_ms≈6.1s` (dominated by `embed_ms≈5s` — consistent with the "embed calls are the expensive resource, not k" cost model from Ananth's design conversation), zero duplicate chunk_ids, every segment timed (`doc_narrow_ms`/`tag_select_ms`/`embed_ms`/`vector_ms`/`inherited_ms`/`dedup_ms`/`neighbor_ms`).

**Not yet done:** eval-bank before/after calibration against the cmhc 26-query bank (blocked on TECH's final structural close, then real calibration run), FAN_OUT theme-level multi-query test against a real FAN_OUT posture query, `inherited()`'s "no payor tag → AHCA substitution already happens in tag_select's own cascade, not here" behavior verified only via the doc-level cascade's existing logic — not yet independently pinned with its own test showing L3_AHCA_D/L4_AHCA actually firing.

---

## Real bugs found + fixed via Payor-Policy's live full-pipeline trace, 2026-07-23

**3. `bm25_score` was silently broken for nearly every real candidate — flat 0.0, not the meaningful ranking signal Filler a was told they had.** Root cause: `plainto_tsquery('english', :query)` AND-joins every content word in the raw natural-language question (verified: an 8-content-word query produced `'time' & 'file' & 'deadlin' & 'sunshin' & 'health' & 'fl' & 'medicaid' & 'claim'`). Legacy's own production use of `plainto_tsquery` is as a WHERE-clause FILTER on an already-narrowed BM25 candidate set (only chunks matching every term are selected at all) — an AND-query is correct there. Pool's use is different: ranking an ARBITRARY candidate set chosen by tag/vector/inheritance, never filtered by full-text match — an AND-query is nearly always false against that set. Confirmed live: **0/581 real candidates scored nonzero** before the fix. **Fix:** convert `plainto_tsquery`'s AND-tsquery into an OR-tsquery via `to_tsquery('english', replace(plainto_tsquery(...)::text, ' & ', ' | '))` — reuses Postgres's own stemming, just swaps the boolean operator. Verified live post-fix: **437/581 candidates now score nonzero**, top-ranked chunks are genuinely relevant ("To send claims electronically to Sunshine Health...", 0.85). Regression test strengthened (`test_bm25_score_present_on_matches_none_on_neighbors` now asserts >10 nonzero scores, not just "not None" — the original test would have passed even at 0/581, a real gap in my own coverage).

**4. `inherited()` had no ORDER BY at all — an arbitrary DB-scan-order slice, not a relevance-ranked one.** This is the actual mechanism behind the reported "unrelated Early Intervention Services doc in top candidates" — confirmed via arm breakdown: 11/12 EI candidates were `source_arm=inherited`, 0 from `tag_select` (ruling out cascade-fallback contamination the report worried about). `inherited()` already computed `bm25_score` per chunk but never used it to order results — just `LIMIT :width` (200) across up to 5 AHCA-inherited documents in whatever order Postgres happened to scan them. **Fix:** added `ORDER BY bm25_score DESC` now that the score is real (fix #3 above) — inherited chunks that actually relate to the query surface first when width truncates. Verified live: top inherited chunks now score 0.63-0.66 (genuinely on-topic FL Medicaid/claims content), EI still appears (14/195, now ranked #3 with a legitimately-earned 0.63, not noise) — this is a real, honest relevance-threshold question for Eval/calibration now, not a broken/unordered-noise bug anymore.

**5. Known gap, not fixed (tied to port-don't-import backlog):** neighbor candidates have `source_type=None`/`document_status=None`/`tags={}` — confirmed via live check. Root cause: legacy's `_fetch_sibling_chunks_batch()` SELECT never fetches those columns at all (verified: its full column list is id/document_id/text/page/paragraph/section/chapter/summary/content_sha/document_display_name/document_filename/document_authority_level/document_payer/document_state — no source_type, no document_status, no chunk tags). Properly fixing this means either an extra backfill query or owning the neighbor-fetch SQL directly — better done when the "port, don't import" backlog item ports this function into Pool's own module, not as a patch on top of a legacy function slated for replacement. Documented here so it isn't lost, not patched now.

**All fixes verified with the full test suite individually passing (no regressions), live-verified against Payor-Policy's exact repro query.**

---

## Expansion-phrase regression restored, 2026-07-23 (Ananth's finding, verified against legacy)

**6. `GateResult.expansion_phrases` was computed by Gate and read by nothing downstream — a real, confirmed regression from legacy.** Legacy's actual production BM25 (`corpus_search.py:943`) OR-joined raw query tokens with Gate's lexicon-derived expansion phrases: `_build_or_tsquery(*raw_tokens, *expansion.expansion_phrases)` — each phrase its own AND-group, groups OR'd together. Confirmed via grep: `expansion_phrases` (`shape/gate.py:319`, stored on `GateResult`) has zero read-sites in `reformat.py`/`pool.py`/any filler. **Fix:** threaded `expansion_phrases` through `run_pool_for_query()` → all three `SourceAdapter` methods (`tag_select`/`vector_search`/`inherited` — all three compute `bm25_score`, all three needed it) → folded into `_BM25_SCORE_EXPR`'s tsquery via `string_agg` of per-phrase `plainto_tsquery` OR-joined with the raw-query OR-tsquery, relying on Postgres's own `&`-binds-tighter-than-`|` precedence so no explicit parens are needed. This is newly-written SQL, not an import from legacy's `_build_or_tsquery`/`_phrase_to_tsquery_term` — consistent with "port, don't import" for anything touched from here on, not just the backlog item.

Verified live against the real 33-phrase expansion set for the repro query (including OCR-noise entries like "cafi orida" — no SQL errors): **577/577 candidates now score nonzero bm25** (up from 437/581 pre-expansion-phrase-fix), confirming genuinely broader, more comprehensive matching. **Honest nuance, not oversold as a pure win:** the specific "180 days" answer chunk's absolute bm25 score is unchanged (0.767), but its RELATIVE rank shifted from 13→24 among all matches — broadening the match set via expansion phrases lifted many other generic claims/billing/medicaid-adjacent chunks too, so the specific answer's rank moved down even though nothing about its own relevance didn't change. This is expected/correct behavior for restoring a broader-recall signal, not a bug, but worth Eval/calibration knowing rather than just claiming "bigger number, better."

---

## 7. `required_phrases`/`boosted_phrases` — Filler A's meta_boost input, 2026-07-23

**Deeper root cause of the 13→24 dilution, found by Retriever:** expansion_phrases had no selectivity weighting at all — legacy's `selectivity_for_tag()`/`partition_terms()` (REQUIRED sel>=0.65 / BOOSTED 0.40-0.65 / DROP<0.40) never survived into the new pipeline either. Verified live this is fully reconstructable within Pool with zero Gate contract changes: the phrase↔code link exists at lexicon-match time (`expand_query_via_lexicon` appends a matched entry's phrases alongside its `full_code`) but is flattened away by the time it lands on `GateResult.expansion_phrases`. Rebuilt via `_load_lexicon_snapshot()` (cached, public table) + the already-imported `selectivity_for_tag()`.

**Shape confirmed directly against Filler A's actual production code** (`filler_a.py`, read directly — not just relayed): `_compute_meta_boost_score(text, tags, required_phrases, boosted_phrases)` reads `list[tuple[str, float]]` via `getattr(pool_result, 'required_phrases', None)`, computing `present_weight` (REQUIRED full weight, BOOSTED × 0.5) over `total_weight`. Their code was already written against this exact shape and was silently scoring 0 meta_boost until this field existed.

**Built:** new `SourceAdapter.phrase_buckets()` ABC method (adapter-owned, since selectivity is corpus-specific — same reasoning as `tag_select`'s own REQUIRED/BOOSTED/DROP bucketing), implemented in `PublicSourceAdapter`, wired into `run_pool_for_query()`'s concurrent `asyncio.gather` (4th independent DB-touching task alongside tag_select/vector/inherited), populating new `PoolResult.required_phrases`/`boosted_phrases` fields.

**Verified live against the repro query:** `required_phrases` = timely_filing/sunshine_health cluster (sel 0.93-0.94); `boosted_phrases` = claims/billing/florida/submit cluster (sel 0.41-0.61); bare DROP-bucket terms excluded correctly. **A subtlety caught in my own test, not the code:** "claims" legitimately appears in `boosted_phrases` (not excluded) because it's ALSO a phrase for `d:claims.general` (BOOSTED, sel=0.606), a separate, more-selective code from bare `d:claims` (DROP, sel=0.0) — my max-selectivity-across-codes resolution correctly promotes it. My first test draft wrongly assumed "claims" should be excluded everywhere and failed; fixed the test's wrong assumption rather than weakening the code.

**0.7/0.3 tsquery-combination weighting (Retriever's earlier proposal for reweighting bm25_score's own tsquery) explicitly NOT built yet** — flagged as needing Ananth/Eval calibration sign-off first, not to be hardcoded as a guess. `required_phrases`/`boosted_phrases` (this section) are a SEPARATE, independent deliverable that unblocks Filler A's meta_boost regardless of whether/when the tsquery-reweighting lands.

Test added: `test_phrase_buckets_exclude_drop_and_shape_matches_filler_a` — passes. Full suite re-verified individually, no regressions.

---

## 8. Vector-arm HNSW ef_search bug, found by Filler b (Vector search), fixed 2026-07-23

**Real bug, confirmed live before fixing:** `app/database.py` sets `hnsw.ef_search=100` as a connection-level default (tuned for legacy's k=80 wide-phase search). Pool's `vector_search()` LIMIT (`width`) runs up to `breadth*VECTOR_WIDTH_MULTIPLIER(100)` — 1000 for a typical breadth=10, **10x** what ef_search=100 explores during HNSW graph traversal. Filler b's repro, independently re-verified: at ef_search=100, the TRUE best semantic match for the Sunshine Health timely-filing query (sim≈0.889, literally the "180/365 days" answer chunk) was **completely absent** from the top-1000 results — HNSW doesn't just return fewer good matches when under-provisioned for a wide LIMIT, it backfills with genuinely worse ones while silently never exploring far enough to find the true nearest neighbors. Raising ef_search to 500/1000 surfaced that chunk at rank 4/3.

**Also confirmed:** legacy already knew about this class of problem — `corpus_search.py`'s `over_fetch_factor` mechanism (comment: "cheap insurance against HNSW tie-crowding") does `k*8` over-fetch + `min_similarity` post-filter. Pool's fresh-built `vector_search()` never ported that defense forward — a real gap from building fresh rather than porting the specific mitigation.

**Fix:** `SET LOCAL hnsw.ef_search = min(max(width, 100), 1000)` immediately before the vector query, in the same transaction/session. Verified live: `SET LOCAL` does NOT accept SQLAlchemy bind parameters (Postgres syntax restriction, confirmed directly — throws `syntax error at or near "$1"`) — safe to interpolate the int directly since `width` is internally computed, never user text. Capped at 1000 as a defensive query-cost ceiling, not because Postgres rejects higher values (it doesn't — confirmed live it accepts up to at least 1500 without erroring).

**Verified live post-fix:** the true best match (sim=0.8865) now appears, correctly ranked #1 by similarity, up from completely absent. **Latency, measured honestly (not just the win):** a cold first call showed 7335ms (dev-DB-proxy cold-start artifact, consistent with the known "restart proxy after long uptime" gotcha — not representative), but repeated steady-state trials show a real, moderate cost: ~330-370ms at ef_search=100 vs ~450-540ms at ef_search=1000 for width=1000. Worth the correctness gain (missing the true answer entirely vs. ~100-200ms added latency), but not free — flagging honestly rather than only reporting the fix.

Test added: `test_vector_arm_ef_search_matches_width` — passes. Full suite re-verified, no regressions.

## BACKLOG: "Port, don't import" — Ananth directive 2026-07-23

**Not urgent-today, but tracked with the same seriousness as any other production-readiness gap.** `public_adapter.py` currently has live imports pointed at the legacy files instead of owning the logic:
- From `corpus_search.py`: `_embed_with_cache`, `_expand_with_neighbors`
- From `corpus_search_agent.py`: `_SELECTIVITY_BOOST`, `_SELECTIVITY_REQUIRED`, `_inherited_authority_doc_ids`, `build_candidate_pool`, `selectivity_for_tag`, `TermAssignment`, `TermPartition`

**Why:** (1) Pool shouldn't depend on those old files continuing to exist/not change underneath it, (2) porting is a real re-verification opportunity — re-test each piece against live data as it moves, don't copy-paste and inherit whatever latent bugs already exist in the old code (same discipline that already caught 2 real bugs during the original build).

**Scope when done:** move each function's actual implementation into a Pool-owned module (not a re-export), bring its existing tests along or write new ones if thin, re-verify against the live dev DB the same way the original build was verified (not just import-checked). Report back per-function what was verified, not just "ported."

---

## 9. Cross-payer contamination — real correctness bug, found by Payor-Policy, fixed 2026-07-23

**Confirmed live before fixing, not taken on the report's word:** `vector_search()` had ZERO payer/jurisdiction filtering — a bare similarity search over the entire 1.94M-row corpus, unlike `tag_select` which scopes via `build_candidate_pool()`. Independently reproduced: for "How do I submit a corrected claim to Sunshine Health Florida?" (Gate correctly matches `j:payor.sunshine_health`), 10 candidates in the top-1000 were tagged ONLY with `payor.aetna` or `payor.molina_healthcare` (no Sunshine/Centene co-tag), scoring 0.77-0.81 similarity — genuinely different payers' claims-resubmission policies surfaced as if relevant to a Sunshine-specific question. This is a correctness issue (wrong-payer content shown as fact), not a recall/precision tradeoff.

**Fix: negative exclusion, not a positive scope filter.** Threaded `j_codes` into `vector_search()`'s signature (new 3rd positional param). When the query names a specific payer (`j_payors` non-empty), the SQL excludes chunks whose `chunk_j_tags` contains ANY OTHER `payor.*` key — but chunks with NO payor tag at all (generic/AHCA-authority content) still pass through untouched, preserving vector's wide semantic-discovery character. A query with no matched payer tag gets no exclusion at all (`CAST(:j_payors AS text[]) = '{}'` short-circuits).

**Verified live post-fix:** 0/1000 cross-payer candidates (down from 10), 607 no-payor-tag candidates still present untouched.

**A real test-writing mistake caught and fixed, not the code:** my first test draft flagged `payor.hmo_plan` as a "wrong payer" — investigated directly via SQL rather than assuming, and found `payor.hmo_plan` is a **D-tag** (content about HMO plans generally), not a J-tag payer identity, despite sharing the "payor." prefix. `PoolCandidate.tags` merges d/p/j tag namespaces into one flat dict, losing provenance — my test checked that flattened dict and mistook a domain tag for a competing payer. The SQL fix itself only ever checked `chunk_j_tags` (correctly) and was never affected. Fixed the test's assumption, not the SQL.

**Note found along the way, not yet acted on:** `pool.py` had drifted significantly since this module's last edit here — another session added `content_quality.py` (TOC/leader-dot noise filtering), a D-only `bm25_phrases` restriction for the tsquery input (separate from the full-scope `required_phrases`/`boosted_phrases` Filler A still gets), and per-FAN_OUT-theme gate substitution (`_gate_for_theme`). Integrated the `j_codes` threading around this cleanly without touching any of that work; flagging its existence here for the record since it wasn't something I built or reviewed line-by-line.

Tests added: `TestCrossPayerExclusion` (3 tests — contamination absence, generic-content passthrough, no-payer-query no-op). Full suite re-verified individually (13+ tests), no regressions.

---

## 10. Junk-string exclusion — investigated, declined to ship, referred to Curation/DB (2026-07-23)

**Real, evidenced corpus problem, not disputed:** Filler b found single-string boilerplate chunks (scraped AHCA nav menu, PDF-viewer/download prompts, state-fiscal-year headers, a templated multi-state family) crowding vector search results — `"-"` alone appears 185,261 times corpus-wide, confirmed independently. Real degradation, real mechanism (near-empty low-information text can embed close to many query vectors).

**Three successive attempts at a safe fix, all declined, in order:**
1. Tag-emptiness heuristic — rejected earlier (not detailed here, predates this thread).
2. Frequency+eyeball ("60 confirmed junk strings, count>=20/length<=40, manually inspected, no ambiguous cases") — I independently re-ran the described scan myself rather than transcribe the list, and got 2,722 distinct strings / 788k rows, not 60/279k. Root cause (found by Filler b themselves, self-reported): their query had `LIMIT 60`, so they'd validated the top-60-by-frequency slice of a set whose true size they never saw — not a validated threshold at all. My fuller scan surfaced clearly legitimate, potentially-correct-answer content mixed in with real junk: `"Veterans Crisis Line"`, `"988 Suicide & Crisis Lifeline"`, `"Buprenorphine Practitioner Locator"`, dollar figures, named hospitals — all real, specific, repeated-but-legitimate content that a frequency-based rule would have silently excluded.
3. Hand-curated micro-list (AHCA nav-menu family + PDF-viewer prompts only, the most zero-ambiguity subset) — Filler b proposed this as a possible stopgap but explicitly recommended against it too, given they'd just gotten the "confirmed" list wrong once already the same day and no longer trusted their own eyeballing.

**Decision: ship nothing today.** Not because the narrowest version (3) is necessarily unsafe on its own merits, but because this is the third progressively-narrower version of the same idea in one session, and that pattern is itself the signal — this class of problem keeps looking safe-enough until the next pass finds a gap. Real fix belongs in Curation/DB as content-quality/dedup infrastructure (tag known-boilerplate chunks at ingest, or dedupe near-identical short chunks corpus-wide), not as a progressively-narrower retrieval-layer patch. Logged here with the real data (mechanism, example strings, occurrence counts) so the investigation isn't lost even though nothing shipped.

---

## 11. Dedup provenance-loss bug — real structural fix, found by Retriever, fixed 2026-07-23

**Real, non-one-off bug, confirmed via direct code inspection before fixing:** `dedup_candidates()` is first-arm-wins on chunk_id collision (union order `[*tag_candidates, *vector_candidates, *inherited_candidates]`). If a chunk is independently found by BOTH `tag_select` and `vector_search`, the surviving deduped entry keeps `tag_select`'s provenance/score — any filler that filters to `source_arm=="vector"` (Filler b's `fill_shape_vector`) never sees that candidate at all, even when `vector_search` independently found the identical chunk with a strong similarity score. Retriever's concrete evidence: a correct-answer chunk in the pool tagged `source_arm=tag_select`, while a standalone `vector_search()` call found the same chunk at rank 165/1000, similarity 0.823.

**Why not a trivial "just remove Filler b's filter" fix:** `PoolCandidate.score` is arm-overloaded — `tag_select`'s `.score` is a raw coverage COUNT, vector's is cosine similarity, inherited's is `None`. Reading `.score` as a similarity value for a non-vector-arm candidate would be a worse bug than today's.

**Fix: new `SourceAdapter.attach_vector_similarity()` method**, mirroring the `bm25_score` pattern (a signal computed for every candidate regardless of which arm's provenance survived dedup, not just one arm's own results). One batch query, post-union+neighbor-expansion, against the final candidate id set, reusing the query embedding Pool already computed once — `SELECT id, 1 - (embedding_vec <=> :qv) AS similarity FROM rag_published_embeddings WHERE id = ANY(:ids)`. New `PoolCandidate.vector_similarity` field. Unlike `bm25_score` (`None` for neighbors — no term-match reason to be in the pool), similarity is meaningful for ANY chunk with an embedding regardless of why it's in the pool, so this is populated for neighbors too, not just matches. No-ops cleanly when `query_embedding` is `None` (embed failed, or vector arm never ran for a zero-breadth posture).

**Verified live:** 178/178 tag_select-provenance candidates and 26/26 neighbors got real `vector_similarity` attached on the repro query; highest similarity among tag_select-provenance candidates was 0.8334 — a genuinely strong match that would have been invisible to any filler restricted to `source_arm=="vector"`. Cost: one extra DB round-trip, measured at ~2.1s on this query (real, not hidden) — segment timed as `vector_similarity_ms`.

Test added: `test_vector_similarity_attached_regardless_of_provenance`. Full suite re-verified individually, no regressions.
