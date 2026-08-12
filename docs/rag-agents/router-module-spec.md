# ROUTER — Module Spec (Reasoning + Strategy) — v1

**Status:** DRAFT — kickoff artifact, reframed 2026-07-23 after Ananth's clarification. Supersedes the "two-phase Router" framing in `change-request-observer-module.md` — that framing (early ladder-planning vs late final-ranking, as two separate reasoning acts) was wrong. Router reasons **once**, upfront, per query — not twice.

**2026-07-23 addendum — dual-build, shadow-mode A/B (Ananth, explicit):** Build BOTH allocators, not one:
1. **Greedy** — the deterministic sequential-fallback allocator (simple, ships first, unblocks the rest of the chain).
2. **Optimizer** — the real constrained-optimization allocator (Section 1, the actual joint-allocation solve).

**Week 1-3 execution model:** for every real query, run **both** allocators and compute **both** RoutingLadders — but only **one** is actually executed against Fillers/Pool (chosen by a simple A/B split, e.g. alternate or a fixed %). The **other allocator's ladder is computed but not executed** — log it as a shadow decision alongside the executed one. This is cheap (allocation is a lookup/solve over priors, not an actual retrieval attempt) and gives a real side-by-side: same query, same priors, two different plans, one measured outcome + one hypothetical plan to compare against once the optimizer's own outcomes accumulate.

**Why:** this isn't the "parallel exploration to de-bias sequential-fallback" idea (rejected) — that was about forcing extra *executed* attempts to unstick priors. This is about comparing two *allocation strategies* against the same inputs so we can see where they'd diverge and tweak the optimizer against greedy's known-safe baseline, without doubling actual retrieval cost.

**Schema implication:** `rag_query_decisions` row gets both ladders logged — `executed_ladder` (the one Fillers actually walked, drives the real accuracy/latency outcome) and `shadow_ladder` (the untaken allocator's plan, no outcome, comparison-only). ONE-WRITER still holds — one row per query, just wider.
**Owner:** to be assigned. **Co-designed with Eval** — Router's optimization runs on Eval-owned priors infrastructure, not something Router invents independently.
**Renamed for clarity:** "Router" = **Reasoning + Strategy**. If "Router" keeps causing scope confusion in conversation, consider renaming the module itself — not decided yet, flag to Ananth.

---

## 0. Dispatch logic: calibration/forced vs production (CRITICAL FIRST DECISION)

Router's FIRST job is to determine which path to take, not to optimize. This is the entry point.

**Calibration/Forced path (skip all Router optimization):**
- If `is_calibration == true` (Eval is running this query in a controlled calibration run), OR
- If `forced_strategy` is set (external caller or chat is forcing a specific strategy for diagnostics/validation)
- Then: **skip Router optimization entirely**
- Action: 
  - Use the forced strategy directly (or calibration's designated strategy)
  - Set `max_attempts = 1` (no retries; measure this strategy in isolation)
  - Populate `strategy_sequence = [forced_strategy]` per slot
  - Skip confidence checks, budget allocation, priors lookups
  - Just execute, capture outcome, write one `rag_query_decisions` row
- Rationale: during calibration, Eval measures individual strategies in isolation to build priors; Router's optimization would interfere. In forced mode, caller wants that specific strategy, not Router's recommendation.

**Production path (run full Router optimization):**
- If NOT calibration AND no forced_strategy
- Then: run the constrained optimization logic (Sections 1–6 below)
- Compute RoutingLadder (strategy sequence per slot, sized to budget)
- Orchestrator walks the ladder; Observer gates attempts
- Write one `rag_query_decisions` row with the outcome

**Implementation note:**
Both paths write the same `rag_query_decisions` row (same schema, ONE-WRITER enforcement). The row's `strategy_sequence` field distinguishes them (calibration: single-element, production: full ladder). The `is_prod` flag (already in schema) also distinguishes them.

---

## 1. What Router actually is (production path): a constrained optimizer, not a per-slot heuristic

Per Ananth's framing (2026-07-23): Router solves one joint optimization problem per query, not N independent per-slot decisions.

**Given:**
- **N slots** (from Slots/`AnswerShapeResult`) — each with its own `slot_semantics`, `capacity`, `priority`.
- **Corpus-depth signal per slot** — Pool's actual BM25/tag-coverage + vector scores for that slot's candidates (how "findable" the answer looks, empirically, for *this specific query*).
- **Historical priors per strategy, conditioned on corpus depth** — base rates for speed/accuracy/recall for strategies a/b (and inherited), learned over time from real query outcomes. **This is Eval-owned infrastructure that already exists** (`project_router_prior_miscalibration.md`: forced-strategy calibration, `run_matrix→derive_priors`; `project_rag_optimization_frame.md`: forced calibration → priors + oracle ceiling). Router must consume these priors, not build its own.
- **Known cost/effectiveness profiles for c/d/s** — external strategies (LLM/Google/cache) have their own speed/accuracy tradeoffs, distinct from pool-based a/b.
- **A global budget** — `resource_posture.speed_budget` + `resource_posture.confidence_bar`, from Structure, apply **across the whole query**, not per slot independently.

**Router's job:** for each slot, pick the strategy sequence (`a>b>c>d>e>f>s`, sized to `max_attempts`) that jointly, across all N slots, hits the accuracy bar within the time budget — allocating the "expensive" strategies only where corpus depth signals they're actually needed, so one hard slot doesn't consume the whole query's time budget and starve the easy slots of their fair share.

**Runs once, upfront, before Fillers acts on anything.** Not re-invoked per attempt — see §2 on Observer's role.

## 2. Router vs Observer — the distinction that caused the confusion, resolved

| | Router | Observer |
|---|---|---|
| **Role** | Reasoning — plans the full strategy sequence per slot, once, upfront | Mechanical — checks one attempt's result against the confidence bar |
| **Runs** | Once per query (before Fillers' first attempt) | Once per Fillers attempt (after each one) |
| **Uses priors/optimization** | Yes — this is the whole point | No — pure comparison, no reasoning |
| **Decides what's next** | Yes — produces the entire ordered sequence upfront | No — orchestrator just reads the next item Router already planned |
| **Can be re-invoked mid-loop** | No | N/A — it's the mechanical gate itself, called every attempt |

**The bandit is the thing that improves Router's priors over time** — not something Router does in the moment. Router reads current priors (Eval-owned, calibrated from historical `rag_query_decisions` outcomes); the bandit/calibration loop (separate, existing, Eval-owned) is what refines those priors for next time.

## 3. Input — what Router receives

- `AnswerShapeResult` (from Slots) — `slots[]` with `slot_semantics`/`capacity`/`priority`/`rewritten_query`
- `PoolResult` (from Pool) — per-slot (or per-rewritten_query) candidate set with scores, giving the corpus-depth signal
- `resource_posture` (from Structure) — `speed_budget`, `confidence_bar`, `max_attempts` (the global constraint)
- **Eval's priors** — historical strategy-performance base rates conditioned on corpus depth (exact interface TBD with Eval — likely a lookup keyed by some depth-bucket + strategy, refreshed by the existing calibration loop)

## 4. Output — `RoutingLadder`

Per `change-request-observer-module.md` §5, unchanged in shape, reframed in how it's produced:
```python
@dataclass
class SlotLadder:
    slot_id: str
    strategy_sequence: list[str]   # e.g., ["a", "b", "c"] — the FULL sequence, planned once

@dataclass
class RoutingLadder:
    ladders: list[SlotLadder]
```
This is Router's one and only output for the loop. Whatever "final ranking/bandit-row-logging" role Router had in earlier framing is **not a second reasoning pass** — it's Router reporting the outcome of what it already decided, once the loop resolves (still ONE-WRITER on `rag_query_decisions`, unchanged from every prior design).

## 5. What's genuinely undesigned — the real optimization logic

1. **The corpus-depth bucketing** — how does Pool's raw BM25/vector scores translate into a "depth" signal Router can key priors on? Needs to be defined, likely jointly with Eval since they own the calibration side.
2. **The joint-allocation algorithm itself** — given N slots' depth signals + priors + a global time budget, what's the actual allocation logic? (Greedy by slot priority? A real constrained-optimization solve? Something simpler for v1 with a documented gap, same pattern as Slots' tag-only-v1 decision?) **This is squarely Eval + Router to design together, not something to build solo.**
3. **c/d/s strategy profiles** — where do their cost/effectiveness numbers come from? Existing calibration data, or need fresh measurement?
4. **Interface to Eval's existing priors infrastructure** — concrete lookup/API shape, not yet defined.

## 6. What's explicitly out of scope

- Observer's mechanical confidence-check (separate, simpler, already specced in `observer-module-spec.md`)
- Fillers' actual chunk-assignment execution (Router decides *what* strategy, Fillers executes it)
- Pool's candidate-fetching (already done, upstream)
- Synthesis/Contract/Timing (further downstream)

## 7. Process

1. **Co-design session with Eval first** — this is not a spec Router should draft solo and send for review; the optimization logic IS Eval's calibration/priors domain. Loop them in before writing anything definitive.
2. Once the joint-allocation approach is agreed, draft the full build spec (same format as every prior module).
3. Build with verify-before-trust discipline.
4. Test: this is the most NUMBER-MOVING module in the whole chain (it directly controls cost/latency/accuracy tradeoffs) — expect Eval's heaviest calibration bar of any module so far.
5. Cross-agent sign-off: Eval (co-designer, not just reviewer), Chat, UX, DB, TECH.
6. Report to Retriever.
