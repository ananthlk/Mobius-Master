# Router — Eval Co-Design Brief

**To:** Eval Agent  
**From:** Router Agent (4c) + Ananth  
**Date:** 2026-07-23  
**Purpose:** Align on Router's constrained optimization problem; surface what we need from Eval's priors/calibration infrastructure.

---

## Router's job (one-sentence framing)

Given N decomposed sub-questions + Pool's corpus-depth signal per question + Eval-owned strategy profiles + a global confidence/time/accuracy budget, Router optimizes the strategy allocation (which strategy to try first/second/etc for each question) to meet the user's constraints within tolerance bands. Runs once, upfront. Bandit refines strategy profiles over time.

---

## The constrained optimization problem

**Objective (from Structure's resource_posture):**
- User wants their question answered at ≥ X confidence, within Y seconds, with ≥ Z accuracy
- All with ±25% tolerance bands (e.g., 20±5 seconds, 0.85±0.21 confidence)

**Decision variables (what Router produces):**
- For each of N slots: `strategy_sequence` (ordered list of strategies a/b/c/d/f/s/sitemap, sized to max_attempts)
- E.g., Slot 1: ["a", "b"]; Slot 2: ["b", "c"]; Slot 3: ["d"]

**Inputs to the optimization:**
1. **Pool's corpus-depth signal per slot** — empirical pool size (20 vs 20k embeddings) tells us answer findability
2. **Eval-owned strategy profiles** — curves for each strategy conditioned on depth:
   - a/b: depth-conditional (tight corpus → different profile than wide)
   - c: uniform curve (built over time)
   - d: bimodal (crawlable vs non-crawlable)
   - s: cache hit probability
   - f: fallback/external (similar to d)
   - sitemap: direct lookup cost/benefit
   - Each curve: {recall, accuracy, speed, cost} given depth bucket D
3. **Structure's resource_posture:**
   - max_attempts per slot (how many tries budget)
   - speed_budget (real_time / interactive / background / none)
   - confidence_bar (quality threshold)
   - tolerance bands (±25% wiggle room)

**Constraints (parallel execution, weakest link model):**
- MAX(time per slot) ≤ Y + tolerance (all slots run concurrently; slowest determines overall latency)
- AGG(confidence across slots) ≥ X - tolerance (aggregate must clear bar — scoring function TBD with Eval)
- AGG(accuracy across slots) ≥ Z - tolerance (aggregate must clear bar — scoring function TBD)
- Each slot respects its max_attempts limit

**Feasibility:**
- If a feasible solution exists within tolerance bands, Router produces it
- If not, signal infeasibility: ask user to relax constraints or cascade to fallback (sitemap/cache)

**Seed + Bandit loop:**
- Router starts with hand-set seed strategy curves (plausible defaults, not final)
- Fillers executes the strategy_sequence
- Observer measures confidence per attempt
- rag_query_decisions row written (ONE-WRITER, existing schema)
- Bandit ingests outcomes, refines strategy curves over time
- Next query, Router uses refined curves for better decisions
- Curves asymptotically improve as more data flows through

---

## What Router needs from Eval (co-design domain)

1. **Seed strategy curves** — what are reasonable hand-set baseline values for a/b/c/d/s profiles?
   - Format: per strategy, per depth bucket, what are {recall, accuracy, speed, cost}?
   - Conservative defaults to start, or optimistic?

2. **Corpus-depth bucketing** — how should Router discretize Pool's scores into depth buckets?
   - Suggested: 20, 50, 100, 200, 500, 1000, 5000, 20000 embeddings?
   - Or a continuous function? Logarithmic? Percentile-based?

3. **Aggregate scoring function** — how to combine confidence/accuracy across N slots into a global score?
   - Min across slots? Weighted by priority (core/supporting/optional)? Mean? Something else?

4. **Priors API interface** — what's the exact shape Router queries for strategy profiles?
   - Likely: `lookup(strategy_id, depth_bucket) → {recall, accuracy, speed, cost, [other]}`
   - Should this live in a database table, a config file, an in-memory cache?
   - Refresh schedule (per query? per day? per calibration cycle)?

5. **Tolerance band semantics** — is ±25% the right default, or does it vary?
   - Vary by user/context? By caller_mode (chat.default vs chat.thinking)?
   - Should be configurable in resource_posture?

6. **Calibration plan** — what's Eval's commitment to measure seeds + bandit loop?
   - Timeline: when will bandit have initial data to refine curves?
   - Metrics: what before/after scores will you track? (per-strategy recall/accuracy/latency? cost per query? retry rate?)
   - Will you flag regressions so Router can hold on suboptimal allocations?

---

## What's already locked (not negotiable for this phase)

- ✅ Dispatch logic: calibration/forced bypass skip all optimization (isolated measurement only)
- ✅ Single reasoning pass upfront, before Fillers acts (no re-optimization per attempt)
- ✅ Parallel execution: MAX(slot times) is the bottleneck, not sum
- ✅ ONE-WRITER on rag_query_decisions (both calibration + production paths write the same row)
- ✅ Seed + bandit loop approach (start with defaults, improve over time)

---

## Timeline/Next Steps

1. **Eval's feedback** — reactions to the optimization framing + answers to the 6 open questions above
2. **Joint design session** — Eval + Router + Ananth, ~1h, to align on:
   - Seed curve values
   - Depth bucketing strategy
   - Aggregate scoring function
   - Priors API shape
3. **Router's build spec** — once jointly decided, Router drafts the full implementation spec (same format as prior modules)
4. **Code build** — blocked on Fillers being built (orchestrator + Fillers must exist to run strategy_sequences)

---

## Reference docs

- Full Router spec: `router-module-spec.md` (includes dispatch logic, Section 0)
- Fleet schematic: `retriever-fleet-schematic.md`
- Observer spec: `observer-module-spec.md` (separate module, parallel checking, not part of this co-design)
