# Retriever Module Gates — Performance Contracts

**Owned by: Technical Review (performance logic) · Validated by: Eval during build**

These are the performance gates each module must satisfy. Master RAG owns the business logic contract (routing, synthesis, grounding); Architects own these performance boundaries.

**Gate verification:** Eval runs before/after on cmhc 22-query bank + latency traces. Every gate must be marked SAFE or NUMBER-MOVING with measured deltas.

---

## 1. shape — Answer shape (decomposer & planner)

**Owner:** Retriever

### Input
- Query text (user question)
- Org context (org_id, payor tags, location filters)

### Output
- **Rewritten queries:** one or more rewritten/decomposed question(s)
- **Answer shape:** slot structure (a, b, s) for the decomposed answer
- **Slots:** capacity + rank order for each slot type

### Performance Gates
- **Decomposition latency:** p50 < 500ms (pure logic, no DB calls)
- **No database access:** shape is pure LLM or rule-based decomposition
- **Deterministic output:** same query always produces same rewritten questions + shape (no randomness)

### Acceptance Criteria
- Eval measures: decomposition overhead (< 500ms added to end-to-end latency)
- Trace telemetry: rewritten_queries[] logged per query
- Shape structure validated (all slots populated, no nulls)

---

## 2. pool — Candidate pool

**Owner:** Retriever (Curation builds data, Retriever consumes)

### Input
- Rewritten queries (from shape module)
- Org context (org_id, payor tags, location filters)

### Output
- **One candidate pool:** sorted list of {chunk_id, source_id, score, tags, rank}
- Pool is built **once per request** (not per filler)
- Includes all retrieval modes: BM25 (term match) + vector (semantic) + tag inheritance (cross-payer auto-union)
- Pool is fully timed per-segment

### Performance Gates
- **Latency:** p50 < 2s, p95 < 4s per rewritten question (on corpus size ~50k; measured under load)
- **One build per input set:** never build the same pool twice; one pool per rewritten question (or union once)
- **Strict→relaxed fallback preserved:** if strict metadata-only (J) is empty for non-AHCA, fallback to relaxed (body d/p tags). Edge: must not silently drop recall when collapsing to union.
- **Large-pool mitigation:** AHCA queries (~2052 docs) capped at _DTAG_ARM_MAX_POOL_DOCS=200 per arm; GIN index covers tag filter or must be bounded in query logic.
- **Empty pool handled:** if vector_broad also empty, honest gap (no crash); signal to shape/router for emergency handling.

### Acceptance Criteria
- Eval measures: oracle_recall (per-query max over {a,b,s}) baseline vs. union-only configuration; delta ≤ −0.01 = SAFE, delta > −0.02 = NUMBER-MOVING
- Every segment timed: bm25_arm, vector_broad, tag_filter, union
- Pool cardinality logged per query
- Strict/relaxed decision traced (decision point + fallback reason if triggered)

---

## 2. shape — Answer shape (slot model)

**Owner:** Retriever

### Input
- Pool (from pool module)
- Query + escalation context (retry attempt, why escalating)

### Output
- **Slot model:** structure with {slot_a, slot_b, slot_s} keyed by filler type
- Each slot has capacity (max docs), rank order, escalation markers
- Shape replaces the a→b→d ladder with explicit slot-driven escalation logic

### Performance Gates
- **Escalation latency:** p50 < 500ms per attempt (loop is currently agent:3137-3399, must be timed per-attempt)
- **Per-attempt timing:** each escalation retry is timed from entrance to decision (routing decision latency separate)
- **Routing decision determinism:** same query + pool always produces same slot order (no randomness in shape logic itself; only router.bandit decision is random)

### Acceptance Criteria
- Eval measures: before/after routing latency (forced option-a vs escalation ladder); NUMBER-MOVING tag confirmed
- Loop timing instrumented: t_loop_start at :3137, t_loop_exit per attempt boundary, span emitted
- Shape produces consistent slot structure (schema validated)
- Escalation retries logged with reason + timing

---

## 3. fillers — Slot fillers (a, b, s)

**Owner:** Retriever

### Input
- Pool(s) (from pool module — read-only)
- Shape (slot specification from shape module)

### Output
- **Filled shape:** {slot_a, slot_b, slot_s} with actual chunks from pool(s)
- One filler per slot type; each must fill its slot from pool candidates (in shape-defined rank order)

### Performance Gates
- **Filler latency:** p50 < 300ms per filler (3 fillers in parallel or sequential, total < 900ms typical)
- **Read-only contract:** fillers may NOT open a DB connection or trigger embeds; they read the pool only
- **Union correctness:** when pool is union (strict ∪ relaxed), fillers must not re-filter or re-score; they consume pool as-is

### Acceptance Criteria
- Eval measures: filler latency per slot type; before/after union-pool configuration
- Static analysis: no db.query(), no embedding calls in filler code paths
- Filled slots match pool structure (rank order preserved, no duplicates)
- Union mechanism validated: recall lift 0.60→0.65 on healed corpus

---

## 4. router — One router (v1/v2 merged)

**Owner:** Retriever

### Input
- Filled shape (from fillers module — all slots already populated with pool chunks)
- Query + context

### Output
- **Routing decision:** one of {a, b, s} (which filled slot to surface), confidence, alternatives
- **Bandit decision row:** (query_id, attempt, chosen_slot, alternatives, reward_metadata) → written to rag_query_decisions
- Per-query routing is **byte-identical** to baseline (option a); diagnostic detail is additive only

### Performance Gates
- **Routing decision latency:** p50 < 100ms (independent of pool size; ranking over filled slots)
- **Byte-identical routing:** per-query routing decision must be deterministic and match v1 baseline; v2 logic is strictly additive (confidence field, alternatives array) — no change to chosen_slot value
- **Bandit row generation:** every routing decision writes exactly one row to rag_query_decisions (Tier-3 writer); ONE-WRITER constraint (single INSERT site)
- **Row schema frozen:** bandit row schema unchanged (machine check enforced)

### Acceptance Criteria
- Eval measures: before/after routing latency (must be SAFE or NUMBER-MOVING per cmhc calibration)
- Byte-diff on routing_dump output: zero changes to routing keys (query, chosen_slot, order)
- Machine check (TECH): ONE-WRITER on rag_query_decisions (only one INSERT site in the codebase)
- Machine check (TECH): routing_dump output byte-identical (field order, format, NULL semantics)
- v1/v2 merge verified: v2 imports v1, no duplicate logic

---

## 5. synthesis — One synthesis pass

**Owner:** Retriever

### Input
- Filled shape (from fillers module — pool chunks assigned to slots)
- Routing decision (from router module — chosen_slot, confidence)
- Query

### Output
- **Answer:** synthesized text grounded in chosen slot's chunks
- **Thinking trace:** reasoning chain (which chunks used, why, how composed)
- **Grounding markers:** links from answer back to source chunks (evidence ⊆ pool)

### Performance Gates
- **Synthesis latency:** p50 < 3s, p95 < 6s (including LLM call)
- **Grounding fidelity:** answer must be a subset of pool evidence (enforced by check_facts scorer, Tier-2 locked)
- **One pass:** synthesis reads the filled shape once, outputs once; no re-ranking or re-scoring

### Acceptance Criteria
- Eval measures: before/after synthesis latency; before/after grounding accuracy (answer ⊆ pool); Tier-2 scorer must be locked (no behavioral change during refactor)
- Grounding_badge presence confirmed (UX gate)
- Trace telemetry present (synthesis reasoning logged)

---

## 6. contract — 12-field envelope (frozen emitter)

**Owner:** Retriever

### Input
- Filled shape (from fillers/routing)
- Routing decision (from router)
- Synthesis outputs (answer, thinking, grounding)
- All timing data (per-segment spans)

### Output
- **Frozen 12-field response:** {query, chosen_slot, score, chunks[], answer_text, thinking, traces, routing_keys, grounding_markers, latency_ms, attempt_count, status}
- Every code path in retriever emits through this contract
- Byte-compatible: field order, format, NULL semantics unchanged

### Performance Gates
- **Byte-compat P0:** no field order changes, no format changes, NULL semantics match baseline (e.g., s-row has NULL feature_vector by design, non-s rows must have non-NULL feature_vector)
- **Emission latency:** p50 < 50ms (serialization + emit to response writer)
- **One emitter:** all code paths funnel through one canonical encoder (routing_dump :4200-4263)

### Acceptance Criteria
- Machine check (TECH): byte-diff clean on response JSON (field order, keys, value types)
- Machine check (TECH): response envelope validated (all 12 fields present, types match, no extra fields)
- Pre-deploy test: s-row NULL feature_vector constraint validated (non-s rows: non-NULL, s-row: NULL)
- Baseline diff run: before/after response shape on cmhc bank (zero byte diffs on non-latency fields)

---

## 7. timing — Cross-cut instrumentation

**Owner:** Retriever (coordinated with all 6 modules)

### Input
- Every module's entry/exit points

### Output
- **Timed spans:** every DB call, retrieval segment, LLM call includes t_start, t_end, duration_ms
- Spans are emitted as part of the trace telemetry

### Performance Gates
- **Every segment timed:** pool, shape, fillers, router, synthesis, contract — each has per-segment timing (not just global t0)
- **Loop timing required:** escalation loop (:3137-3399) must emit per-attempt timing (t_attempt_start, t_attempt_end) before shape can be signed off
- **Trace completeness:** no untimed segments; "untimed = defect"

### Acceptance Criteria
- Machine check (TECH): grep for untimed code paths; escalation loop must have per-attempt spans
- Eval measures: latency distribution per segment (p50, p95) before/after
- Trace schema validated (all segments present in every query trace)

---

## Architecture Sequencing (Critical)

This gate document assumes the following module order (NEW design):

1. **Shape** (decompose query, plan structure)
2. **Pool** (fetch candidates per rewritten-q)
3. **Fillers** (assign pool to shape slots)
4. **Router** (rank/order filled slots, log decision)
5. **Synthesis** (turn filled shape into answer)
6. **Contract** (serialize response)
7. **Timing** (cross-cut instrumentation)

**Deviation from current state:** Shape now runs first (not pool). This is a structural change Retriever must design to.

---

## Sign-off Order

1. **Master RAG confirms** gates 1, 5 (shape decomposition, synthesis grounding) preserve business logic
2. **Tech Review signs all gates** (structural + instrumentation + sequencing)
3. **DB signs gates 2, 4, 6** (pool access patterns, router bandit-row schema, contract envelope schema)
4. **Eval signs performance acceptance criteria** (latency + before/after calibration on cmhc bank)
5. **Ananth approves gates** before Retriever builds

Once approved: Retriever designs per-module logic (current → future), then builds. Eval validates at each gate during build.

---

**Updated 2026-07-22 by Tech Review (incorporating Master RAG structural feedback)**  
**Related:** [module-sequence.md](module-sequence.md) (visual schematic) · [retriever-current-state.md](retriever-current-state.md) · spec §4 gates
