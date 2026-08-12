# OBSERVER Module Spec (Step 4e, between Fillers and Router's continuation decision) — v2

**Status:** BUILT — `app/services/retriever/observer.py`, real per-strategy logic for a/b/c/s + d (decay-floor, reusing Filler b's 0.6x-of-top-score pattern against real BM25 `original_score`), 23/23 tests passing. NOT yet wired into `orchestrator.py`'s production loop — gated on Eval's committed calibration plan (`observer-calibration-plan.md`, drafted 2026-07-24), which is the one remaining condition. Cross-agent sign-off in progress (a/b/c/s routed to Chat/DB/TECH; d fast-follows).
**Owner:** "Observer 4e" session, under Retriever.

**Lineage — read this before trusting any other Observer doc in this directory.** This module went through two real design generations before landing here, neither formally marked superseded in writing until this rewrite (a real documentation gap, caught 2026-07-24 when Observer went looking for a spec to route alongside sign-off and found three contradictory drafts):

1. **v1 (this doc's original content, 2026-07-23)** — a mechanical bool+float+bool verdict (`ObserverVerdict{satisfied, confidence_score, speed_budget_exceeded}`), Observer itself checking `speed_budget` as a hard ceiling on every call.
2. **Bayesian addendum (`observer-bayesian-confidence-spec.md`, 2026-07-23)** — superseded v1's "purely mechanical" framing with a live per-slot Beta-posterior confidence update, a "ceiling test" against optimistic remaining strategies, and Router's ladder becoming a ranked candidate pool instead of a fixed sequence. **Never built. SUPERSEDED as of this rewrite** — see that file's own banner.
3. **This spec (v2, what's actually built)** — decided directly with Ananth, 2026-07-24, refining scope back down past even v1's complexity: no confidence-score float, no Beta posteriors. Each filler answers one strategy-specific yes/no — "would this slot benefit from another turn" — using whatever criteria fits that strategy (no shared confidence scale across strategies, Ananth's explicit call). Verdicts are Router's own enum (`app/services/router/continuation.py`), imported not redefined: `WOULD_BENEFIT` / `SATISFIED` / `EXHAUSTED_ATTEMPTS` (Observer emits these three) / `EXHAUSTED_BUDGET` / `ERROR` (orchestrator/infra-level, never Observer's call). Cross-slot aggregation — deciding whether the QUERY needs another turn — is explicitly NOT Observer's job; that's Router's `decide_continuation()`.

`change-request-observer-module.md` (the original proposal to add this module at all) is **fulfilled** — the module exists, built against v2, not the design it originally proposed sign-off for. Marked accordingly in that file.

---

## 1. Where Observer sits in the loop

```
Router plans RoutingLadder per slot (dual-allocator shadow-mode, unchanged)
  → LOOP per slot, per attempt, driven by the ORCHESTRATOR (orchestrator.py, not Observer):
       Fillers attempts a fill using the current ladder rung
       → OBSERVER evaluates: evaluate(strategy_id, filled_slot, attempt_number=, max_attempts=) -> (verdict, reason)
       → orchestrator builds a SlotTurnInput per slot from ALL verdicts + elapsed time
       → Router's decide_continuation() aggregates across ALL slots into ONE "another turn, or done" call
       → satisfied slots stay done; justified/ride-along slots get their next rung; exhausted/dropped slots stop
  → once the query resolves: Router logs the ONE bandit row (rag_query_decisions)
```

**Who drives the loop: the orchestrator, same as v1 said — but the AGGREGATION is Router's, not the orchestrator's own ad hoc logic.** Observer is a pure per-slot, per-attempt function — no cross-slot visibility, no control-flow role. It doesn't know about siblings, doesn't know the time budget, doesn't decide whether a turn happens. The orchestrator calls `evaluate()` per slot, then hands ALL slots' (verdict, reason) pairs to `decide_continuation()`, which is where cross-slot reasoning (ride-along, envelope timing, budget) actually lives.

## 2. Input — what Observer receives

`evaluate(strategy_id: str, filled_slot: FilledSlot, *, attempt_number: int = 1, max_attempts: int = 1, filler_emit: dict | None = None) -> tuple[str, str]`

- `strategy_id` — which filler produced this rung ("a"/"b"/"c"/"d"/"s"); dispatches to that strategy's own sufficiency test.
- `filled_slot` — the rung's real `FilledSlot` output (chunks, occupancy, under_filled).
- `attempt_number`/`max_attempts` — **caller-supplied, not self-derived.** Observer has no ladder visibility and doesn't need it: the orchestrator is contractually responsible for deriving these honestly from real ladder-cursor state on every call (documented explicitly in orchestrator.py at the call site). Observer only needs to know "have I used up my shot," not "how long is the chain."
- `filler_emit` — optional, forward-compatible, unused by any handler today.

**No `speed_budget`/elapsed-time input at all — this is a deliberate architectural placement, not an oversight (see §4).**

## 3. Output — what Observer produces

`(verdict: str, reason: str)` — verdict is one of Router's own three Observer-relevant constants (`VERDICT_WOULD_BENEFIT`/`VERDICT_SATISFIED`/`VERDICT_EXHAUSTED_ATTEMPTS`, imported from `continuation.py`, never redefined). Reason is a human-readable string — **non-negotiable per Eval**: calibration exclusion rules key off both the verdict enum and the reason text, never the enum alone.

Per-strategy sufficiency tests, real and shipped:
- **a (BM25) / b (Vector)** — deterministic Pool reranks; sufficient = filled to capacity (`not under_filled`). Same-rung retry has zero information gain for these (re-running an identical rerank over an unchanged Pool result can't change the result) — "would benefit" always means "deploy the ladder's NEXT (different) rung," never "retry me."
- **c (LLM Retrieval)** — sufficient = filled to capacity AND every assigned chunk's LLM-cited quote actually verified against the returned text (`assignment_reason != "llm_partial_match"`).
- **s (Fact Store)** — sufficient = a hit (`occupancy > 0`); the slot has capacity 1, one verified fact answers it fully.
- **d (Web Search)** — sufficient = filled to capacity AND no chunk scores below 0.6x the slot's own top-scoring chunk (decay-floor, reusing Filler b's exact threshold against d's real BM25 `original_score`).

Determinism is encoded explicitly (`is_deterministic(strategy_id)`, `_IS_DETERMINISTIC = {a: True, b: True, c: False, d: False, s: True}`) — a/b/s can only ever resolve `SATISFIED`/`EXHAUSTED_ATTEMPTS` on their own rung (same-rung retry is meaningless for them); c/d are the only strategies where a same-rung retry could genuinely differ, though nothing wires that as same-rung retry today — the fact still lives on the strategy, not buried in a verdict branch, so it's ready the day that changes.

## 4. `speed_budget`/time-budget enforcement — satisfied ONE LAYER UP, not by Observer itself

v1's requirement (Chat, non-negotiable) was that *something* hard-stops the loop on time, independent of confidence. **That requirement is satisfied — just not inside `evaluate()`.** Router's `decide_continuation()` (`app/services/router/continuation.py`) takes `elapsed_ms`/`latency_allowance_ms` as direct inputs and is the actual hard ceiling: a turn only happens if a justifying slot's next-rung latency fits the remaining budget; `budget_remaining_ms` and `stop_reason="required_slots_over_budget"` are real, tested outputs. This is the correct architectural seam, not a gap: Observer has no cross-slot or time-budget visibility by design (§1), and time budget is inherently a cross-slot, cross-attempt concept (how much of the WHOLE query's budget is left, not any one slot's). Putting the ceiling check where the cross-slot aggregation already happens avoids duplicating budget logic in two places that could drift out of sync.

## 5. What Observer does NOT do

- Does not call Fillers, Pool, Router, or anything else — pure function of what it's given.
- Does not decide what strategy to try next (that's the `RoutingLadder`, Router's job) or which rung the orchestrator commits to next (readiness-aware deferral for `d`, e.g. skipping a not-yet-ready speculative prefetch, is orchestrator-level, per `router-build-spec.md` §11).
- Does not run the loop itself, and does not aggregate across slots (that's `decide_continuation()`, Router's).
- Does not check time budget itself (§4).
- Does not write to any DB.

## 6. Build-gate status — Eval's conditions

1. ✅ Fillers exist (all five, real). ✅ Synthesis exists (v1 built, sign-off in progress).
2. ✅ Committed calibration plan drafted (`observer-calibration-plan.md`, 2026-07-24) — arms confirmed: **A = today's actual production stopgap loop** (not a first-attempt-only strawman — the honest counterfactual is what ships if Observer doesn't, which already retries via the dumb stopgap), **B = the real multi-turn loop wired to Observer's actual `evaluate()`**. Metrics: final_answer_quality (real LLM-judge, `eval/judge.py`'s `adjudicate()`, rubric mode), cost (latency/tokens/LLM-calls reported separately), retry_rate, retry_precision (≥0.5 gate — of slots Observer said WOULD_BENEFIT and retried, what fraction actually improved). Optional arm 0 (single-rung, no loop) recommended for interpretability if a B-vs-A delta comes back small and ambiguous.
3. `confidence_bar` validation folded into the same calibration plan (§4 of that doc) rather than a separate condition.

**Production wiring (swapping Observer's real `evaluate()` in for the orchestrator's stopgap) does not happen until the calibration run above actually executes and clears its gates.** Design/build of Observer itself is NOT gated on this — that's done.

## 7. What's explicitly out of scope

- Router's ladder-planning logic and late-phase bandit-logging (unchanged).
- Fillers' actual chunk-assignment (Observer only reads the result).
- The orchestrator's loop-driving code and Router's cross-slot aggregation (Observer is a pure per-slot function called by both, not a replacement for either).
- Rung retention (superseded-output combination for a future Synthesis step) — see §8, unchanged, still design-only.

## 8. Retention contract — Ananth's ruling: RETAIN superseded rungs (2026-07-23, design-only)

*Drafted by Router (4c) at Retriever's request; anchors the cross-turn state
design. CONTRACT ONLY — build is gated on Synthesis kickoff: retention
without a consumer is pure token liability (kept chunks nobody synthesizes
across = cost with zero recall benefit).*

**Ruling (Ananth via Retriever):** superseded rungs' outputs are RETAINED,
not discarded — a future Synthesis step combines/chooses across multiple
rungs' results rather than only ever seeing the single winning rung.

**What this changes, and where each piece lives:**

1. **Plan-time payload accounting: MAX → SUM (Router).** Today's model —
   worst-case slot payload = MAX over chain rungs — is correct precisely
   because advance-on-empty DISCARDS failed rungs' output. Under retention,
   a slot's worst case becomes the SUM over rungs that execute. Do NOT flip
   early: SUM under live discard behavior overstates payload and causes
   false `payload_over_token_allowance` skips. The flip ships in the same
   change as the retention mechanism. (Flip-trigger documented in
   allocation.py's payload block and continuation.py's docstring.)

2. **Continuation decision gains a token axis (Router).** decide_continuation()
   currently takes no token input — correct today because every planned rung
   pre-passed the payload gate and later rungs replace earlier output. Under
   retention, each turn ADDS to retained volume, so the function gains
   `retained_tokens` + `token_allowance` inputs and a turn can be refused for
   token exhaustion even when latency budget remains (new stop_reason:
   `token_budget_exhausted`; new dropped reason for riders whose rung would
   overflow the remaining token budget).

3. **Cross-turn retention state (Orchestrator/Retriever).** What has been
   collected so far, across turns, per slot. Orchestrator-level — it spans
   the whole per-slot loop across turns; neither Router (pure planner) nor
   individual Fillers (single-attempt scope) can own it. Open sub-questions
   for the build: retained form (full FilledChunks vs references), and
   whether retention is per-slot or per-query pooled.

4. **Retention cap and token_budget are ONE number, not two (design
   constraint).** The retained volume is exactly what SUM-model accounting
   budgets; a separate retention cap would create two knobs governing the
   same resource. `ResourcePosture.token_budget` (Structure-threaded) is THE
   cap; retention state reports usage against it.

5. **Grading implications (Eval).** Retained-but-unused chunks must not
   count as recall; how Synthesis-credit attributes across retained rungs is
   an Eval design question, related to (but distinct from) the ride-along
   `participation` segmentation already contracted in decide_continuation().

**Sequencing:** this section is the design of record now; NO code moves
until Synthesis kickoff names a consumer. At that point: Router flips 1+2
(both localized), Retriever builds 3, Eval rules on 5, and 4 is a
constraint on all three.
