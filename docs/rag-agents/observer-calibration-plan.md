# Observer Production-Wiring Calibration Plan (Eval)

**Status:** COMMITTED PLAN (protocol/methodology/gates) — 2026-07-24. This is the last of the three Observer build-gate conditions (the other two: Fillers+Synthesis exist ✅ both now do; confidence_bar validated against real quality — folded in as §4 here). This document authorizes wiring Observer's real per-strategy verdict logic into the live orchestrator loop ONCE the before/after run below is executed and clears the gates. Drafting the plan does not itself lift the gate — the measured run does.

**Hard dependency, stated up front:** every quality number in this plan requires **LLM-judge grading against the cmhc rubric** (the `must_facts`/`golden_answer`/`forbidden_facts` methodology behind the authoritative 0.278/0.632 baselines) — NOT the string/token-match grading used for the exploratory forced-filler numbers. That distinction is not pedantic: the token-match grading was proven inflated earlier today (cmhc008 scored recall=1.0 on chunks that contained none of the actual facts), which is exactly why the priors fold got rolled back. Any calibration run that measures "answer quality" with string-match instead of the real judge will inflate the same way and must not gate a production wiring. Whoever executes this needs live LLM-judge + pipeline access.

---

## 1. What Observer's wiring actually changes (the thing being measured)

Today's live orchestrator loop uses a STOPGAP verdict (bare occupancy check). Observer replaces it with real per-strategy verdicts: for each required slot, "would this slot benefit from another turn?" → if WOULD_BENEFIT and attempts remain, advance to the next rung; if SATISFIED or EXHAUSTED_ATTEMPTS, stop. The number-moving question: **does replacing the stopgap with real per-strategy verdicts produce better final answers, and at what cost?**

## 2. Arms (corrected 2026-07-24 after Retriever flagged the counterfactual)

Original draft said "arm A = first-attempt-only." That's the WRONG counterfactual for the ship decision. Today's production is NOT first-attempt-only — it already retries via the crude stopgap (bare occupancy check). The gate decision is "wire Observer in, REPLACING the stopgap," so the honest counterfactual is the stopgap loop, not a first-attempt-only world that doesn't exist in production. Comparing Observer against first-attempt-only would overstate Observer's value by crediting it for the entire retry loop, when a (dumb) retry loop already ships.

**Arm A (baseline) — today's stopgap loop:** the current production behavior, crude occupancy-check verdict driving retry. This is the real counterfactual — what we keep running if Observer doesn't ship.
**Arm B (proposed) — Observer loop:** the real multi-turn loop wired to Observer's actual `evaluate()` (a/b/c/s real logic, d placeholder) instead of the stopgap.

The gate decision (§5) is fundamentally B-vs-A: are Observer's smart verdicts better than the dumb stopgap they'd replace, per unit cost? If Observer ≈ stopgap on quality but retries more, don't wire it.

**Arm 0 (OPTIONAL, decomposition only — Retriever's call given execution cost):** single-rung, no loop at all. Not gate-required, but if run, it decomposes the value: A-vs-0 = "how much does dumb retrying help," B-vs-0 = "how much does smart retrying help," and B-vs-A (the gate) = "is smart worth it over dumb." Without arm 0, a small B-vs-A delta is ambiguous — could mean "Observer barely helps" OR "retrying helps a lot and the stopgap already captured most of it." Arm 0 resolves that ambiguity for ~+50% execution cost. Recommended if affordable, skippable if not — the gate itself only needs A and B.

Same eval bank (`eval/queries_cmhc.yaml`, 22 queries — the standing bank, not queries.yaml), same corpus revision, same priors, all arms. Only the loop-control differs.

## 3. Metrics (all per-query, aggregated after)

1. **final_answer_quality** — LLM-judge rubric score (per §hard-dependency). This is THE quality signal; string-match is not acceptable here.
2. **cost_per_query** — three components, reported separately not blended: wall-clock latency, payload tokens (Router's per-rung accounting), LLM-call count. Retries increase all three; the point is to see by how much.
3. **retry_rate** — fraction of required slots that got a retry under arm B.
4. **retry_precision (the real calibration measure)** — of the slots Observer said WOULD_BENEFIT and got a retry, what fraction ACTUALLY improved (the additional rung changed the slot from under-bar to a materially better result)? A retry that advances and lands the same under-bar result is pure waste. This is Observer's verdict accuracy: WOULD_BENEFIT is a PREDICTION; retry_precision measures whether the prediction was right.

## 4. confidence_bar validation (build-gate condition 3, folded in)

The bar is the threshold separating WOULD_BENEFIT from SATISFIED. Validating it against real quality = an ROC-style sweep: at candidate bar values, measure (a) do slots Observer calls SATISFIED actually have good rubric-graded answers (few false-SATISFIEDs shipping bad answers), and (b) do slots it calls under-bar actually have bad ones (few false-WOULD_BENEFITs triggering pointless retries). Pick the bar where the separation is cleanest — highest retry_precision at acceptable retry_rate. Do NOT assume the current bar value is correct; it was hand-set.

## 5. Gates (all three must clear before production wiring)

1. **Quality non-regression + improvement:** arm B final_answer_quality ≥ arm A (the whole point is retrying under-confident slots helps). A wiring that doesn't improve quality has no justification for its added cost.
2. **Bounded cost (the retry-happy-regression catch):** arm B cost increase must be justified by the quality gain. Concrete gate: retry_rate ≤ a committed ceiling (proposed 40% of required slots — tune with real data), AND retry_precision ≥ 0.5 (at least half of triggered retries actually improve the answer; below that Observer is predicting benefit that doesn't materialize and is just burning budget). A 2%-quality-gain-for-80%-retry-rate outcome fails this gate.
3. **No silent quality loss on the SATISFIED side:** slots Observer calls SATISFIED must not be shipping materially-wrong answers at a higher rate than baseline's first-attempt results — i.e. Observer stopping early must not be worse than never checking.

## 6. What I cannot do here, and what unblocks it

I can commit this plan (done — this document). I CANNOT execute the baseline in this environment: no live LLM-judge, no DB/pipeline access. Executing arms A and B against the real judge needs whoever holds that infra.

**What would let this finish fastest:** if today's live validation runs (Retriever mentioned these) already pushed the 22-bank through the REAL pipeline AND graded with the LLM judge (not string-match), those runs may already BE arm A (baseline) or close to it — point me at that output and I'll check whether it's usable as the baseline or what's missing. If the live runs were string-match-graded, they're a useful pipeline-correctness check but NOT a quality baseline, and the judge pass still has to happen. Either way the specific unblock is: real-judge-graded before/after runs of the 22 bank, arms A and B. I design and adjudicate; execution needs the infra.
