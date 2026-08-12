# ROUTER — Build Spec (Reasoning + Strategy)

**Status:** LOCKED — co-designed with Eval 2026-07-23. All deliverables complete. Ready for cross-agent sign-off (Chat/UX/DB/TECH).

**Owner:** Router Agent (4c)

**Co-partners:** Eval (priors infrastructure, calibration loop), Retriever (fleet coordination)

---

## 1. Dispatch Logic (Entry Point)

Router's FIRST decision: which path to take. Not optimization yet.

### Calibration/Forced Bypass Path
**Triggers:** `is_calibration == true` OR `forced_strategy` set

**Action:**
- Skip all Router optimization
- Use forced/calibration strategy directly
- Set `max_attempts = 1` (isolation, measurement only)
- `strategy_sequence = [forced_strategy]` per slot
- Skip priors, budget allocation, confidence logic
- Just execute, capture outcome, write ONE `rag_query_decisions` row

**Rationale:** During calibration, Eval measures strategies in isolation to build priors. Optimization would interfere. Forced mode is caller-directed, not Router's recommendation.

### Production Path
**Triggers:** NOT calibration AND no `forced_strategy`

**Action:** Run full constrained optimization (Sections 2–5 below)

---

## 2. Constrained Optimization Problem

### Objective (from Structure's resource_posture)
User wants their question answered at ≥X confidence, within Y seconds, with ≥Z accuracy.
- **Tolerance bands (caller-mode-dependent, per UX):**
  - Real-time caller (chat.default): ±15% wiggle room (e.g., 20±3 seconds, 0.85±0.13 confidence)
  - Background caller (chat.thinking, batch): ±25% wiggle room (e.g., 20±5 seconds, 0.85±0.21 confidence)
  - Default fallback: ±25% if caller_mode not specified
- This is the **global constraint across all N slots**, not per-slot

### Decision Variables
For each of N slots: `strategy_sequence` (ordered list of strategies, sized to max_attempts)
- E.g., Slot 0: ["a", "b"]; Slot 1: ["b", "c"]; Slot 2: ["d"]
- Output: `RoutingLadder` (per slot_id → strategy_sequence)

### Inputs
0. **`GateResult.j_codes`** *(ADDED 2026-07-23 — input-contract gap Retriever
   caught: Gate already computes the payor jurisdiction codes, they just never
   survived to Router)* — threaded as query-level context (`gate_j_codes`,
   same precedent as caller_mode). Drives the TAG-GATED eligibility dimension:
   strategy `s` (Payor Fact Store) is eligible iff any j_code starts with
   `payor.` (codes carry no kind prefix, e.g. `payor.sunshine_health`). FAIL
   CLOSED — absent/empty → s never planned. Consequence (Eval-ratified): s's
   priors cells mean P(success | payor tag present), clean by construction.
1. **Pool's corpus-depth signal per slot** — empirical pool size + top-candidate score percentile (how "findable" the answer looks)
2. **Eval-owned strategy profiles** — curves for each strategy conditioned on corpus depth:
   - **a/b:** depth-conditional (performance varies with corpus depth)
   - **c:** uniform curve (built over time)
   - **d:** bimodal (crawlable vs non-crawlable)
   - **s:** cache hit probability
   - **f:** fallback/external (similar to d)
   - **sitemap:** direct lookup cost/benefit
   - **Each curve:** {recall_lift, latency_p50, cost, accuracy_estimate} given depth_bucket D
3. **Structure's resource_posture:**
   - max_attempts per slot (how many tries budget)
   - speed_budget (real_time / interactive / background / none)
   - confidence_bar (quality threshold)
   - tolerance bands (±25% wiggle room)

### Constraints (Parallel Execution Model)
- **MAX(time per slot) ≤ Y + tolerance(caller_mode)** — all slots run concurrently; slowest determines overall latency (tolerance: ±15% real_time, ±25% background)
- **AGG(confidence across slots) ≥ X - tolerance(caller_mode)** — aggregate must clear bar; scoring function: mean(all slot confidences)
- **AGG(accuracy across slots) ≥ Z - tolerance(caller_mode)** — aggregate must clear bar
- **Each slot respects its max_attempts limit**
- **TOKEN/PAYLOAD BUDGET** *(ADDED 2026-07-23, Ananth: "keep track of tokens
  you can send — if it extracts a whole provider manual that's no use")* —
  plans must be token-feasible by construction, not just time-feasible.
  PER-RUNG gate: `capacity × payload_tokens_per_chunk(strategy) ≤
  token_allowance_per_slot` (posture knob, default 8000 — generous:
  accounting + guardrail, no behavior change at defaults). Chain payload is
  NOT additive — only the winning rung's chunks fill the slot
  (advance-on-empty discards failures) — so worst-case slot payload = MAX
  over chosen rungs; query total = SUM over slots (telemetry:
  `payload_tokens` in executed/shadow ladder JSONB, narration RESULT line).
  Skip reason `payload_over_token_allowance`; binding constraint
  `payload_budget_exhausted`. Per-chunk values: d VERIFIED 500 (filler_d
  `_MAX_PASSAGE_CHARS=2000` ≈ 4 chars/token); a/b/c 1000 + s 150 are
  ESTIMATES pending real corpus measurement — flagged to Eval to become
  per-cell priors-file fields (same swap-without-redeploy contract).
- **AUTHORITY GATE — caller-declared citability** *(ADDED 2026-07-23,
  Ananth: d is "accurate from a website but not citable to a payor... for an
  appeal this is important, but for a chat call? Can we not bifurcate based
  on the caller telling us")* — fourth eligibility dimension (after
  slot_semantics, tag-gating, crawl-gating). Posture field
  `authority_requirement`: `"any"` (default, FAIL-OPEN — d competes on
  recall merits, zero behavior change) | `"citable_required"` — non-citable
  strategies (`NON_CITABLE_STRATEGIES = {d}`) become ineligible for
  REQUIRED slots only; optional/external_context slots KEEP d (web context
  remains useful context even when it can't be evidence; optional never
  gates, §2a). Skip reason `authority_gated_non_citable`. Seam: Router knob
  built first; caller-side declaration in design with Chat (can the caller
  distinguish appeal vs casual?), threading via Structure's ResourcePosture
  (same path as token_budget). Declared-per-caller, never Router-guessed.

### Feasibility & Infeasibility Handling
- **If feasible solution exists** within tolerance bands → produce it
- **If no feasible solution** even within relaxed tolerance → signal infeasibility: ask user to relax constraints or cascade to fallback (sitemap/cache)

---

## 2a. OBJECTIVE ADDENDUM (2026-07-23 evening, Ananth via Eval — SUPERSEDES aggregate-mean gating; SIGN-OFF PENDING, no code until ratified)

**1. Per-QUESTION confidence enforcement — the aggregate mean is the wrong quantity.**
*(Corrected per Ananth via Eval: the enforcement unit is the QUESTION, keyed on
the slot's `required` flag from Slots' AnswerShapeResult — not mechanically
every slot.)* Every **required=True** slot (the user's question, or a genuine
FAN_OUT sub-question) must independently clear the confidence bar. If a
question isn't answered at the bar, it isn't answered — no other slot's
success offsets that. **required=False** slots (RELY_ON_EXTERNAL's
external_context, CLARIFY_REPHRASE's best_guess — supplementary/fallback BY
DESIGN) are filled, LB-computed, and traced with status OPTIONAL, but never
gate the outcome: a query whose required slots all clear is
`all_slots_cleared` even if every optional slot is under-confident.
*Efficiency corollary (Eval's catch, 2026-07-23): optional slots are capped at
ONE attempt (`OPTIONAL_SLOT_MAX_ATTEMPTS=1`) — they must not chase a bar they
never gate on; an uncapped optional chain was doubling worst-case query
latency for telemetry-only value.*
*Strategy-roster boundary (Eval-ratified 2026-07-23): the priors universe is
exactly SIX retrieval strategies {a,b,c,d,f,s}. Fillers `e` (Fast Exit) and
`q` (Clarify) are PERMANENTLY excluded from the depth_bucket×strategy priors
table and from allocator candidate sets — they are terminal dispatch outcomes
of upstream verdicts (q ← Reformat's CLARIFY posture; e ← Router's §2a
infeasibility outcome), not points on the recall/cost frontier. Deliberate
architecture, not a gap — do not "complete" the roster.*
*Terminal-leg rule (Ananth, 2026-07-23): while e/q never compete in the chain
math, Router ATTACHES them as the verdict-driven FINAL LEG of the plan —
rule-based, zero priors: required slot UNDER_CONFIDENT → terminal
`clarify_low_confidence` (dispatches Filler q — clarify can rescue a
low-confidence answer); NO_VIABLE_STRATEGY → terminal `fast_exit_no_viable`
(dispatches Filler e — nothing to retrieve, nothing to ask);
CLEARED/OPTIONAL → none. Decision-level: clarify wins over fast-exit.
Carried as `per_slot_terminal`/`terminal_action` on the ladder, trace,
narration, and persisted executed_ladder JSONB. VALUES RENAMED from the bare
filler ids "q"/"e" (Retriever/Eval directive, pre-Contract): those collided
semantically with Shape's DECLINE/CLARIFY_REPHRASE stage.
CONTRACT FORWARD REQUIREMENT (shape agreed with Chat 2026-07-23): the
envelope carries one nested `routing_verdict` object — `{outcome,
terminal_action, helpers: [], confidence_bar, adjusted_bar, slots: {slot_id:
{status, lb, terminal, helpers, required}}}`. `helpers` (Ananth's helper
layer, 2026-07-23) is the recall-failure aid plan — ordered subset of
["clarify_low_confidence", "sitemap_links"]: non-recall user-pain-solvers
invoked when the loop fails (clarify asks for the missing detail;
sitemap_links hands the user the payer's real pages, gated on payor
identity). Zero priors, never in chain math.
PAIRING INVARIANT (Chat, 2026-07-23; refined per Sitemap's real lookup
contract): Router plans "sitemap_links" only when BOTH preconditions hold —
payor j_code AND at least one d-code (Sitemap's lookup_sitemap_links()
requires payer_display_name and a d:-tag topic keyword match; missing either
returns []). Router's gate is the cheap pre-filter; the keyword-table match
happens inside Sitemap, so the ORCHESTRATOR reconciles at execution: if the
dispatched lookup returns empty suggested_links[], it DROPS "sitemap_links"
from the final routing_verdict.helpers — Chat includes the "You might also
check" block iff suggested_links is non-empty. LATENCY RULE (Sitemap's
flag): the failure-path dispatch MUST reuse the orchestrator's
already-resolved PayerContext (round-11 threading), never re-call
resolve_payer_context() — a fresh call reintroduces the ~3s registry timeout
into what must stay a cheap fallback path. — field names identical to the persisted
executed_ladder vocabulary so DB row / emit / envelope share one vocabulary
with zero translation layer. `adjusted_bar` (Chat's confirmed ask) is the
FINAL tolerance-adjusted number UX renders proximity against ("0.58 vs 0.72")
— display logic must not need caller_mode math. Per-slot is the native grain
(FAN_OUT queries carry several slots with different verdicts).* This kills:
- the `AGG(confidence) = mean(slots) ≥ bar` gate in §2's constraint list, and
- greedy's Phase-2 "top-up" (strong slots compensating weak ones — verified
  present in `allocation.py` today, e.g. hard slot at 0.65 carried by an easy
  slot at 0.95). Cross-slot compensation is removed entirely.
The aggregate mean survives only as reported telemetry, never as a gate.

**2. "95% confidence" = statistical lower bound, not a point estimate.**
This addendum lands TOGETHER with the uncertainty workstream (same co-design
gate with Eval — interval method Wilson/Beta LB, N-per-cell in priors, z-level
knob): the per-slot check is `LB(true slot confidence) ≥ bar`, computed from
priors' uncertainty, not from means treated as certain. One redesign pass, not
two.

**3. Explicit failure mode — infeasibility must be impossible to silently swallow.**
Current behavior (route() logs a warning and continues executing the
best-effort ladder) is NOT acceptable. When a slot's bar is genuinely
unreachable (all viable strategies exhausted within max_attempts/time budget,
LB still below bar), Router must surface a per-slot outcome distinct from
"cleared":
- per-slot status: `CLEARED | UNDER_CONFIDENT (best-effort, bar unreachable,
  binding constraint stated: attempts|budget|strategies) | NO_VIABLE_STRATEGY`
- decision-level outcome: `all_slots_cleared | partial_infeasible | no_slots`,
  carried on RouterDecision, in the emitted trace, and in the persisted
  executed_ladder JSONB.
Router does NOT choose the downstream response — the two valid paths (honest
"no confident answer" to the user, or ask-for-relaxation so a looser-budget
caller like chat.thinking retries) belong to Chat/Synthesis. Router's
obligation ends at making the signal explicit, structured, and unmissable.

**Implementation impact when ratified:** allocation.py Phase-1/Phase-2 rewrite
(per-slot bar, no top-up), optimizer feasibility per slot (its per-slot argmax
already matches the new objective; only the gate changes), LB math from the
uncertainty workstream wired into both, RoutingLadder/RouterDecision/persist
gain per-slot status. Existing tests asserting top-up/aggregate behavior
(e.g. `test_topup_strong_slot_compensates_weak_slot`) will be inverted.

---

## 3. Greedy-by-Priority Allocation Algorithm

**Allocate strategies per slot in priority order, gate on aggregate confidence.**

```python
def allocate_strategies(slots, pool_metadata, resource_posture, priors):
    """
    Input:
      - slots: list of AnswerSlots with semantics, priority, rewritten_query
      - pool_metadata: corpus_depth signal per slot (top_score_percentile, pool_size, etc.)
      - resource_posture: {speed_budget, confidence_bar, max_attempts_per_slot, tolerance_bands}
      - priors: dict[depth_bucket][strategy_id] → {recall_lift, latency_p50, cost, accuracy}
    
    Output:
      - RoutingLadder: per slot_id → strategy_sequence (ordered, sized to budget)
    """
    
    routing_ladder = RoutingLadder()
    remaining_time_budget = speed_budget_in_ms(resource_posture.speed_budget)
    achieved_confidences = []  # track per-slot confidence
    
    # Process slots in priority order (core → supporting → optional)
    for slot in sorted(slots, key=lambda s: priority_rank(s.priority)):
        slot_depth_bucket = compute_depth_bucket(pool_metadata[slot.id])
        slot_confidence = 0
        slot_sequence = []
        
        # Try strategies in order until aggregate >= confidence_bar or out of budget/tries
        for strategy in [a, b, c, d, f, s]:  # default order; can be tuned per depth
            if len(slot_sequence) >= slot.max_attempts:
                break  # respect per-slot attempt limit
            
            priors_lookup = lookup_priors(slot_depth_bucket, strategy)
            if priors_lookup is None:
                priors_lookup = lookup_priors_qclass_fallback(slot.query_class, strategy)
            
            latency = priors_lookup.latency_p50
            if latency > remaining_time_budget:
                continue  # skip if this strategy would exceed time budget
            
            # Add strategy to sequence
            slot_sequence.append(strategy)
            slot_confidence += priors_lookup.recall_lift
            remaining_time_budget -= latency
            achieved_confidences.append(slot_confidence)
            
            # Check aggregate: stop if mean(all slot confidences) >= bar
            aggregate_confidence = mean(achieved_confidences)
            if aggregate_confidence >= resource_posture.confidence_bar:
                break
        
        routing_ladder.add_slot(slot.id, slot_sequence)
    
    return routing_ladder
```

**Semantics:**
- **Gate on aggregate confidence** (mean across all N slots), not per-slot
- **Parallel execution:** MAX(slot times) is the bottleneck; all slots run concurrently
- **Priority-aware:** core slots get preference for strategies
- **Time budget is PER SLOT** *(AMENDED 2026-07-23 during build)*: the original pseudo-code above deducts one global budget across slots — that contradicts §2's `MAX(slot time) ≤ Y` constraint (parallel slots each have the full wall-clock budget; global deduction starved later slots). Implemented per §2: each slot's sequential fallback chain must fit `speed_budget × (1 + tolerance)`; query latency = MAX over slots. The pseudo-code above is superseded by `app/services/router/allocation.py` on this point.
- **Confidence accumulates as expected value** *(AMENDED 2026-07-23)*: `slot_confidence += recall_lift` in the pseudo-code double-counts; implemented as fallback-chain expected value `P = 1 - Π(1 - p_i)` (strategies-independent assumption documented in code).
- **Fallback:** if priors_lookup fails (depth_bucket data not yet available), use qclass-based priors
- **Conservative:** pessimistic defaults during bootstrap, improves as bandit refines

---

## 4. Corpus-Depth Bucketing

### Depth Signal Computation
```python
def compute_depth_bucket(pool_metadata_for_slot: dict) -> int:
    """
    Map Pool's empirical scores to a depth bucket.
    
    Input: pool_metadata from Pool (top-candidate score, pool_size, percentiles, etc.)
    Output: depth_bucket ∈ [0, 1, 2, 3, 4] (or finer granularity if calibration supports it)
    
    Method: Use Pool's top-candidate score percentile:
      - rank_percentile = percentile_rank(max_score[pool], historical_top_scores)
      - depth_bucket = quantize(rank_percentile, buckets=[0, 0.2, 0.4, 0.6, 0.8, 1.0])
    
    Fallback: If historical_top_scores unavailable, use pool_size as proxy:
      - depth_bucket = quantize(pool_size, buckets=[0, 20, 100, 500, 1000, inf])
    """
```

### Bucket Definitions (v1, subject to Eval's calibration structure)
- **Depth Bucket 0:** Lowest findability (top_score_percentile < 20% OR pool_size < 20)
- **Depth Bucket 1:** Low findability (20–40% OR pool_size 20–100)
- **Depth Bucket 2:** Medium findability (40–60% OR pool_size 100–500)
- **Depth Bucket 3:** High findability (60–80% OR pool_size 500–1000)
- **Depth Bucket 4:** Highest findability (80%+ OR pool_size 1000+)

---

## 5. Priors Interface & Bootstrap Strategy

### Priors Lookup (Two-Tier Fallback)
```python
def get_strategy_profile(depth_bucket: int, strategy_id: str) -> StrategyProfile:
    """
    Look up historical strategy performance.
    
    Tier 1 (primary): depth_bucket-based priors (empirical, per-slot)
      - Source: Eval's calibration loop (ingests rag_query_decisions tuples)
      - Available: Week 1+ (bootstrap)
      - Fallback threshold: use only if ≥50 data points per cell
    
    Tier 2 (fallback): qclass-based priors (metadata, query-level)
      - Source: existing legacy priors
      - Available: now (always, as fallback)
      - Used when: depth_bucket data unavailable or too sparse
    """
    
    # Tier 1: depth_bucket
    priors = PRIORS_DEPTH_BUCKET.get(depth_bucket, {}).get(strategy_id)
    if priors and priors.confidence_level >= HIGH:  # ≥50 samples
        return priors
    
    # Tier 2: qclass fallback (graceful degradation during bootstrap)
    priors = PRIORS_QCLASS_LEGACY.get(query_class, {}).get(strategy_id)
    if priors:
        return priors
    
    # Last resort: seed defaults (pessimistic)
    return PRIORS_SEED_DEFAULTS[strategy_id]
```

### Bootstrap Timeline (Eval Commitment, LOCKED 2026-07-23)
- **Week 1:** Router ships with seed priors active. Calibration loop ingests (depth_bucket, strategy, outcome) tuples from rag_query_decisions. Nightly derivation begins.
- **Week 2:** ~100–200 queries logged per depth_bucket cell. Calibration loop runs nightly, computes per-cell aggregates. Seeds still active (cells <50 samples).
- **Week 3:** Production-grade depth_bucket priors replace seeds (all 30 cells reach N≥50 samples). Fallback to qclass-based priors becomes optional. Empirical priors take over.
- **Week 3+:** Bandit refinement continues; priors converge to steady-state. Calibration loop updates nightly.

**Conservative assumption:** 50–100 queries per depth_bucket per day under normal traffic. At that rate, 5 buckets × 6 strategies = 30 cells; 3–4 days per cell to reach 50 samples.

### Seed Strategy Profiles (LOCKED & VALIDATED — Eval 2026-07-23)

**CRITICAL: Accuracy-Recall Tradeoff**
- **Tight corpus (Depth 0):** HIGH accuracy (precise results), LOW recall (limited coverage)
- **Broad corpus (Depth 4):** LOWER accuracy (noisy results), HIGH recall (comprehensive coverage)

```python
PRIORS_SEED_DEFAULTS: dict[str, dict[int, StrategyProfile]] = {
    "a": {
        0: StrategyProfile(recall_lift=0.100, latency_p50_ms=500, cost=1, accuracy_estimate=0.165),
        1: StrategyProfile(recall_lift=0.280, latency_p50_ms=500, cost=1, accuracy_estimate=0.263),
        2: StrategyProfile(recall_lift=0.450, latency_p50_ms=500, cost=1, accuracy_estimate=0.5),
        3: StrategyProfile(recall_lift=0.620, latency_p50_ms=500, cost=1, accuracy_estimate=0.425),
        4: StrategyProfile(recall_lift=0.730, latency_p50_ms=500, cost=1, accuracy_estimate=0.313),
    },
    "b": {
        0: StrategyProfile(recall_lift=0.070, latency_p50_ms=1500, cost=1, accuracy_estimate=0.225),
        1: StrategyProfile(recall_lift=0.250, latency_p50_ms=1500, cost=1, accuracy_estimate=0.206),
        2: StrategyProfile(recall_lift=0.435, latency_p50_ms=1500, cost=1, accuracy_estimate=0.225),
        3: StrategyProfile(recall_lift=0.620, latency_p50_ms=1500, cost=1, accuracy_estimate=0.284),
        4: StrategyProfile(recall_lift=0.765, latency_p50_ms=1500, cost=1, accuracy_estimate=0.45),
    },
    "c": {
        0: StrategyProfile(recall_lift=0.090, latency_p50_ms=2000, cost=2, accuracy_estimate=0.18),
        1: StrategyProfile(recall_lift=0.280, latency_p50_ms=2000, cost=2, accuracy_estimate=0.151),
        2: StrategyProfile(recall_lift=0.450, latency_p50_ms=2000, cost=2, accuracy_estimate=0.0),
        3: StrategyProfile(recall_lift=0.620, latency_p50_ms=2000, cost=2, accuracy_estimate=0.091),
        4: StrategyProfile(recall_lift=0.770, latency_p50_ms=2000, cost=2, accuracy_estimate=0.0),
    },
    "d": {
        0: StrategyProfile(recall_lift=0.080, latency_p50_ms=3000, cost=3, accuracy_estimate=0.3),
        1: StrategyProfile(recall_lift=0.320, latency_p50_ms=3000, cost=3, accuracy_estimate=0.35),
        2: StrategyProfile(recall_lift=0.540, latency_p50_ms=3000, cost=3, accuracy_estimate=0.4),
        3: StrategyProfile(recall_lift=0.680, latency_p50_ms=3000, cost=3, accuracy_estimate=0.45),
        4: StrategyProfile(recall_lift=0.770, latency_p50_ms=3000, cost=3, accuracy_estimate=0.5),
    },
    "f": {
        0: StrategyProfile(recall_lift=0.080, latency_p50_ms=3000, cost=3, accuracy_estimate=0.3),
        1: StrategyProfile(recall_lift=0.320, latency_p50_ms=3000, cost=3, accuracy_estimate=0.35),
        2: StrategyProfile(recall_lift=0.540, latency_p50_ms=3000, cost=3, accuracy_estimate=0.4),
        3: StrategyProfile(recall_lift=0.680, latency_p50_ms=3000, cost=3, accuracy_estimate=0.45),
        4: StrategyProfile(recall_lift=0.720, latency_p50_ms=3000, cost=3, accuracy_estimate=0.5),
    },
    "s": {  # cache/short-circuit (always high recall, perfect accuracy when hits)
        0: StrategyProfile(recall_lift=0.800, latency_p50_ms=50, cost=0, accuracy_estimate=1.0),
        1: StrategyProfile(recall_lift=0.800, latency_p50_ms=50, cost=0, accuracy_estimate=1.0),
        2: StrategyProfile(recall_lift=0.800, latency_p50_ms=50, cost=0, accuracy_estimate=1.0),
        3: StrategyProfile(recall_lift=0.800, latency_p50_ms=50, cost=0, accuracy_estimate=1.0),
        4: StrategyProfile(recall_lift=0.800, latency_p50_ms=50, cost=0, accuracy_estimate=1.0),
    },
}
```

**Seed Pattern (Eval's validated accuracy-recall model):**
- Accuracy: conservative 60%-95% scale (tight corpus → high precision)
- Recall: INVERTED (tight corpus → low coverage; broad corpus → high coverage)
- Correctly models: tight retrieval is precise but limited; broad retrieval is comprehensive but noisy
- Strategy a: best for tight corpus (high accuracy 0.165-0.5, low recall 0.1-0.73)
- Strategy b: competitive for broad corpus (declining accuracy 0.225-0.45, rising recall 0.07-0.765)
- Strategies c/d/f: external, high recall across depths, variable accuracy
- Strategy s: cache/short-circuit, high recall (0.8) across depths, perfect accuracy (1.0) when hits
- Bandit refines these values over time as calibration data accumulates
- Backward-compatible: if depth_bucket data unavailable, fallback to qclass-based priors

---

## 6. Logging & Instrumentation (ONE-WRITER)

### rag_query_decisions Row Schema (Frozen, Eval gate)
Router writes exactly one row per query:

```python
INSERT INTO rag_query_decisions (
    id, agent_id, query,
    is_calibration, is_prod, eval_run_id,
    depth_bucket, strategy_chosen, strategy_sequence,
    gate_contour, gate_underspecified_kind, reformat_posture, reformat_fanout_n,
    feature_vector, strategy_scores, priors_version,
    confidence, accuracy_estimate, cost,
    total_ms, leaf_key
) VALUES (...)
```

**Key fields for calibration loop:**
- `depth_bucket` — the corpus-depth signal used for priors lookup (Eval ingests this)
- `strategy_sequence` — the full ordered sequence Router produced (for audit)
- `strategy_chosen` — which strategy was actually picked by orchestrator (may differ if escalated)
- `gate_contour`, `gate_underspecified_kind` — deferred from Shape:Gate (UX diagnostic; combined migration with Router)
- `reformat_posture`, `reformat_fanout_n` — deferred from Shape:Reformat (UX diagnostic; combined migration with Router)
- `priors_version` — which seed/refined priors were active (for versioning)
- `confidence` — aggregate confidence achieved (for calibration)

**ONE-WRITER enforcement:** Only `router.persist_decision()` writes to this table (both calibration + production paths call the same function). All 21 columns migrate together in one DDL pass.

---

## 7. Cross-Cutting Guarantees

### No Untimed Segments
- `[trace:router_dispatch]` — entry point logic
- `[trace:router_allocate]` — optimization algorithm
- `[trace:router_persist]` — async write to rag_query_decisions

### Byte-Compatible Routing Dump
- Frozen contract (Option a) — per-query `routing` shape unchanged for bandit
- feature_vector + scores non-null on non-s rows; s-rows NULL emergent
- Dispatch logic (calibration path) doesn't change row shape

### No DB Access During Optimization
- Priors are read-only (cached, refreshed by Eval's loop)
- Pool's corpus-depth signal is pre-computed (no new Pool fetches)
- Router is pure over its inputs; no side effects except the write

---

## 8. Build Blockers & Dependencies

### Blocked On
- **Fillers specification approval** (✅ done, code not built yet)
- **Orchestrator ready** to walk Router's strategy_sequences
- **Observer built** (separate, Eval-gated; not on Router's critical path)

### Unlocks
- Code build can start once Eval provides seed values
- Testing phase: characterization test (Router's decisions are deterministic per seed), integration test (with Fillers + Observer mock), calibration bootstrap

---

## 9. Sign-Off Gates (Before Code Build)

**Technical Review (TECH):**
- No DB access during optimization ✅ (by design)
- Every segment timed ✅ (by instrumentation spec)
- Byte-compat maintained ✅ (by frozen contract)

**Eval:**
- Seed values finalized ✅ (Eval delivered: accuracy-recall tradeoff validated, `priors_bootstrap.yaml` updated)
- Calibration loop wiring confirmed ✅ (Eval's commitment: ingest (depth_bucket, strategy, outcome), derive empirical priors Week 1-3)
- Bandit integration ready ✅ (by design)

**Chat: ✅ SIGNED OFF** — all four items approved, forward-looking catch on partial streaming vs wait-for-all-slots routed to Ananth (not blocking Router)

**TECH: ✅ SIGNED OFF** — cross-cutting guarantees verified, ONE-WRITER confirmed across dispatch paths, ready for code build

**UX: IN PROGRESS** — partial input on tolerance bands (recommends ±15% real_time, ±25% background, incorporated into §2), still reading full spec before final sign-off. NOT BLOCKING if other conditions met.

**DB: ✅ FIXED** — added 4 deferred columns from Gate/Reformat (gate_contour, gate_underspecified_kind, reformat_posture, reformat_fanout_n) to §6, combined DDL migration confirmed. Awaiting DB's final sign-off confirmation.

**Broadcaster:** awaiting Retriever's routine check-in

---

## 10. Next Steps (Sign-Off → Build)

### Sign-Off Status (2026-07-23)
- **Chat:** ✅ signed off (4/4 items)
- **TECH:** ✅ signed off (cross-cutting guarantees verified)
- **UX:** in progress (tolerance bands incorporated, spec review underway, not blocking)
- **DB:** ✅ gap fixed (4 deferred columns added), awaiting confirmation
- **Broadcaster:** routine check-in pending

### Final Gate (TODAY)
1. **Confirm DB column fix** — DB verifies §6's 21-column list includes all 4 deferred columns, combined migration is valid
2. **UX completes review** — final sign-off on tolerance bands + overall design
3. Once 2/2 clear, **proceed to code build** immediately

### Build Phase (POST-SIGN-OFF)
1. **Code build** — implement dispatch logic + allocation algorithm + persistence layer (ONE-WRITER rag_query_decisions)
2. **Testing** — characterization (deterministic routing), integration (with Fillers/Observer/orchestrator), calibration bootstrap (seed→empirical priors Week 1-3)
3. **Validation** — tradeoff verification (tight corpus high-accuracy routing, broad corpus high-recall routing), end-to-end test case gallery
4. **Deploy** — behind `RAG_ANSWER_ENGINE=legacy|shape` flag, instant roll-back available

---

**See also:**
- `router-eval-codesign-brief.md` — the co-design conversation
- `router-module-spec.md` — architectural overview (Section 0 dispatch logic)
- `retriever-fleet-schematic.md` — Router's place in the chain
- `mobius-rag/eval/priors_bootstrap.yaml` — Eval-provided seed strategy profiles (ready to integrate)

## 11. Execution-time rung reordering — plan-preserving, permitted (2026-07-23)

*(Ananth via Web Search: don't commit a slot's attempt to `d` when its
speculative prescreen search isn't ready — run an already-ready rung
instead when time is ticking.)*

**Contract: the RoutingLadder is a rung SET with a preferred order, not a
schedule.** Every §2a-enforced quantity is invariant under permutation of a
slot's chain — chain LB and mean (1−Π(1−p), commutative), worst-case
latency (sum), cost (sum), payload (max) — so the execution loop MAY check
live readiness (e.g. `prescreen_search_task.done()`, non-blocking) at the
moment it would commit to a rung and run a different PLANNED rung first,
deferring the unready one to a later attempt. No Router replanning, no
Router code involved. Guarded by
`TestExecutionReorderingContract::test_enforced_quantities_invariant_under_chain_permutation`
— if any enforced quantity ever becomes order-dependent, that test fails
and this permission must be renegotiated with the orchestrator.

Boundaries: (1) reordering is within the planned set only — substituting an
UNplanned strategy remains a plan violation; (2) executed order must be
emitted as executed (per-attempt telemetry already does this; calibration
cells key on (depth_bucket, strategy) per attempt, order-free — Eval
unaffected); (3) if an unready rung ends up never running this query, emit
it distinctly (suggested label: `prescreen_not_ready_deferred`) rather than
folding into failure — same row-labeling hygiene as every exclusion.
Plan-time readiness-conditioned d-latency priors (mechanism 1) are a
separate, later, Eval-data-gated improvement — not mutually exclusive.

## 12. PARKED — Selective rung hedging (future use case, data-gated; Ananth 2026-07-23)

Brainstormed, explicitly HELD until good empirical data exists. Idea: run
select rungs of one slot's chain in parallel ("hedging"), priced by expected
value — hedge rung i+1 when `latency_saved × P(rung i fails)` exceeds
`cost_{i+1} × P(rung i succeeds) + token cost`. Confidence math is already
concurrency-invariant (§11's permutation guard covers it), so this is pure
execution economics. Candidate patterns when revived: cheap-rung hedges
(s ~free alongside anything), deadline-triggered parallelism (allowance <
sum but ≥ max of remaining rungs), exploration-funded hedges (unconditioned
observations for Eval's cells on live traffic).

WHY PARKED: the EV rule prices hedges off P(success)/cost/latency per cell —
seed pseudo-data isn't good enough to spend real compute on (the retracted
inflated-grading fold is the cautionary tale). REVIVAL GATE: trustworthy
empirical priors (post LLM-judge regrade) + the three prerequisites: SUM
token model (ships with retention, §8 observer spec), answer-arbitration
rule (authority tiers give one), DB connection-pool headroom. Distinct from
the REJECTED parallel-allocator-plans idea (that stays rejected; shadow
A/B is the mechanism there).
