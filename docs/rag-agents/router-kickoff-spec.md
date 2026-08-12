# Router — Kickoff Spec (Reasoning + Strategy)

**Status:** REFRAMED 2026-07-23 (see below). **Co-design with Eval is the next real step, not solo spec refinement.**

**⚠️ REFRAMED:** This is NOT two-phase (early heuristic + late ranking). That framing was wrong — it implied two separate reasoning acts. **Router is ONE reasoning pass** — a constrained optimizer that plans the full strategy sequence across all slots ONCE, upfront. No re-invocation. "Late phase reporting" (outcome + bandit row) is just reporting what Router already decided, not a second reasoning pass.

Supercedes `change-request-observer-module.md` framing. See `router-module-spec.md` (the authoritative spec) and `observer-module-spec.md` (Observer's separate, purely mechanical role).

**Scope (one reasoning pass, upfront):**
1. **Router (optimization):** given all N slots + Pool's corpus-depth signal + Eval's priors + global budget, compute optimal strategy sequence per slot → RoutingLadder. Runs once before Fillers' first attempt.
2. **Observer (mechanical gate):** after each Fillers attempt, check confidence + speed. Orchestrator walks Router's pre-planned ladder based on verdicts.
3. **Router (reporting):** after all slots resolve, rank outcome + log one bandit row. Not a second reasoning pass.

**This spec is now DRAFT status only.** Awaiting Eval co-design on the optimization logic (priors, joint-allocation algorithm).

---

## Input Contract (PENDING FILLERS FINALIZATION)

From Fillers, the router receives a `filled_shape` object with:
- `answer_shape` (essay / structured / binary / any) — the user's requested answer format
- `slots[]` — list of answer slots, each with:
  - `slot_id` (unique identifier within this answer_shape)
  - `chunks[]` — candidate chunks assigned by Fillers (pre-ranked, best-first)
  - `slot_score` (optional, Fillers' confidence in this slot's fill)
  - `slot_status` (fulfilled / partial / gap)
- `pool_metadata` (pool size, tag coverage, query class — inherited from Shape)
- `caller_prefs` — answer_shape, accuracy_need, speed_budget (from the original request)

**Assumptions (to verify once Fillers ships):**
- Slots are pre-ranked by Fillers (best-fit-first order)
- Each slot has at least one chunk (gap slots have `status=gap`)
- Pool metadata includes query_class + feature_vector used by Shape

---

## PHASE 1: Early (Per-Slot Strategy Ladder)

**INPUT (from Structure's AnswerSlot):**
- `slot_id`
- `resource_posture` with:
  - `max_attempts` (int) — how many strategies can this slot try?
  - `confidence_bar` (float [0,1]) — what confidence threshold counts as "done"?
  - `priority` (str) — criticality of this slot (e.g., core, supporting, optional)
- `answer_shape` — what format does this slot need?

**OUTPUT:**
Populate `AnswerSlot.strategy_sequence` with an ordered list of strategy IDs:
```python
# Example outputs:
slot.strategy_sequence = ["a", "b"]  # max_attempts=2
slot.strategy_sequence = ["a", "b", "c", "d"]  # max_attempts=4
slot.strategy_sequence = ["b"]  # max_attempts=1, high-priority, route straight to essay filler
```

**Ladder Logic:**
The sequence trades off coverage vs. resource budget:
- **Small budget (max_attempts=1):** pick ONE best strategy for this slot's profile
- **Medium budget (max_attempts=2–3):** ordered escalation (fast+accurate first, then broader coverage)
- **Large budget (max_attempts=4+):** sequential coverage (start narrow, expand if needed)

**Considerations:**
- Per-slot, not per-query (unlike v1/v2). Slots have different postures; one slot may get 1 attempt, another 4.
- Slot's answer_shape + priority + pool_metadata (from Shape context) inform the sequence
- No DB access; pure logic over slot profile + query features
- NOT deciding what to retrieve (Pool already fetched everything); deciding which Fillers strategy to try in which order

**Timing:**
Runs once per slot, upfront, before Fillers attempt loop. Very fast (< 10ms per slot).

---

## PHASE 2: Late (Ranking + Decision Logging)

**[Original job, unchanged from pre-change-request spec below]**

### Stage 1: Slot Scoring
For each non-gap slot:
- **Slot quality score** = `slot_score` (from Fillers, if provided; else derived from top-chunk evidence)
- **Caller alignment** = how well the slot's chunks match caller's accuracy_need + recall_demand
  - High accuracy_need + low slot_score → lower rank
  - Low speed_budget + many chunks → lower rank (synthesis will be slow)
- **Combined score** = weighted blend of slot_quality + caller_alignment

### Stage 2: Ranking + Selection
1. Rank non-gap slots by combined score (descending)
2. Pick **top slot as primary**
3. Pick **2nd-ranked as fallback** (for ReAct re-route if primary's synthesis abstains)
4. If all slots are gaps → escalate to strategy `e` (refuse), compute honest-gap outcome

### Stage 3: Confidence
Compute **confidence** as a continuous value [0, 1]:
- High (≥0.8): top-slot score significantly ahead of alternatives
- Medium (0.5–0.8): close race between top-2 slots
- Low (<0.5): top slot barely wins, or few chunks in pool

Confidence drives ReAct escalation: if confidence ≤ threshold, agent re-routes to fallback immediately.

---

## Output Contract (BYTE-IDENTICAL ROUTING_DUMP + DECISION ROW)

### routing_decision object
```python
@dataclass
class RoutingDecision:
    chosen_slot: str          # the primary slot_id
    fallback_slot: str | None # 2nd best (for ReAct re-route)
    confidence: float         # [0, 1]
    all_scores: dict[str, float]  # all slots → score (for cockpit)
    query_decision_id: str    # UUID for this decision
```

### rag_query_decisions row (§9 / §10 aligned)
Write a single row per query with:
- **`leaf_key`:** the chosen slot_id (byte-compat with legacy "chosen strategy")
- **`feature_vector`:** context dict (pool size, query class, caller prefs) — the bandit's input `x`
- **`strategy_scores`:** a dict slot_id → score (all non-gap slots) — the bandit's reward context
- **`corpus_version`:** cached from pool (never compute-at-query)
- **`routing`:** the full routing dump (dict with chosen, fallback, confidence, all_scores, feature_vector)
- **Per-slot detail (NEW, additive, OPTION A):** a sub-field `routing.per_slot_detail` with:
  - Each slot_id → {score, status, n_chunks, top_chunk_source}
  - Logged for cockpit/analysis; does NOT change leaf_key/feature_vector semantics
  - **Needs Eval sign-off before schema migration**

---

## Architectural Boundaries

### Pure over filled_shape
- Router reads the filled_shape (zero DB access)
- No embeddings, no new retrieval, no pool builds
- Signature: `decide(filled_shape: FilledShape, caller_prefs: RoutePreferences) → RoutingDecision`

### Timed segments (spec §4 gate d)
- **[trace:router_decide]** — slot scoring + ranking (< 50ms)
- **[trace:router_persist]** — async write to rag_query_decisions (fire-and-forget, idempotent)
- Total: part of the answer-path orchestration spans that currently live at `agent.py :3137-3399` (untimed in v1, gate d target)

### Byte-compatibility (spec §4 gate a)
The 12-field envelope routing_dump must be projectable into the same columns as today's legacy routing_dump:
```python
routing_dump = {
    "chosen_slot": decision.chosen_slot,
    "fallback_slot": decision.fallback_slot,
    "confidence": decision.confidence,
    "query_decision_id": decision.query_decision_id,
    "feature_vector": feature_vector,
    "all_scores": decision.all_scores,
    # s-row NULL protection: feature_vector NULL on s-rows (gap escalation)
}
```

---

## One-Writer Enforcement (spec §4 gate f)

Only `router.py:persist_decision()` may INSERT into `rag_query_decisions`. No other write site allowed post-refactor.

- Move the eval-path write (`eval/calibrate.py:362`) to call the same `persist_decision()` function
- OR separate the prod + eval writes into flagged branches of one writer
- **Outcome:** one symbol, one version stamp, one control point

---

## Routing Contract Decision (EVAL-SIGNED 2026-07-22 — LOCKED)

**RESOLVED: Option (a), back-compatible.**
- Keep the per-query `routing` shape the bandit reads **EXACTLY unchanged** (priors_version, feature_vector, leaf_key, scores)
- `leaf_key` = chosen_slot_id (per-query, not per-slot)
- Log per-slot detail in a new additive sub-field `routing.per_slot_detail` (diagnostic-only, not consumed by bandit)
- Per-slot schema: `{ slot_id: {score, status, n_chunks, top_chunk_source, ...} }`
- **No change to `leaf_key` or `feature_vector` STRUCTURE** → not a telemetry migration → no db8f597-class break risk
- feature_vector **VALUES** differ from legacy (filled_shape context vs raw_query), but that's an **intentional input change**, not a migration
- Bandit reward + context derive SOLELY from per-query keys → training row byte-identical in structure

**Not taken (Option b):** per-slot leaf_key + feature_vector = separate future telemetry migration requiring fresh sign-off. Deferred.

**Enforced by 3 machine checks:** ONE-WRITER, ONE-IMPORTER, FACT_CHECKER_VERSION stamp.

---

## File Structure (Phase 2 split)

```
mobius-rag/app/services/
├── router/
│   ├── __init__.py
│   ├── decision.py        # RoutingDecision, RoutePreferences
│   ├── score.py           # slot scoring logic
│   ├── ranker.py          # ranking + selection
│   ├── persist.py         # ONE-WRITER, rag_query_decisions insert
│   └── telemetry.py       # feature_vector + bandit row schema
├── (legacy v1/v2 frozen behind `RAG_ANSWER_ENGINE=legacy`)
```

Estimated ~400–500 LOC (scoring + ranking + persist + tests).

---

## Build Gates (same as all Step-4 modules)

**Technical Review (structural):**
- (a) Byte-compat: routing_dump diffed on eval bank ✓ (design checks this)
- (b) Single-pool: router reads filled_shape, never opens DB ✓ (signature enforces)
- (d) Timed: every segment tagged ✓ (design includes [trace:router_*])
- (f) ONE-WRITER: only `persist_decision()` writes ✓ (architecture enforces)

**Eval (outcomes):**
- Per-slot detail (Option A) explicit sign-off ← **blocking**
- Forced-arm latency: router < 50ms ← verification once built
- Recall: no change (router doesn't change retrieval, only ranking) ← verification

---

## Open Questions (Early Phase)

**Pending change-request approval + input from Shape/Fillers:**

1. **Ladder semantics:** should the sequence always be [a, b, c, d], or can it vary per slot profile?
   - Conservative: always [a, b, c, d] for max_attempts=4; truncate to [a, b] for max_attempts=2
   - Adaptive: use slot's answer_shape + priority to reorder (e.g., essay-first when needed)
   - Constraint: must not exceed slot's max_attempts budget

2. **Observer's confidence bar integration:**
   - Router's early phase doesn't compute actual confidence (that's Observer's job post-fill)
   - But Router should be aware of the bar when sizing the ladder
   - E.g., if confidence_bar=0.9 (strict), maybe skip c/d in the ladder?

3. **Priority-awareness:**
   - Should core/required slots get preferential strategy order?
   - E.g., core slots: [a, b, c, d]; optional: [a, d] (skip middle breadth)?

4. **Pool metadata impact:**
   - Pool's size/tag_coverage/query_class should inform the ladder
   - E.g., wide pool (>500 docs): [a, b] (breadth); tight pool: [a, d] (depth)

---

## Next Steps (BLOCKING ON FILLERS SIGN-OFF + CHANGE-REQUEST APPROVAL)

1. **Change-request approval:** Chat/UX/Eval/DB/TECH sign-off on two-phase router + Observer module
2. **Receive:** Fillers' real `FilledShape` contract (schema, examples)
3. **Receive:** Structure's `ResourcePosture` exact schema (max_attempts, confidence_bar, priority)
4. **Design early phase:** ladder logic + heuristics (conservative vs adaptive)
5. **Design late phase:** refine slot_score, confidence model
6. **Build:** behind `RAG_ANSWER_ENGINE=shape` flag (contract already frozen + signed)
7. **Gate:** structural (TECH) + outcomes (Eval) both green before flag flips
