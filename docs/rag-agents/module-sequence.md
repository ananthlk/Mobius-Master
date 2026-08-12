# Retriever Module Sequence — Architecture Schematic

**The 7-module flow:** query → answer with traces

```
QUERY (user question)
    ↓
┌─ STEP 1: SHAPE (decomposer & planner)
│  Input:  query, org context
│  Output: rewritten_queries[], answer_shape, slots[]
│  Role:   Breaks query into sub-questions, plans answer structure
│  ↓
┌─ STEP 2: POOL (candidate builder)
│  Input:  rewritten_queries[] (from shape)
│  Output: one pool PER rewritten query (or union of all pools)
│  Role:   Fetches candidates matching the decomposed questions
│  ↓
┌─ STEP 3: FILLERS (slot filler)
│  Input:  pool(s) (from pool), shape (from shape)
│  Output: filled_shape (slots → chunks from pool)
│  Role:   Assigns pool chunks to the answer structure
│  ↓
┌─ STEP 4: ROUTER (ordering & ranking)
│  Input:  filled_shape (from fillers)
│  Output: routing_decision (chosen_slot, confidence, alternatives)
│           bandit_row (rag_query_decisions)
│  Role:   Decides which filled slot to surface; logs the decision
│  ↓
┌─ STEP 5: SYNTHESIS (answer generator)
│  Input:  filled_shape, routing_decision
│  Output: answer_text, thinking_trace, grounding_markers
│  Role:   Turns the filled shape into natural language
│  ↓
┌─ STEP 6: CONTRACT (response envelope)
│  Input:  all prior outputs
│  Output: 12-field response {query, chosen_slot, chunks[], answer, traces, routing_keys, …}
│  Role:   Byte-identical envelope for all paths
│  ↓
┌─ STEP 7: TIMING (instrumentation, cross-cut)
│  Input:  entry/exit of every segment
│  Output: timed_spans (per-segment duration, emitted as telemetry)
│  Role:   Measure latency on every boundary; no untimed segments
│  ↓
RESPONSE (answer + traces + grounding)
```

---

## Module Responsibilities

| Step | Module | Input | Output | Owns | Constraints |
|---|---|---|---|---|---|
| 1 | **shape** | query, org context | rewritten_queries[], answer_shape, slots[] | Query decomposition + structure planning | No DB calls; pure logic. Timed. |
| 2 | **pool** | rewritten_queries[] | one pool per query OR union | Candidate fetching for decomposed questions | One build per input set. Timed. Strict→relaxed fallback preserved. |
| 3 | **fillers** | pool(s), shape | filled_shape (slots → chunks) | Matching pool to structure | Read-only (no DB/embed); consume pool as-is. Pure slot-fill logic. Timed. |
| 4 | **router** | filled_shape | chosen_slot, confidence, bandit_row | Ranking + decision logging | Byte-identical per-query routing. One-writer on rag_query_decisions. Timed. |
| 5 | **synthesis** | filled_shape, routing_decision | answer_text, thinking, grounding | Answer generation | Grounding ⊆ pool (enforced by scorer). Timed. |
| 6 | **contract** | all prior outputs | 12-field response envelope | Response serialization | Byte-compat P0. One emitter. Timed. |
| 7 | **timing** | all segment boundaries | per-segment spans | Instrumentation | Every segment timed; no untimed code paths. |

---

## Sequencing Guarantees

1. **Shape must run first.** It defines the structure and rewritten questions.
2. **Pool depends on shape output.** Pool is scoped to the questions shape produces.
3. **Fillers depend on both pool and shape.** They match pool candidates to shape structure.
4. **Router depends on fillers.** It ranks what fillers have already assigned.
5. **Synthesis depends on routing decision.** It reads what router has decided to surface.
6. **Contract depends on all prior.** It serializes everything into one envelope.
7. **Timing is cross-cut.** Every segment contributes its timed span.

---

## Key Design Decisions

- **Shape is the entry point**, not the pool. This lets chat control decomposition + structure before retrieval runs.
- **Pool is scoped to rewritten questions**, not the original query. This tightens candidate retrieval.
- **Fillers are read-only** (consume pre-built pool). No retrieval happens inside fillers.
- **Router ranks filled slots**, not deciding which retrieval to run. The decision is now "which of the filled slots to surface" (still byte-identical to picking a chosen slot).
- **Timing is mandatory on every segment**. No untimed work.

---

**This is the contract Retriever builds to. Sequence first, then fill in logic per module.**
