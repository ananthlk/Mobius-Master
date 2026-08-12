# Retriever Meet-Old — Test Plan (v1)

**Status:** FINAL, ready for build + test cycle
**Date:** 2026-07-22
**Baseline:** cmhc 22-query bank (0.278 baseline, 41% routing, 0.505 avg score)

---

## Test Plan Structure

**Per-module:** acceptance criteria + test cases + gate (pass/fail threshold)
**Cross-module:** integration tests, end-to-end flow, cmhc baseline validation
**Sign-off:** TECH + Eval + Master RAG approve before next module

---

## Module 1: POOL (search + rerank + neighbors)

### Acceptance Criteria
- ✅ Byte-identical to legacy on cmhc bank (same queries, same ranks, same scores)
- ✅ Pool built once per rewritten_query (no per-filler re-search)
- ✅ Fallback cascade triggers correctly (strict→relaxed at threshold)
- ✅ Neighbors assembled (±2 para / ±1 page, _neighbor_text populated)
- ✅ No NULL vecs in vector search (all 1.94M rows have embeddings)

### Test Cases

#### Pool Fallback Threshold (threshold = 5)
```
test_cascade_at_threshold:
  | strict_count | expected_cascade | rationale |
  |---|---|---|
  | 0 | YES | empty, observe needs targets |
  | 1 | NO | rare but valid, skip tax |
  | 4 | YES | below threshold |
  | 5 | NO | at boundary |
  | 6 | NO | above threshold |
  
  for each: verify pool_result has both strict + relaxed chunks
```

#### BM25 + Vector Search Parity
```
test_bm25_strict_relaxed:
  - query: "medicaid eligibility florida"
  - scope: "strict" (J/P/D tag match only)
  - measure: strict_count, scores, is_neighbor flags
  - assert: all chunks ranked by ts_rank_cd descending

test_vector_strict_relaxed:
  - query: embed("medicaid eligibility florida")
  - scope: "strict"
  - measure: strict_count, cosine scores
  - assert: all chunks ranked by similarity descending
```

#### Neighbor Assembly (±2 para / ±1 page)
```
test_neighbors_window:
  - select chunk at position mid-document
  - fetch neighbors via _fetch_sibling_chunks_batch
  - assert: ±2 para present, ±1 page present
  - assert: is_neighbor=True, score=None, _neighbor_text populated
  - measure: _neighbor_text length (expect paragraph + page context)
```

#### Rerank Tag-Coverage
```
test_rerank_tag_coverage:
  - pool with mixed J/P/D tag completeness
  - run rerank with _TAG_COVERAGE_FLOOR
  - assert: chunks with all 3 tags rank higher
  - measure: score boost from tag-coverage (expect 1.1-1.3x multiplier)
```

### Gate
- **cmhc 22-query baseline:** recall ≥ legacy (0.278), no regression
- **Pool latency:** p50 < 2s, p95 < 4s
- **Fallback trigger:** 3+ queries fire cascade; verify correct at threshold
- **Sign-off:** Eval confirms byte-diff clean on routing_dump

---

## Module 2: ROUTER (2b, strategy selection)

### Acceptance Criteria
- ✅ Linear formula computes all 5 strategy scores {a,b,c,d,s}
- ✅ Frozen weights (calibration baseline, no tuning in v1)
- ✅ One decision-row per query (one INSERT site :3606)
- ✅ Byte-identical routing to legacy (chosen_slot matches v1)
- ✅ Alternative_scores logged (used for escalation)

### Test Cases

#### Linear Formula Determinism
```
test_linear_determinism:
  - run same query 3x
  - assert: chosen_strategy identical, alternative_scores identical
  - measure: zero variance (not randomized)
```

#### Strategy Score Ranking
```
test_strategy_scores:
  - query: "medicaid eligibility"
  - measure: scores for {a, b, c, d, s}
  - assert: chosen strategy = argmax(scores)
  - assert: alternative_scores ordered descending
```

#### Decision-Row Schema
```
test_decision_row_insert:
  - router picks strategy
  - verify INSERT into rag_query_decisions with:
    - decision_id (pre-allocated by Eval)
    - chosen_strategy, score, alternative_scores
    - feature_vector (NULL if strategy=s)
  - assert: one row per query (not duplicates)
  - measure: INSERT latency (expect <50ms)
```

#### s-row NULL feature_vector Edge
```
test_s_row_null_feature_vector:
  - force router to pick strategy=s (cache)
  - assert: feature_vector is NULL (not empty string, not 0)
  - verify: schema CHECK constraint prevents non-NULL
```

### Gate
- **Byte-diff vs v1 routing_dump:** zero changes to chosen_slot, score order
- **Determinism:** 3 runs = identical scores/strategy
- **One-writer:** verify only :3606 INSERTs (no eval/calibrate duplication)
- **Sign-off:** Eval + DB approve decision-row schema + one-writer constraint

---

## Module 3: FILLERS (execute strategy, thin consumer)

### Acceptance Criteria
- ✅ Thin: no DB/embed calls, read-only pool consumption
- ✅ All 5 strategies {a,b,c,d,s} execute correctly
- ✅ Output: FilledResult {strategy, chunks, answer, metadata}
- ✅ Parallel: N fillers run concurrently without locks
- ✅ Byte-identical results to legacy per strategy

### Test Cases

#### Filler a (BM25 thin consumer)
```
test_filler_a:
  - pool_result from POOL module
  - fillers pick top-K matches (no re-search)
  - assert: chunks match pool result, is_neighbor flags preserved
  - assert: no db.query() calls, no embed() calls
```

#### Filler b (vector thin consumer)
```
test_filler_b:
  - pool_result from POOL module
  - fillers pick top-K matches
  - assert: chunks from pool, scores from pool (no re-rank)
  - assert: read-only (no state mutation)
```

#### Fillers c/d (LLM/web thin dispatch)
```
test_filler_c:
  - pass pool_result + query to synthesis path
  - assert: answer candidate generated (grounded or freeform)

test_filler_d:
  - call external search API
  - assert: results parsed, links extracted
```

#### Filler s (cache thin lookup)
```
test_filler_s:
  - query payor-platform agent API
  - assert: cached answer or NULL (no error on miss)
```

#### Parallel Execution
```
test_fillers_parallel:
  - 5 fillers run concurrently (a/b/c/d/s)
  - assert: no race conditions, no shared state mutation
  - measure: latency (expect <300ms per filler)
```

### Gate
- **No DB/embed:** static analysis passes (grep for db.query, embed calls)
- **Read-only:** verify pool not modified in-place
- **Byte-diff:** filler outputs match legacy per strategy
- **Concurrency:** 5 parallel fillers, no locks
- **Sign-off:** TECH + Eval approve thin interface

---

## Module 4: OBSERVE (cross-lens validation)

### Acceptance Criteria
- ✅ Per-strategy cross-lens validation (a+vector, b+tag, c/d/s+multi)
- ✅ Confidence_score produced [0, 1]
- ✅ Neighbors skipped during validation (context only)
- ✅ NULL-tag neutral policy (skip, measure frequency)
- ✅ Outcomes: converge/diverge/empty/low-confidence

### Test Cases

#### Observe a (BM25 + vector cross-check)
```
test_observe_a_cross_lens:
  - filler_a returns chunks (BM25 search results)
  - observe validates: match_count ≥ threshold, scores ≥ floor
  - cross-check: embed chunks, measure cosine to query
  - assert: confidence_score = f(match_count, score_strength, vector_sim)
  - measure: confidence in [0, 1]
```

#### Observe b (vector + tag cross-check)
```
test_observe_b_cross_lens:
  - filler_b returns chunks (vector search results)
  - observe validates: match_count, scores
  - cross-check: J/P/D tag presence
  - assert: NULL-tag chunks skipped (neutral policy)
  - measure: confidence based on tag coverage
```

#### Observe c/d (multi-lens)
```
test_observe_c_multi_lens:
  - filler_c returns answer candidate
  - validate: source authenticity, vector sim, tag language
  - measure: confidence from all three lenses
```

#### Neighbor Skip (context scaffolding)
```
test_observe_skips_neighbors:
  - pool with matches + neighbors (is_neighbor=True, score=None)
  - observe validates only matches (skip neighbors)
  - assert: confidence_score does not include neighbor validation
  - measure: validation output has neighbors removed
```

#### NULL-Tag Neutral Policy
```
test_observe_b_null_tags:
  - chunk.tags = None
  - observe b skips (neutral policy)
  - measure: NULL-tag frequency in pool
  - if >5%: flag escalation to strict policy
```

### Gate
- **Confidence range:** all scores in [0, 1], distribution visualized
- **Neighbor skip:** validate output excludes neighbors
- **NULL-tag frequency:** baseline measurement, escalate if >5%
- **Cross-lens coverage:** all 5 strategies produce confidence_score
- **Sign-off:** Master RAG + Eval approve confidence calculation

---

## Module 5: SYNTHESIS (compose + decide reroute)

### Acceptance Criteria
- ✅ Confidence threshold applied (0.50 global)
- ✅ Synthesize if confidence ≥ 0.50 (high confidence)
- ✅ Reroute if confidence < 0.50 (low confidence)
- ✅ Empty pool → fail-close (no freeform synthesis)
- ✅ Grounding validated by check_facts scorer (Tier-2)

### Test Cases

#### Confidence Threshold (0.50)
```
test_synthesis_confidence_threshold:
  - confidence = 0.49: expect REROUTE
  - confidence = 0.50: expect SYNTHESIZE (boundary)
  - confidence = 0.51: expect SYNTHESIZE
  - verify: deterministic decision per score
```

#### High Confidence Path (synthesize)
```
test_synthesis_high_confidence:
  - observe returns confidence = 0.75
  - synthesis composes answer from pool
  - assert: answer_text populated
  - assert: thinking_trace + grounding_markers populated
  - run check_facts scorer: expect grounding ⊆ pool
```

#### Low Confidence Path (reroute)
```
test_synthesis_low_confidence:
  - observe returns confidence = 0.35
  - synthesis returns REROUTE decision
  - assert: escalation loop retries (next strategy)
  - assert: no answer_text (deferred)
```

#### Empty Pool Fail-Close
```
test_synthesis_empty_pool:
  - all strategies {a,b,c,d,s} return empty
  - gate.corpus_gap = True
  - synthesis returns: status=ESCALATION, message="no information available"
  - assert: no freeform synthesis
  - verify: content team logged corpus_gap event
```

#### check_facts Grounding (Tier-2)
```
test_synthesis_grounding:
  - synthesis produces answer
  - run check_facts scorer (untouched Tier-2)
  - assert: grounding_confidence > 0.50 (arbitrary gate, Eval decides)
  - if grounding fails: mark answer unreliable (bandit feedback)
```

### Gate
- **Threshold determinism:** same confidence always → same decision
- **Grounding:** check_facts validates (answer ⊆ pool)
- **Empty pool:** no hallucination on empty pools
- **Reroute loop:** escalation attempt incremented, budget checked
- **Sign-off:** Master RAG + Eval approve synthesis logic + grounding gate

---

## Module 6: CONTRACT (emit 12-field response)

### Acceptance Criteria
- ✅ Byte-compat P0: field order, format, NULL semantics frozen
- ✅ All code paths funnel through one emitter
- ✅ 12 fields present: query, strategy, score, chunks, answer, thinking, traces, routing_keys, grounding, latency, attempt_count, status
- ✅ s-row NULL feature_vector enforced (schema CHECK)

### Test Cases

#### Field Order + Format
```
test_contract_schema:
  - emit contract from all code paths (converge/reroute/empty/escalate)
  - verify: field order stable (JSON key order)
  - verify: type consistency (score is float, not string)
  - assert: NULL values explicit (not missing keys)
```

#### s-row NULL Edge
```
test_contract_s_row_null:
  - strategy=s (cache)
  - assert: feature_vector is NULL (not 0, not empty)
  - verify: schema CHECK constraint prevents non-NULL
```

#### All Code Paths
```
test_contract_converge:
  - path: high confidence → synthesize → answer
  - verify: contract has answer_text, status="answer"

test_contract_reroute:
  - path: low confidence → reroute → no answer yet
  - verify: contract has status="reroute", answer_text=null

test_contract_empty:
  - path: all strategies empty → escalate
  - verify: contract has status="escalation", message="no info"

test_contract_diverge:
  - path: N queries diverge on axis
  - verify: contract has status="diverge", options for clarify
```

#### One Emitter
```
test_contract_single_emitter:
  - static analysis: verify one INSERT site for routing_dump
  - verify: all return paths call emit_contract()
  - measure: emission latency <50ms
```

### Gate
- **Byte-diff:** zero field order changes vs legacy
- **Schema validation:** all 12 fields present, types correct
- **One emitter:** single encode site
- **s-row constraint:** CHECK constraint enforced in DDL
- **Sign-off:** DB + Eval approve schema + CHECK constraint

---

## Module 7: TIMING (cross-cut instrumentation)

### Acceptance Criteria
- ✅ 9 segments timed: shape, pool (a/b/rerank/neighbors), router, fillers, observe, synthesis, contract
- ✅ Per-attempt spans in escalation loop (t_attempt_start, t_attempt_end)
- ✅ No untimed code paths (grep audit passes)
- ✅ Latency_ms schema fits rag_query_traces (JSONB)

### Test Cases

#### 9 Segments Timed
```
test_timing_all_segments:
  - run cmhc 22-query baseline
  - verify all 9 segments emit t_start, t_end, duration_ms
  - measure: per-segment latency (p50, p95)
  - expected: shape_ms <100, pool_ms <2000, router_ms <100, fillers_ms <300, observe_ms <200, synthesis_ms <3000
```

#### Per-Attempt Spans
```
test_timing_per_attempt:
  - force escalation (low confidence, budget>1)
  - measure: attempt_0, attempt_1, ... timing
  - verify: per_attempt[] array in latency_ms
  - assert: each attempt has t_attempt_start, t_attempt_end
```

#### No Untimed Code Paths
```
test_timing_audit:
  - grep for untimed segments (search corpus_search_agent.py, retriever_*.py)
  - assert: 0 untimed paths (all branches have spans)
  - measure: code coverage of timing instrumentation
```

#### Latency Schema Fit
```
test_timing_schema_compat:
  - verify rag_query_traces has full_response JSONB column
  - insert: latency_ms with 9 segments + per_attempt[] array
  - assert: no schema error, no truncation
  - measure: JSON size (expect <2KB per query)
```

### Gate
- **No untimed code:** grep audit = 0 findings
- **Per-attempt coverage:** escalation loop fires → per_attempt[] populated
- **Latency baselines:** p50/p95 per segment measured on cmhc
- **Schema fit:** rag_query_traces JSONB accepts latency_ms without modification
- **Sign-off:** TECH + DB approve timing instrumentation

---

## End-to-End Integration Tests

### Scenario 1: Happy Path (converge on first attempt)
```
test_e2e_happy_path:
  - query: "medicaid eligibility florida"
  - expected: shape (gate + reformat + structure)
            → pool (BM25 + neighbors)
            → router (pick strategy a)
            → fillers (execute a)
            → observe (validate, confidence=0.75)
            → synthesis (compose answer)
            → contract (emit 12-field)
  - gate: answer present, status="answer", latency_ms populated
  - assert: byte-compat vs legacy
```

### Scenario 2: Escalation Reroute (low confidence, retry)
```
test_e2e_escalation:
  - query: "aetna telehealth" (weak match)
  - expected: attempt_0 (strategy a, confidence=0.35, reroute)
            → attempt_1 (strategy b, confidence=0.60, synthesize)
            → answer
  - gate: attempt_count=2, per_attempt[] spans present
  - assert: escalation order follows alternative_scores
```

### Scenario 3: Divergence (N queries split)
```
test_e2e_divergence:
  - query: "medicaid eligibility" (fan-out to N=3 rewritten_queries)
  - path 1: "medicaid florida" → strategy a, confidence=0.70
  - path 2: "medicaid texas" → strategy a, confidence=0.72
  - path 3: "generic medicaid" → strategy d (web), confidence=0.45
  - observe: divergence detected (results split by state)
  - expected: status="diverge", options for clarify
```

### Scenario 4: Empty Pool Fail-Close
```
test_e2e_empty_pool:
  - query: "obscure internal policy no docs cover"
  - pool: empty (all strategies return 0 matches)
  - gate.corpus_gap: True
  - synthesis: status="escalation", message="no information available"
  - content team: corpus_gap logged
```

---

## cmhc 22-Query Baseline Gate

**Before code ships:** run cmhc 22-query bank with meet-old enabled (`RAG_ANSWER_ENGINE=shape`).

| Metric | Baseline (legacy) | Meet-Old Gate | Pass/Fail |
|---|---|---|---|
| Recall (top-3) | 7/22 (32%) | ≥ 7/22 (no regression) | PASS if ≥7 |
| Routing % | 41% | ±5% (allow tuning window) | PASS if 36-46% |
| Avg score | 0.505 | ±0.02 (accept 0.485-0.525) | PASS if in range |
| Precision (grounded answers) | N/A (measure now) | ≥ 60% (gate via check_facts) | PASS if Tier-2 score >0.50 avg |
| Latency p50 | N/A (measure now) | < 2s (shape + pool + synthesis) | PASS if <2000ms |
| Latency p95 | N/A (measure now) | < 4s | PASS if <4000ms |

**Eval validation steps (before v2):**
1. Measure escalation frequency on cmhc (expect 10-20% reroute rate)
2. Validate alternative_scores rank order vs escalation outcomes (confirm model correctness)
3. If precision <60%, widen eval bank to calibrate confidence threshold

---

## Sign-Off Process

**Per module:**
1. **Build:** code written (retriever team)
2. **Test:** acceptance criteria pass (Retriever + QA)
3. **Review:** TECH + Eval (+ Master RAG if business logic) approve
4. **Merge:** land on main, deploy to dev
5. **Baseline:** run cmhc 22-query, publish latency/recall deltas
6. **Sign-off:** all gates pass → move to next module

**One-pass final signoff:** all 7 modules + end-to-end tests pass → ready for exceed phase

---

## Test Execution Order

1. **POOL** (no dependencies)
2. **ROUTER** (depends on pool schema, but independent logic)
3. **FILLERS** (depends on pool output)
4. **OBSERVE** (depends on filler outputs)
5. **SYNTHESIS** (depends on observe confidence scores)
6. **CONTRACT** (depends on all priors)
7. **TIMING** (cross-cut, verify all segments)
8. **End-to-end** (all modules integrated)

**Parallelizable:** POOL + ROUTER (independent if schema clear)
**Sequential:** FILLERS → OBSERVE → SYNTHESIS → CONTRACT → TIMING

---

**READY TO BUILD. Test plan locked. Approval: Eval + TECH + Master RAG + DB.**
