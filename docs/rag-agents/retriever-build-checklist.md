# Retriever Meet-Old — Build Checklist (v1)

**Status:** FINAL, ready for module-by-module build
**Kickoff:** 2026-07-22
**Owner:** Retriever Agent (ME) with TECH structural review + Eval gating + DB sign-off

---

## Build Order & Dependencies

```
POOL (Module #1, independent)
  ↓
ROUTER (Module #2b, independent of POOL logic, depends on pool schema only)
  ↓
FILLERS (Module #3, depends on POOL + ROUTER for strategy dispatch)
  ↓
OBSERVE (Module #4, depends on FILLERS outputs)
  ↓
SYNTHESIS (Module #5, depends on OBSERVE confidence scores)
  ↓
CONTRACT (Module #6, depends on all priors)
  ↓
TIMING (Module #7, cross-cut, instrument all segments)
  ↓
END-TO-END TESTS (all modules integrated)
```

**Parallel:** POOL + ROUTER can build in parallel if pool schema (rag_published_embeddings) is clear
**Sequential:** FILLERS → OBSERVE → SYNTHESIS → CONTRACT → TIMING must be sequential (dependency chain)

---

## Module #1: POOL (search + rerank + neighbors)

**Owner:** Retriever Agent (ME)
**Dependencies:** None (existing rag_published_embeddings table)
**Build time estimate:** 5–7 days (code + test + review)

### Tasks

- [ ] **Extract search functions** (from corpus_search_agent.py)
  - `_search_bm25_strict_relaxed()` — strict at :3347, fallback at :3417
  - `_search_vector_strict_relaxed()` — strict + fallback via :1225 cascade
  - Anchor constant: `_MIN_STRICT_RESULTS = 5` (TECH decision)
  - Test: fallback threshold matrix (0→cascade, 1→no, 4→cascade, 5→no, 6→no)

- [ ] **Extract rerank function** (shared by a/b)
  - `_rerank_with_tags()` — normalize scores, apply _TAG_COVERAGE_FLOOR, filter, sort
  - Preserve: is_promoted_neighbor logic (:2210)
  - Test: tag-coverage boost measure (expect 1.1-1.3x multiplier)

- [ ] **Wire neighbor assembly** (already exists)
  - `_fetch_sibling_chunks_batch :2560` — ±2 para / ±1 page
  - Verify: _neighbor_text populated, is_neighbor=True on siblings
  - Test: neighbor window validation (±2/±1 correctly fetched)

- [ ] **Pool output contract**
  - Return: `{pool_result[]: {chunk_id, is_neighbor, score, _neighbor_text, tags}, metadata}`
  - Test: schema validation, no NULL vectors

- [ ] **Test pool fallback** (parameterized test matrix)
  - 0 strict → cascade, 1 → no, 4 → cascade, 5 → no, 6 → no
  - Measure: pool latency p50/p95 (gate: <2s p50, <4s p95)

- [ ] **Baseline: cmhc 22-query**
  - Measure recall (gate: ≥7/22, no regression)
  - Measure pool latency per segment (bm25_ms, vector_ms, rerank_ms, neighbors_ms)
  - Publish results

### Sign-Off Gate
- ✅ Byte-diff clean on cmhc baseline (same chunks, same ranks, same scores)
- ✅ Fallback threshold correct (3+ queries fire at <5, none above)
- ✅ Neighbors assembled (is_neighbor flags, _neighbor_text present)
- ✅ Latency gate (p50 <2s, p95 <4s)
- ✅ Eval + TECH approve → move to Module #2

---

## Module #2b: ROUTER (strategy selection)

**Owner:** Retriever Agent (ME) + DB Agent (schema)
**Dependencies:** rag_query_decisions schema + decision_id pre-allocation (eval handshake)
**Build time estimate:** 4–5 days (code + test + review + DB DDL)

### Tasks

- [ ] **Implement linear formula** (v1 + v2 merged)
  - Import v1 router (:4161 corpus_search_router.py)
  - Verify v2 imports v1 (no forked logic)
  - Frozen weights (calibration baseline, no tuning)
  - Test: determinism (3 runs = identical scores + strategy)

- [ ] **Decision-row logging** (one-writer collapse, Option B)
  - Agent receives `decision_id` (pre-allocated by Eval)
  - Agent INSERTs: `{decision_id, corpus_id, query_text, strategy, scores[], feature_vector, ...}`
  - Code review: verify agent has ZERO uuid.uuid4() calls
  - Test: INSERT latency (<50ms), no duplicates

- [ ] **Escalation ranking** (linear formula, not hardcoded ladder)
  - `escalate_to = sort(alternative_scores, descending)[1]` (next-best)
  - Deterministic per-query, testable
  - Test: 3 escalations = same strategy order
  - Validation: on held-out escalations, confirm rank order matches performance

- [ ] **s-row NULL feature_vector edge**
  - If strategy=s, feature_vector NULL (not 0, not empty)
  - Schema CHECK constraint: `strategy_used != 's' OR feature_vector IS NULL`
  - Test: force s-strategy, assert NULL

- [ ] **DB schema** (DB Agent)
  - Add CHECK constraint on rag_query_decisions
  - Optional: eval_run_decisions junction table (if needed for eval tracking)
  - Migration: tested on dev DB
  - Code review: DB + TECH approve DDL

- [ ] **Test decision-row** (parameterized)
  - INSERT via agent with pre-allocated ID (no uuid.uuid4())
  - Verify: one row per query, no conflicts
  - Byte-diff: chosen_slot matches legacy v1

- [ ] **Baseline: cmhc 22-query**
  - Measure routing consistency (3 runs = identical choices)
  - Measure router latency (gate: <100ms)
  - Publish results

### Sign-Off Gate
- ✅ Byte-diff vs v1 routing_dump (zero changes to chosen_slot, score order)
- ✅ Determinism (3 runs = identical)
- ✅ One-writer verified (agent only, no eval/calibrate duplication)
- ✅ Escalation ranking correct (alternative_scores order, not hardcoded ladder)
- ✅ s-row NULL constraint enforced (schema CHECK)
- ✅ Eval + TECH + DB approve → move to Module #3

---

## Module #3: FILLERS (execute strategy, thin consumer)

**Owner:** Retriever Agent (ME)
**Dependencies:** POOL + ROUTER (pool output, strategy selection)
**Build time estimate:** 4–5 days (code + test + review)

### Tasks

- [ ] **Filler a (BM25 thin consumer)**
  - Read pool_result (pre-built), pick top-K matches (no re-search)
  - Verify: no db.query(), no embed() calls
  - Output: FilledResult {strategy="a", chunks, metadata}
  - Test: byte-diff vs legacy per-strategy

- [ ] **Filler b (vector thin consumer)**
  - Read pool_result, pick top-K
  - Verify: read-only (pool not mutated)
  - Output: FilledResult {strategy="b", chunks, metadata}

- [ ] **Filler c (LLM synthesis path)**
  - Pass pool_result + query to synthesis
  - Verify: answer candidate generated
  - Output: FilledResult {strategy="c", chunks, answer}

- [ ] **Filler d (web search)**
  - Call external API
  - Verify: no DB/embed calls within filler (external only)
  - Output: FilledResult {strategy="d", chunks, answer}

- [ ] **Filler s (cache lookup)**
  - Query payor-platform agent API
  - Verify: no error on cache miss
  - Output: FilledResult {strategy="s", chunks, answer}

- [ ] **Parallel execution safety**
  - 5 fillers run concurrently
  - No locks needed (pool read-only)
  - Test: parallel stress (10 concurrent pools, 5 fillers each)

- [ ] **Static analysis: no DB/embed**
  - grep corpus_search_agent.py (fillers section) for db.query, embed
  - expect: 0 matches (all DB/embed in pool, not fillers)

- [ ] **Test fillers (parameterized)**
  - test_filler_a, test_filler_b, test_filler_c, test_filler_d, test_filler_s
  - Measure: latency per filler (<300ms each)
  - Byte-diff: outputs match legacy

- [ ] **Baseline: cmhc 22-query**
  - Measure filler latency per strategy
  - Publish results

### Sign-Off Gate
- ✅ Static analysis: zero DB/embed calls in filler section
- ✅ Read-only verified (pool not mutated)
- ✅ Parallel safety (no race conditions, no locks)
- ✅ Byte-diff vs legacy per strategy
- ✅ Latency gate (p50 <300ms per filler)
- ✅ TECH + Eval approve → move to Module #4

---

## Module #4: OBSERVE (cross-lens validation)

**Owner:** Retriever Agent (ME)
**Dependencies:** FILLERS (filler outputs)
**Build time estimate:** 5–6 days (code + test + review)

### Tasks

- [ ] **Observe a (BM25 + vector cross-check)**
  - Validate: match_count ≥ threshold, scores ≥ floor
  - Cross-lens: embed chunks, measure cosine to query
  - Output: confidence_score ∈ [0, 1]
  - Test: confidence range validation

- [ ] **Observe b (vector + tag cross-check)**
  - Validate: match_count, scores
  - Cross-lens: J/P/D tag presence
  - NULL-tag policy: "neutral" (skip, measure frequency)
  - Output: confidence_score
  - Test: NULL-tag edge case (chunk.tags = None → skip)

- [ ] **Observe c (LLM + multi-lens)**
  - Validate: source authenticity, vector sim, tag language
  - Output: confidence_score

- [ ] **Observe d (web + multi-lens)**
  - Validate: source reputation, semantic match, domain language
  - Output: confidence_score

- [ ] **Observe s (cache + vector+tag)**
  - Validate: freshness (age), vector drift, tag shift
  - Output: confidence_score

- [ ] **Neighbor skip (context scaffolding)**
  - For all strategies: skip is_neighbor=True chunks during validation
  - Code: `for chunk in pool: if chunk.is_neighbor: continue`
  - Test: validate output excludes neighbors

- [ ] **NULL-tag frequency measurement**
  - Count % of chunks with tags=None in cmhc baseline
  - If >5%: flag escalation to "strict" policy (after baseline)
  - Log: NULL-tag frequency per query

- [ ] **Confidence score distribution**
  - Measure: mean, median, p25/p75 of confidence_score across cmhc
  - Publish: histogram for calibration

- [ ] **Test observe (parameterized)**
  - test_observe_a_cross_lens, test_observe_b_cross_lens, etc.
  - test_observe_skips_neighbors
  - test_observe_b_null_tags
  - Measure: confidence distribution

- [ ] **Baseline: cmhc 22-query**
  - Measure confidence scores per strategy
  - Measure NULL-tag frequency
  - Publish results

### Sign-Off Gate
- ✅ Confidence scores produced [0, 1] for all 5 strategies
- ✅ Neighbors skipped (validate output = no is_neighbor=True)
- ✅ NULL-tag frequency measured (baseline <5%?)
- ✅ Cross-lens coverage (all 5 strategies validated)
- ✅ Master RAG + Eval approve confidence calculation → move to Module #5

---

## Module #5: SYNTHESIS (compose + decide reroute)

**Owner:** Retriever Agent (ME) + Master RAG (business logic)
**Dependencies:** OBSERVE (confidence scores)
**Build time estimate:** 5–6 days (code + test + review)

### Tasks

- [ ] **Confidence threshold application**
  - Config: `synthesis_confidence_threshold: 0.50` (Eval decision)
  - If confidence ≥ 0.50: synthesize (high confidence path)
  - If confidence < 0.50: reroute (low confidence path)
  - Test: threshold determinism (same score always → same decision)

- [ ] **High confidence path (synthesize)**
  - Compose answer from pool chunks
  - Generate: answer_text, thinking_trace, grounding_markers
  - Run check_facts scorer (Tier-2, untouched)
  - Output: answer candidate

- [ ] **Low confidence path (reroute)**
  - Signal escalation loop to retry (next strategy)
  - Increment attempt counter
  - Output: status=REROUTE (no answer yet)

- [ ] **Empty pool fail-close**
  - If all strategies return empty + gate.corpus_gap=True
  - Return: status=ESCALATION, message="no information available"
  - Log: corpus_gap_for_content_team
  - NO freeform synthesis when pool={}

- [ ] **Grounding validation**
  - Run check_facts Tier-2 scorer (not modified)
  - Verify: answer ⊆ pool (grounding correctness)
  - Test: grounding_confidence > threshold (gate via Eval)

- [ ] **Reroute loop integration**
  - Synthesis calls escalation loop if low confidence
  - Loop increments attempt, picks next strategy (via alternative_scores)
  - Loop stops if budget exhausted (MAX_TRIES=4)
  - Test: escalation attempt flow

- [ ] **Test synthesis (parameterized)**
  - test_synthesis_high_confidence (score ≥0.50 → synthesize)
  - test_synthesis_low_confidence (score <0.50 → reroute)
  - test_synthesis_empty_pool (all empty → fail-close)
  - test_synthesis_grounding (check_facts validates)

- [ ] **Baseline: cmhc 22-query**
  - Measure % queries at high/low confidence
  - Measure escalation frequency (reroute %)
  - Measure grounding precision (check_facts score)
  - Publish results

### Sign-Off Gate
- ✅ Threshold determinism (same score = same decision)
- ✅ Grounding validated (answer ⊆ pool via check_facts)
- ✅ Empty pool fail-close (no hallucination on empty)
- ✅ Escalation loop correct (attempts, budget, strategy order)
- ✅ Master RAG + Eval approve → move to Module #6

---

## Module #6: CONTRACT (emit 12-field response)

**Owner:** Retriever Agent (ME) + DB Agent (schema)
**Dependencies:** SYNTHESIS (all prior outputs)
**Build time estimate:** 3–4 days (code + test + review)

### Tasks

- [ ] **One emitter (routing_dump refactor)**
  - Extract routing_dump :4200-4263 into `emit_contract()` function
  - All code paths (converge, reroute, empty, escalate, diverge) → one emitter
  - Verify: single INSERT site for routing_dump

- [ ] **12-field schema (frozen)**
  ```
  {
    query_id, rewritten_query, chosen_strategy, strategy_score,
    alternative_scores, chunks[], answer_text, thinking_trace,
    grounding_markers, latency_ms, attempt_count, status, feature_vector
  }
  ```
  - Field order locked (no reorder)
  - NULL semantics: s-row NULL feature_vector, others non-NULL

- [ ] **s-row NULL feature_vector edge**
  - If strategy=s: feature_vector NULL (verified by CHECK constraint)
  - Test: force s-strategy, assert NULL in output

- [ ] **Test contract (parameterized)**
  - test_contract_schema (field order, types, NULLs)
  - test_contract_s_row_null (strategy=s → feature_vector=NULL)
  - test_contract_converge, test_contract_reroute, test_contract_empty, test_contract_diverge
  - Measure: emission latency (<50ms)

- [ ] **Byte-diff validation**
  - Compare contract output (legacy vs meet-old)
  - All non-latency fields: byte-identical
  - Latency fields: new (observe_ms, per_attempt[])

- [ ] **Baseline: cmhc 22-query**
  - Measure emission latency
  - Byte-diff report
  - Publish results

### Sign-Off Gate
- ✅ Byte-diff clean (field order, format, NULL semantics)
- ✅ One emitter verified (single encode site)
- ✅ s-row NULL constraint enforced
- ✅ All code paths tested (converge/reroute/empty/escalate/diverge)
- ✅ Latency <50ms
- ✅ DB + Eval approve → move to Module #7

---

## Module #7: TIMING (cross-cut instrumentation)

**Owner:** Retriever Agent (ME) + TECH (verification)
**Dependencies:** All 6 prior modules (instrument all segments)
**Build time estimate:** 4–5 days (code + test + review)

### Tasks

- [ ] **Instrument 9 segments**
  1. shape (t_start → t_end)
  2. pool_bm25_search_ms
  3. pool_vector_search_ms
  4. pool_rerank_ms
  5. pool_neighbors_ms
  6. router_ms
  7. fillers_a/b/c/d/s_ms (per-strategy, only logged if chosen)
  8. observe_ms
  9. synthesis_ms
  10. contract_ms (+ per_attempt[] array)

- [ ] **Per-attempt timing (escalation loop)**
  - Escalation loop (:3137) must emit: t_attempt_start, t_attempt_end, duration_ms
  - Schema: `per_attempt: [{attempt: 0, duration_ms: 1200}, {attempt: 1, duration_ms: 850}, ...]`
  - Test: escalation fires → per_attempt[] populated

- [ ] **Latency schema** (rag_query_traces JSONB)
  - Verify: full_response.telemetry has room for 9 segments + per_attempt[]
  - No migration needed (JSONB flexible)
  - But document: structure for downstream queries

- [ ] **Static audit: no untimed code**
  - grep corpus_search_agent.py for untimed paths
  - Every branch must have t_start/t_end
  - expect: 0 untimed findings

- [ ] **Test timing (parameterized)**
  - test_timing_all_segments (9 segments emit timings)
  - test_timing_per_attempt (escalation loop fires, per_attempt[] present)
  - test_timing_audit (grep finds 0 untimed paths)
  - Measure: per-segment latency (p50, p95)

- [ ] **Baseline: cmhc 22-query**
  - Measure: per-segment latency distribution (p50, p95, max)
  - Measure: escalation frequency (% queries with attempt>1)
  - Measure: total latency (p50, p95)
  - Publish: latency report (segment breakdown)

### Sign-Off Gate
- ✅ Static audit: zero untimed code paths
- ✅ Per-attempt timing correct (escalation loop fires → per_attempt[] populated)
- ✅ All 9 segments instrumented
- ✅ Latency schema fits (JSONB, no migration needed)
- ✅ Latency gate (p50 <2s shape+pool+synthesis, p95 <4s)
- ✅ TECH + Eval approve → ready for END-TO-END TESTS

---

## END-TO-END TESTS (all modules integrated)

**Owner:** Retriever Agent (ME) + QA
**Dependencies:** All 7 modules complete + signed off
**Build time estimate:** 2–3 days (integration + validation)

### Tests

- [ ] **Scenario 1: Happy Path**
  - query → shape → pool → router → fillers → observe → synthesis → contract
  - Gate: answer present, status="answer", latency_ms populated
  - Byte-compat vs legacy

- [ ] **Scenario 2: Escalation Reroute**
  - attempt_0 (low confidence) → attempt_1 (high confidence) → answer
  - Gate: attempt_count=2, per_attempt[] spans present
  - Escalation order follows alternative_scores

- [ ] **Scenario 3: Divergence**
  - N rewritten_queries diverge on axis (state, payer, etc.)
  - Gate: status="diverge", options for clarify

- [ ] **Scenario 4: Empty Pool Fail-Close**
  - All strategies empty + corpus_gap=True
  - Gate: status="escalation", message="no information available"
  - Content team: corpus_gap logged

- [ ] **cmhc 22-query full run**
  - All gates pass (recall ≥7/22, latency <2s p50, precision ≥60%)
  - Compare to legacy (byte-diff clean on non-latency fields)
  - Publish: final baseline report

- [ ] **Eval validation (end-to-end)**
  - Escalation outcomes (did strategy order match expected?)
  - Confidence calibration (are high-confidence answers actually correct?)
  - Grounding (check_facts validates answers)

### Sign-Off Gate
- ✅ All 4 scenarios tested (happy / escalation / divergence / empty-pool)
- ✅ cmhc 22-query baseline meets gates (recall, latency, precision)
- ✅ Byte-diff clean on legacy fields
- ✅ Eval + TECH + Master RAG + DB ALL APPROVE
- ✅ **READY FOR EXCEED PHASE** ✅

---

## Final Sign-Off Checklist

Before merge to main (one-pass signoff):

- [ ] Module #1 (POOL): signed off by TECH + Eval
- [ ] Module #2b (ROUTER): signed off by TECH + Eval + DB
- [ ] Module #3 (FILLERS): signed off by TECH + Eval
- [ ] Module #4 (OBSERVE): signed off by Master RAG + Eval
- [ ] Module #5 (SYNTHESIS): signed off by Master RAG + Eval
- [ ] Module #6 (CONTRACT): signed off by DB + Eval
- [ ] Module #7 (TIMING): signed off by TECH + Eval
- [ ] End-to-end: all 4 scenarios + cmhc baseline, signed off by ALL
- [ ] cmhc 22-query baseline report published (recall, latency, precision, grounding)
- [ ] Escalation order validation published (alternative_scores rank test)
- [ ] NULL-tag frequency baseline published (ready for exceed if >5%)

**After final sign-off:** Deploy to dev → Exceed phase → Multi-invoke + decomposition + freeform synthesis

---

**READY TO BUILD. Kickoff: 2026-07-22. Build time estimate: 4–5 weeks (7 modules + e2e + baseline).**
