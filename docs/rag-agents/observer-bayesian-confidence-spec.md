# Observer — Bayesian Confidence Update (Spec Addendum, redefines Observer's scope)

**⚠️ SUPERSEDED 2026-07-24 — NEVER BUILT. Do not use this doc as a reference for Observer's real design.** Ananth directly refined Observer's scope back down past this addendum (and past even the pre-Bayesian v1 it was proposing to replace) to a much simpler discrete per-strategy yes/no verdict — no Beta posteriors, no confidence-score float, no "ranked candidate pool" reframing of Router's ladder. The real, built design is `observer-module-spec.md` (v2) — read that instead. This file is kept only for historical record of a design path that was explored and abandoned; the decision to abandon it was made in direct conversation with Ananth and was not written down anywhere until the v2 rewrite caught the gap (Observer's own session found this file, still marked DRAFT with no supersession notice, while looking for a spec to route for sign-off).

**Status (as of when this was live):** DRAFT — align-and-iterate, not locked. Written by P1 lead per Ananth's direction 2026-07-23. Supersedes the "Observer is purely mechanical, Router reasons once upfront" framing in `router-module-spec.md` §2 and `observer-module-spec.md` v1 — that framing is now wrong in one specific way (see §1). Everything else those specs established (confidence_bar/speed_budget gating, required-vs-optional, LB-not-mean enforcement) still holds; this addendum changes *when* and *how often* the confidence estimate is computed, not what it's checked against.

**Owner:** to be assigned once ratified — likely Observer's owning session once forked, co-designed with Router + Eval.

---

## 1. The problem this fixes

Today: Router computes the entire `RoutingLadder` **once, upfront**, from static historical priors (population-level: "across all queries in this depth_bucket, strategy X succeeds P% of the time, n samples"). If the resulting LB looks weak, we call the slot `UNDER_CONFIDENT`/infeasible **before a single real retrieval has happened for this specific query**.

That conflates two different things:
- **Population uncertainty** — "we don't have much historical data about strategy X at this depth" (this is what n=8 seed pseudo-counts and Wilson LB currently capture).
- **This-query uncertainty** — "is this *particular* question actually answerable from the corpus." A query can have terrible seed priors for its depth bucket and still turn out to have excellent real signal once you actually look — or the reverse.

The current design can never distinguish these, because it never looks at real evidence before deciding to exit. It plans the whole chain from the prior alone, executes it mechanically, and only then (implicitly, via Observer's existing pass/fail check) learns whether reality agreed with the prior.

## 2. The fix: sequential Bayesian updating, per query, per slot

Reframe each strategy's prior as a **Beta distribution**, not a point estimate + Wilson bound:

```
alpha_0 = recall_lift * n
beta_0  = (1 - recall_lift) * n
```

(same `recall_lift`/`n` already in `StrategyProfile` — this is a reframing of existing data, not new inputs.)

**After each Fillers attempt executes for a slot:**
1. Fillers/Pool return real evidence for that attempt (see §3 — what counts as evidence is still open).
2. That evidence updates the slot's posterior: `alpha_1 = alpha_0 + observed_successes`, `beta_1 = beta_0 + observed_failures` (exact update rule depends on §3's answer).
3. The slot's current confidence is now `wilson_or_beta_lb(alpha_1, beta_1, confidence_level)` — narrower or wider than the seed LB depending on what was actually observed, not the static prior alone.
4. This posterior is **local to the query** — it does not persist or feed Eval's cross-query empirical-priors loop. Cross-query learning (real N replacing seed n=8) stays exactly the separate, existing calibration loop. Do not conflate the two update mechanisms.

This is the mechanism that reconciles the population-level prior with the individual query's real evidence — which is the whole reason Observer exists rather than Router just executing its upfront plan blindly.

## 3. Open question — what counts as "evidence"? (needs Observer/Fillers/Eval co-design, not decided here)

We don't have ground truth accuracy at inference time (no golden answer to check against in production). So the per-attempt "observation" that updates the posterior has to be a **proxy signal** available at inference time. Candidates, none chosen yet:
- Count/fraction of chunks assigned to the slot with retrieval score ≥ some threshold (e.g. "5 slots filled ≥0.8" from Ananth's example).
- Occupancy achieved vs capacity requested (a full slot is weak evidence of a well-covered query; a starved slot is weak evidence of a poorly-covered one).
- A cheap self-consistency check (does a fast independent signal agree with what was retrieved).

This needs a real decision, and probably needs Fillers' actual output shape in hand to pick something real rather than hypothetical. Flag as the first thing to resolve once this addendum is reviewed — don't let the rest of the design stall waiting for it, but don't build the update mechanism against a guessed proxy either.

**Sharpened by Retriever's review (2026-07-23), critical constraint on §3:** occupancy alone is not just insufficient, it's actively misleading right now — Filler b's calibration independently found ~9.6% of the entire corpus is degenerate junk (bare `"-"` characters, PDF-viewer UI chrome) that scores legitimately on cosine similarity and wins top-N vector slots outright. A slot can be fully occupied with worthless content. Any evidence proxy MUST be quality-aware (does the retrieved content actually look like an answer, not just "did a slot get filled"), or the Bayesian update will confidently strengthen the posterior on junk. Whoever designs §3 needs real retrieved content in hand to validate the proxy against, not a hypothetical — and the proxy's design may need to explicitly discount known-junk patterns until Curation's corpus cleanup (separate thread, in progress, pin-baseline-then-measure-lift sequencing already decided) actually lands.

**Cross-linked reconciliation (Router + Eval, 2026-07-23):** "what counts as evidence for §3" and "what counts as 'slot satisfied' for Router's calibration Beta-update" are the same underlying question, resolved once in `depth-conditioned-priors-real-data.md`: **slot satisfied ≡ ALL must_facts found (recall == 1.0), not a partial-credit threshold** — a partial fact match is a materially wrong answer in this domain (payer rules, timely-filing windows), not merely incomplete. Whatever §3's evidence proxy ultimately computes (percentile-based fill-quality, has_content-gated, diversity-dampened per the amendments above) should target this same binary bar when it's used to judge "did this attempt succeed," so Router's calibration loop and Observer's live posterior update are measuring the same event, not two different ones that happen to share a name.

## 4. Exit condition — best-case ceiling test (replaces "build the full static chain, check the end result")

After each attempt, before trying the next rung, compute:

```
ceiling = current_posterior_LB + best_case_contribution(remaining_eligible_strategies, remaining_budget)
```

where `best_case_contribution` assumes every remaining strategy that could still be tried within the time/attempts budget fires at its **optimistic** bound (not its mean, not its LB — the upper end of what's plausible), combined via the same `1 - Π(1-p)` chain math.

- If `ceiling < adjusted_bar` even under this optimistic assumption → **exit now**. Don't spend remaining budget chasing a case that can't close even in the best case.
- If `ceiling >= adjusted_bar` → continue, there's still real headroom to close the gap.

This is the one place seeing real results changes the strategy: a query that looked hopeless from priors alone might have real headroom once you've actually observed one good attempt; a query that looked fine from priors alone might reveal it's actually unanswerable once real attempts come back weak — either way, the exit decision is made from evidence, not solely from the pre-computed static ladder.

## 5. What this changes architecturally — Router vs Observer boundary redrawn

| | Old (locked spec) | New (this addendum) |
|---|---|---|
| Router | Plans the full ladder once, upfront, from static priors | Still does upfront population-level planning: strategy eligibility (§ slot_semantics gate, already built), rough ordering, the STARTING prior per slot. Does not compute the final answer alone anymore. |
| Observer | Purely mechanical pass/fail against a bar Router already computed | The real per-query reasoning engine: ingests each attempt's evidence, updates the posterior, re-runs the ceiling test, decides continue/cleared/exit. This is why Ananth calls this module "the brains." |

Router's plan becomes a **prioritized candidate list with a starting prior**, not a fully pre-committed fixed sequence blindly executed. Observer is what actually decides, attempt-by-attempt, whether to keep going.

## 6. What does NOT change

- `confidence_bar`/`adjusted_bar` (tolerance-adjusted) semantics — unchanged.
- Required-vs-optional gating (§2a, already built and verified) — unchanged; the Bayesian update and ceiling test apply per-slot, same required/optional distinction.
- Strategy eligibility by `slot_semantics` (already built and verified) — unchanged; this addendum only changes how confidence is computed and when exit is decided, not which strategies are allowed for which slot role.
- Cross-query empirical priors (Eval's calibration loop, N replacing seed pseudo-counts over time) — unchanged, stays a separate mechanism from the within-query posterior update in §2.

## 6a. Resolved by Router's review (2026-07-23) — endorsed, folding into the design

**§7.4 (RoutingLadder's shape) — RESOLVED:** RoutingLadder becomes a **ranked candidate pool + starting priors**, not a live-state container. Per slot: eligible candidates post-semantics-gate, ranked, each with a starting prior `(α₀, β₀, latency_p50, cost)`; plus the budget envelope (per-slot allowance, max_attempts) and adjusted bar. Router stays pure/stateless/deterministic/replayable — every existing guarantee (byte-identical plans, trace replay, ONE-WRITER on the plan row) survives untouched. All live state (the posterior, the ceiling test, continue/exit decisions) lives with Observer in a per-query `PosteriorState`. Fillers' contract changes to "read next candidate from Observer" instead of "read rung i of a fixed list" — one indirection, not a rebuild.

**§7.3 (optimistic bound for the ceiling test) — RESOLVED:** use the **upper-tail quantile of the same Beta prior** (e.g. 95th percentile) — symmetric with using the lower-tail quantile for enforcement, closed-form, no new data needed. Rejected alternative: historically-best-observed-outcome (outlier-sensitive, needs new plumbing).

**§7.2 (Beta update rule for non-Bernoulli evidence) — proposed mechanism, weight still owned by §3:** fractional update `α += w·s, β += w·(1-s)`, where `s ∈ [0,1]` is the §3 evidence proxy and `w ≤ 1` is an evidence weight preventing one noisy observation from overwhelming an n=8 prior. The weight value `w` is set together with the §3 proxy decision, not fixed here.

**Router's upfront verdicts get refined, not deleted — this is the key synthesis:** Router still emits an upfront verdict per required slot, but it's now three-way instead of the current binary CLEARED/UNDER_CONFIDENT:
- `CLEARED_BY_PRIOR` — LB ≥ bar before any attempt (rare). Skip Observer escalation entirely.
- `VIABLE` — LB < bar ≤ pre-execution ceiling (the common case). Hand to Observer for the live loop.
- `STRUCTURALLY_INFEASIBLE` — even the zero-evidence optimistic ceiling < bar. Exit before spending anything; this is strictly better than today's static check because it's provably hopeless, not just "looked weak on the mean."
- `OPTIONAL` — unchanged.

**Two hazards Router flagged, now hard requirements on the eventual build (not suggestions):**
1. **The query-local posterior must never leak into the cross-query empirical-priors loop.** The §3 proxy is NOT ground truth — if proxy-updated posteriors contaminate Eval's calibration data, it poisons the exact thing this whole workstream exists to protect. This needs a test-enforced boundary, same rigor as the existing ONE-WRITER pattern (`test_only_persist_py_contains_the_insert`-style test, applied to this boundary).
2. **Shadow A/B semantics change and need re-scoping before Week-2 data is trusted.** Today's dual-build A/B compares two complete static plans end-to-end. Once execution is Observer-driven, the plan-level comparison (which candidates/priors each allocator proposed) still holds, but outcome attribution (which allocator "won") doesn't cleanly carry over — don't reuse Week 1-3 dual-build analytics under the old interpretation once this ships.

**Tracing — resolved shape:** `DecisionTrace` (Router's plan) stays as-is. Observer needs a new `AttemptTrace` stream: prior α/β → evidence → posterior α/β → ceiling arithmetic → continue/cleared/exit decision, same narrate-everything philosophy as everything built so far. Schema co-design between Router and whoever forks Observer, must compose with the existing plan trace for walkthrough views (like the ones we've been doing).

**Sequencing:** start §3's evidence-proxy co-design against Filler-a's real calibration output NOW (it's mid-run already) rather than waiting for the full filler family to exist — that's the actual critical path; everything else above is well-defined enough to draft the revised `observer-module-spec.md` around.

## 6b. Open question #6 (Retriever, formalized 2026-07-23) — RESOLVED: what does shadow A/B comparison mean once execution is Observer-driven?

**The problem:** the old dual-build model compared two fully-specified static plans — the untaken plan had a well-defined hypothetical outcome because both plans were complete before execution started. Under this addendum, the executed path's stopping point is data-dependent (Observer decides live from the evidence stream), so the untaken allocator's plan no longer has a well-defined counterfactual outcome — it never saw the evidence that would have driven its own stopping decision.

**Decision: Option C (population-level A/B) is primary; Option A (plan-level diagnostic) is secondary; Option B (per-query counterfactual replay) is explicitly rejected as a permanent policy, not deferred.**

- **Primary (C):** attribution happens only through the existing `ab_split`/`draw` tagging. Each allocator's real outcomes are measured on the queries where it actually executed, compared at the population level per `(depth_bucket, slot role)` — no per-query counterfactual claims. Statistically clean, needs volume, already fully supported by existing persisted fields (`dispatch_mode`, `ab_split`, `draw`) — no new machinery required.
- **Secondary (A), per-query diagnostic only:** compare starting rankings, priors, pre-execution ceilings, estimated cost/latency between the executed and shadow plans. No outcome attribution — this is "what did each allocator propose," not "what would each have scored."
- **Rejected (B):** post-hoc simulating the shadow allocator + Observer against the executed path's logged evidence stream. Only valid where the two plans' strategy sets overlap (evidence for a strategy the shadow never ranked is simply missing), easy to over-trust as if it were a real measurement, and it isn't one — the shadow never made its own live stopping decisions against that evidence. Do not build this.

**Binding consequence for the schema:** `shadow_ladder`'s role narrows permanently to plan-diagnostics (option A material) once this ships. Any "the shadow would have scored X" analysis is explicitly out of scope — this sentence exists so nobody reinvents it as a metric later.

## 6c. §3 evidence proxy — RESOLVED (P1 lead decision, seeded by Router against Filler-a's real contract, 2026-07-23)

**Decision: percentile-normalized fill-quality proxy.**

```
s = min(1, #{chunks in FilledSlot.chunks : pool_percentile(chunk.original_score) >= 0.8} / capacity)
```

using Pool's existing `top_score_percentile` machinery (already computed, already the same signal Router keys depth_bucket on — no new infrastructure).

**Why percentile, not a raw score threshold:** `FilledChunk.original_score` is not scale-comparable across strategies — BM25 is unbounded, vector is cosine-ish [0,1], future external strategies (d/f) will have their own scales. A raw threshold ("score >= 0.8") silently means something different per strategy, which would bias the posterior update by strategy — exactly the kind of hidden bias this whole workstream (Wilson LB, required/optional gating, eligibility-by-semantics) has been systematically removing. Percentile-within-this-query's-pool is scale-free and consistent with existing depth-bucket signal.

This directly implements Ananth's original "5 slots filled >= 0.8" intuition, computed from real `FilledShape` output (verified against `contracts.py`'s actual shipped `FilledSlot`/`FilledChunk`/`FilledShape` shapes, not a hypothetical): both a starved slot (occupancy < capacity) and a junk-filled slot (chunks present but low percentile-within-pool) score low on `s`.

**Known limitation, explicit, not silently absorbed:** this solves scale-comparability across strategies, NOT the corpus-junk confound Retriever flagged in §3 originally — a junk chunk can still legitimately win high percentile within a junk-heavy pool. That's Curation's corpus-cleanup track (`corpus-content-gate-spec.md`, in progress, sequenced separately per the pin-baseline-then-measure-lift decision). The proxy will under-correct for this until that cleanup lands; expected and tracked, not a flaw unique to this design.

**Third known limitation, general to any score-based proxy (Filler d, 2026-07-23, found doing a real full-text read, not a preview check):** retrieval score (BM25/vector/percentile-of-either) measures topical/lexical relevance, not factual completeness. A chunk can be genuinely on-topic, score well, and still not contain the actual answer — Filler d's finding: a multi-page PDF's extracted text was the cover page + table of contents (topically correct — it's the right document) while the real deadline fact sat on page 4, never extracted. This is NOT the corpus-junk confound (the text isn't garbage, it's real content) and NOT a has_content gap (content is present) — it's a structural ceiling on what ANY score-based evidence proxy can detect: score correlates with "is this the right document/passage," not "does this passage state the fact." Applies in principle to every strategy (a/b/c/d), not uniquely to Filler d; Filler d's PDF-extraction-specific angle (naive first-~2000-chars grab) is a separate, scoped, fixable engineering improvement for that filler (search within the PDF for keyword-relevant sections instead of a blind prefix), tracked as Filler d backlog, not an Observer-proxy fix.

**Second known gap, closed 2026-07-23 (Filler f, links-only, caught before it shipped):** the formula as written counts ANY chunk with a high-percentile `original_score`, with zero awareness of whether that chunk actually carries verified content. Filler f (Sitemap Validation) produces link-only results — a bare URL, no fetched text — and correctly flagged that giving these a constant-high `original_score` (matching legacy's sitemap-trust ordering) would make a slot register as high-confidence-filled while giving Synthesis nothing to actually work with. Same failure class as the junk-chunk confound above, but structural (a legitimate content-less source type) rather than a corpus-quality defect.

**Resolution update (2026-07-23):** Chat ruled link-only results never become a `FilledChunk` at all — they route to a separate `suggested_links[]` field, no `original_score`, no grounding-badge contribution, never enter the scored-chunk flow. So for Filler f specifically, the blind spot doesn't materialize in practice; the `has_content` contracts.py change is no longer required to unblock Filler f and is DEFERRED, not built, unless another filler needs it.

**The design invariant still stands, generally, for the Observer proxy:** a scored-but-unverified-content result must never count as evidence toward `s`. Filler f's case got resolved by routing around the scored-chunk flow entirely (arguably cleaner than a flag); if some future filler produces a different content-less-but-scored result type that can't route around the flow the same way, the `has_content`-gated formula above is the fallback design, already specified, not yet needed. Keeping this section rather than deleting it — it's cheap insurance against the same failure class recurring in a shape that can't dodge it as cleanly as Filler f did.

**Hard constraints on the update mechanism (Router's asks, adopted as requirements):**
1. Computable from `FilledSlot` alone at inference time — no ground truth, no extra retrieval calls. (Satisfied.)
2. Logged into `AttemptTrace` for replay: the `s` value plus its inputs (counts, occupancy, capacity, threshold) — numbers and ids only, **never chunk text** (same PHI rule as narration everywhere else in this system).
3. Deterministic given the same `FilledSlot` — **no LLM-judged evidence in the α/β update path.** An LLM self-consistency check would make posteriors non-replayable and adds a per-attempt latency tax. If a judged signal is wanted later, it's a separate advisory signal, never part of the core update.

**Evidence weight:** `w = 1.0` per attempt at bootstrap (n=8 seed priors) — one real observation moves the posterior by ~1/9, which is correct: real evidence should move the needle hard when priors are thin, and this self-attenuates naturally as empirical n grows via the normal Bayesian update arithmetic (no separate decay schedule needed).

**Before this is fully locked:** sanity-check this proxy against a handful of REAL `FilledSlot` instances from Filler-a's in-progress cmhc-26 calibration run (session "4d - BM25", mid-run as of this writing) — confirm the 0.8 percentile threshold produces sensible `s` values against actual score distributions, not just the formula on paper. This is the last step before `observer-module-spec.md` gets drafted from this addendum.

**Two required test cases for that sanity-check, boundary drawn precisely (Router, 2026-07-23):** `_run_fillers_simple` now has a binary advance-on-ZERO-occupancy rule (orchestrator.py, `simple_advance_on_empty_no_observer` emit tag, 368 tests passing fleet-wide) — a rung returning literally zero chunks walks to the next rung Router planned, no Observer needed. This closes the cmhc001 case (vector arm honest-zero, tag_select's 185 real candidates one rung away) at the dispatch level, not via the Bayesian design. That's correct scoping, not a shortcut: **empty is the one evidence value so unambiguous a binary rule handles it without any posterior machinery.**

But this draws the exact boundary where Observer's real value begins. **A rung returning a few weak-but-nonempty chunks when the next rung held real content still stops the walk today** — same failure shape as cmhc001, one notch subtler, and no binary rule can adjudicate "is 3 mediocre chunks enough or should I keep going." That's precisely the posterior-update + ceiling-test territory this whole addendum exists for.

Sanity-check against BOTH cases, not just one:
1. **cmhc001-shape (empty vs. viable)** — already solved by the degenerate binary rule; use as the baseline regression fixture Observer's real design must trivially reproduce (known-good data on both rungs, a live fixture, not synthetic).
2. **Weak-nonempty-vs-viable variant** — the first real case the evidence proxy must get right that the binary rule structurally cannot. This is the actual test of whether the Bayesian design earns its complexity, not the empty case.

**Fourth known limitation, upgraded to a REQUIRED amendment (Router, 2026-07-23, motivated by a real live-pipeline failure, not a hypothetical):** Filler b's live cmhc001 run returned all 10 assigned top-N chunks as the literal text `"Florida Medicaid o CHIP"` — one repeated 23-char boilerplate string across 8+ documents, high vector score, surviving reranking. Both proxy candidates on the table (occupancy-vs-capacity, score-threshold-fraction) are fooled identically: occupancy reads 10/10, score-fraction reads high, because the junk scores high. A slot filled with ten copies of one weak item must NOT register the same as ten genuinely distinct high-quality items.

**Required amendment to the §6c formula:** add a content-diversity term, dedup by **normalized TEXT** before counting toward the numerator:

```
s = min(1, #{distinct-content chunks (by normalized text) : pool_percentile(chunk.original_score) >= 0.8} / capacity)
```

**Correction (Router, 2026-07-23, verified during Pool's implementation):** the dedup key must be normalized text, NOT `content_sha` — Pool found `content_sha` is unreliable as a text-dedup key in this schema (5 byte-identical-text chunks carried 5 different `content_sha` values; a `content_sha`-based count would have completely missed Filler b's exact junk cluster). Pool's shipped `distinct_content_topk` signal groups by normalized text and is the reference implementation Observer's own dedup should match.

Diversity must be a MULTIPLICATIVE dampener on the signal, not an additive correction — uniform junk should crush `s` toward zero, not merely trim it by a fixed penalty. (A formula that subtracts a flat penalty for duplication would still let a 10x-repeated junk chunk read as moderately confident; that's not acceptable given how strong the observed real-world case is — 0.797 cosine similarity, enough margin that even reranking's length-penalty couldn't overcome it.)

**Wider implication for Router's depth-bucket input — RESOLVED, not just tracked (Router + Pool, 2026-07-23):** the same junk inflates `top_score_percentile`, which was misclassifying query depth buckets. Pool now supplies `distinct_content_topk` (count of distinct normalized-text chunks in the top 10) and `compute_depth_bucket` (priors.py:418) applies demotion-only thresholds: `distinct_content_topk <= 2` forces bucket >= 3; `<= 4` forces bucket >= 2; absent stays unchanged (fail-open). Verified: cmhc001 post-fix (score .7997 after a second bug fix — tag-coverage counts were clamping to a fake 1.0 — distinct=7) gets NO demotion, correctly bucket 1; an all-junk shape (tight-looking score, distinct=1) gets forced to bucket 3, which is the actual defense. Demotion-only, never promotes a genuinely broad bucket; every demotion is traced/narrated for replayability. 189/189, independently verified.

**Calibration methodology caveat, NARROWED (was open-ended, now bounded):** the bucket-mislabeling risk is closed at the input side for any query flowing through the fixed orchestrator from 2026-07-23 onward. The only remaining contaminated class is rows persisted BEFORE the orchestrator fix landed — and there's essentially no real production data volume in that window, so this is a formality more than a live risk. Eval's Week-3+ empirical-priors derivation should scope the caveat to "pre-2026-07-23-fix rows," not treat it as an open-ended ongoing risk.

## 7. Open questions for alignment (this is a draft, iterate before building)

1. §3 — the observable evidence proxy. Must be resolved with real Fillers output in hand.
2. The exact Beta-update rule for a non-Bernoulli observation (e.g. a fractional occupancy signal, not a clean success/failure).
3. What counts as "optimistic bound" for the ceiling test — the prior's upper confidence bound? Best historically observed outcome for that cell? Needs a concrete, defensible definition, not a hand-wave.
4. Does this change `RoutingLadder`'s shape (still a `strategy_sequence` list, or does it become more like a ranked candidate pool + live state)? Affects Fillers' contract too — Fillers currently reads "which rung = current attempt" off a fixed sequence; if the sequence is no longer fully fixed upfront, Fillers'/Router's/Observer's contracts all need to be re-checked together. **Not theoretical (Retriever, 2026-07-23): Filler a and Filler b are both already built and already read `strategy_sequence` as a fixed pre-computed list (verified in code, `filler_a.py:34-44`). If this changes, both fillers' input contracts need real revision, not a future consideration for modules that don't exist yet.**
5. Telemetry/tracing: the existing trace format assumes a fixed planned chain executed in order; this needs live per-attempt posterior snapshots added, not just the final chain.

## 8. Process

This is a bigger redesign than any prior addendum in this workstream (bigger than the LB fix, bigger than required/optional gating) — it changes the Router/Observer contract that `router-module-spec.md` and `observer-module-spec.md` both currently lock. Do not build against this until:
1. Retriever reviews (this changes Observer's scope, which Retriever owns end-to-end).
2. Router reviews (this changes what Router's output actually is).
3. Eval co-designs §3's evidence proxy and the Beta-update mechanics (same pattern as every uncertainty decision so far).
4. A revised `observer-module-spec.md` gets drafted reflecting the new boundary, then goes through the same cross-agent sign-off as every other module.
