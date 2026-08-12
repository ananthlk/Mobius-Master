# Blend Model Design — Cross-Strategy Portfolio + Fusion

**Status: IN PROGRESS, converging. Nothing implemented yet.** Driven by
Retriever, coordinating Router / Synthesizer / Eval / Chat. This doc
consolidates a real-time cross-session design conversation (2026-07-24)
into one place — see the end for who to ping with open questions.

## 1. Why this replaces the single-winner model

Today's model (`orchestrator.py`'s `_run_fillers_simple` + Router's
continuation loop): each slot tries ONE strategy per turn; if insufficient,
the NEXT strategy's result **replaces** it entirely (DISCARD model —
superseded rungs' chunks are thrown away, not kept).

Eval's forced-per-leg calibration (22-query bank) shows why this is lossy:

| leg | forced score |
|---|---|
| d | 0.42 |
| b | 0.20 |
| a | 0.14 |
| c | 0.07 |
| s | 0.00 |

**5-leg oracle (best single leg per query) = 0.55.** The integrated
single-winner pipeline scored **0.146** (clean baseline, 4 Vertex-429 rows
excluded — see `single-winner-baseline.md`). That ~0.40 gap is almost
entirely discarded rungs — the legs retrieve **complementary**, not
redundant, facts (e.g. b wins on cmhc005/006/018 where a is weak; d wins
outright on 8 queries where a/b score 0).

## 2. The end-state model

Fillers fill each strategy's own candidate set independently (no early
termination on partial success). Retention replaces discard: every
executed rung's `FilledChunk`s are **kept**, unioned into the slot's chunk
list (not a new dataclass shape — Synthesis's existing pipeline is already
provenance-agnostic). Synthesis fuses across all retained candidates and
fills to the real token budget.

This directly unblocks `observer-module-spec.md` §8 (rung retention),
previously gated on "Synthesis needing it as a consumer" — Synthesis now
exists and is live.

## 3. Two complementary, NOT redundant, allocation layers

**Router's portfolio {k_i} — EX-ANTE, retrieval budget.** Decided from
calibrated priors *before any content exists*: how many chunks to FETCH per
strategy. Math (Router, 2026-07-24): objective is
`P(covered) = 1 − Π_i(1−q_i)^{k_i}` subject to
`Σ k_i·tokens_i ≤ token_budget`, `k_i ≤ cap_i`. In log space this is
`Σ k_i·ln(1−q_i)` — with rank-decreasing per-chunk value `q_i(r)` (Pool's
score-at-rank curve), the optimal allocation is **greedy-by-marginal-
coverage-per-token**: give the next chunk to whichever strategy's
next-ranked candidate buys the most coverage per token. This is why
"3 from a, 2 from b" isn't an arbitrary heuristic — it falls out of first
principles once q_i and the rank-decay curve are known.

Note: this generalizes capacity-as-a-joint-variable (already discussed
with Eval) AND is the same object as the task-#13 candidate-pool contract
redraw. **One design doc, not three.**

**Synthesis's fusion pass — EX-POST, synthesis-input budget.** On ACTUAL
retrieved content (not prior estimates), evaluate true incremental value
across ALL strategies' combined output and fill the final context by real
marginal worth — NOT constrained by Router's per-strategy quotas at this
stage. Real chunks diverge from prior estimates (two strategies' chunks
can turn out near-duplicate in practice even though priors treated the
strategies as independent) — Synthesis is the only layer that can see
that, because it's the only layer holding the actual text.

Drop either layer and something breaks: no portfolio → unbounded/
misallocated fetch spend; no fusion pass → cross-strategy duplication and
prior-reality divergence go uncorrected.

**Capacity transform + LB propagation (Eval↔Router, RATIFIED 2026-07-24).**
Existing cells' `recall_lift` r was observed at calibration capacity k₀.
Transform to arbitrary fill k: `P(satisfied | k) = 1−(1−r)^(k/k₀)`
(per-chunk hit prob `q = 1−(1−r)^(1/k₀)`). One parametric transform of
existing cells, no new cell dimensions. Because g(r)=1−(1−r)^(k/k₀) is
strictly monotone ↑ in r and quantiles commute with monotone transforms,
the ratified Wilson/Beta lower bound propagates in closed form:
**`LB_k = 1−(1−LB_r)^(k/k₀)`**, coverage guarantee intact, both tracks.
- **What's exact vs approximate:** the LB formula EXACTLY propagates r's
  *sampling* uncertainty. It does NOT capture *model* misspecification: g
  assumes uniform-q, independent chunks, single-hit satisfaction. Real
  biases pull opposite ways — rank effect (top chunks > avg q) makes g
  conservative at small k; chunk redundancy makes g optimistic at large k;
  and multi-fact "satisfied ≡ ALL facts" is really `Π_f(1−(1−q_f)^k)`, not
  a single power. **Trust g in ~[k₀/2, 2k₀]; re-calibrate beyond, don't
  treat far-extrapolated LBs as hard guarantees.**
- **v1 = uniform-q cell transform (accepted).** v2 = rank-conditioning +
  multi-fact decomposition (Eval-owned, gated on the candidate-pool /
  score-at-rank contract).
- **k₀ AUDIT COMPLETE (Eval, 2026-07-24) — three findings, all landed in code:**
  (1) Today's cells are ALL SEEDS (no explicit `n` in the file; hand-set
  graduated-scale values never measured at ANY capacity) — so the transform
  is **INERT-UNTIL-REAL-CALIBRATION**: applied to seeds it produces
  regularized-prior bounds on designed numbers (fine as shadow diagnostics,
  never guarantees). It ACTIVATES per cell only when the empirical writer
  emits `(recall_lift, n, k0)` together from a real run.
  (2) **k₀ is per-(depth,strategy), NOT global:** a/b/d calibrate at
  occupancy ~10 while c and s rarely exceed 1 — global k₀=10 would badly
  misrebase c/s (treating 1-chunk recall as 10-chunk, understating q).
  (3) `k0` is now a per-cell field: `StrategyProfile.k0` (default
  K0_NOMINAL=10), parsed from the YAML per cell, consumed per cell by the
  portfolio allocator — the empirical writer emits it as a MANDATORY
  companion to `n` (Eval wiring that when the writer is built).

## 4. Fusion algorithm (v1 ruling: Eval, 2026-07-24)

**Raw global score-rank across strategies is unsound** — a/b/d's scores
are on different, incomparable scales/distributions (same root cause as
the deferred `chosen_slot`/`best_score` bug in `contract.py`).

**v1: Reciprocal Rank Fusion (RRF).** Fuse by rank position within each
strategy's own set, not raw score — comparability-free by construction,
cheap, standard for hybrid retrieval.

**v2 (only if RRF underperforms, needs data we don't have yet):**
calibrated cross-strategy relevance — map each strategy's score to
`P(relevant)` via labeled data.

**Diversity floor:** explicit per-strategy quotas are a blunt fallback, not
the primary mechanism — but keep a cheap floor (≥1 chunk from each viable
strategy that cleared its own gate) so fusion can't collapse to a single
strategy by accident.

**MMR-style incremental-value check** (Ananth's framing: "does this chunk
add a fact the selected set doesn't already have") is the mechanism that
realizes RRF's ranking into an actual selection — standard technique:
iteratively pick `argmax(λ·relevance(c) − (1−λ)·max_similarity(c, already_selected))`
until budget is exhausted.

- **Similarity function (Synthesizer's infra finding, 2026-07-24):** no
  per-chunk embeddings flow through the pipeline today — only the query's
  own embedding is reused (Filler s). Chunk-level vectors live only in
  pgvector, compared via SQL, never surfaced into Python objects.
  Embedding-based chunk-to-chunk similarity would need either a new
  batched DB lookup (internal chunks only, no external/fact_store
  coverage) or a fresh embedding API call (a new latency/cost dependency
  Synthesis has never had). **v1 recommendation: cheap text-overlap
  heuristic** (Jaccard/TF-IDF on chunk text) — zero new infra, uniform
  coverage across internal/external/fact_store. Embedding-based similarity
  is a contained upgrade later if the heuristic proves insufficient (a real
  contract change, same governance class as title/quote_verified — not
  built ahead of measured need).
- **Similarity refinement (Eval, 2026-07-24): TF-IDF, NOT raw Jaccard.**
  In this corpus duplicate facts share their high-information tokens (codes
  `96130-96139`, numbers `180 days`, payer names `Sunshine Health`), which
  TF-IDF weights and raw Jaccard drowns in common words. So TF-IDF cosine
  catches most real duplicate-fact pairs here; embeddings only buy the
  pure-paraphrase tail (disjoint vocabulary — a minority in payer docs).
  TF-IDF v1 is acceptable on that basis.
- **The real risk is RECALL, not precision (Eval, 2026-07-24).** The doc's
  "insufficiently precise" framing understates it. Text overlap also sees
  two chunks that share topic anchors but state DIFFERENT facts as similar
  (two "Sunshine Health prior authorization" chunks about different codes).
  If MMR drops one as redundant, a distinct must_fact is LOST. On multi-fact
  slots, wrongly merging two distinct facts is worse than keeping a true
  duplicate (a wrong answer vs a wasted budget slot). So fear over-merging,
  not under-merging. Mitigation: conservative similarity threshold (only
  drop on very high overlap; bias toward keeping) + a recall-leaning λ.
- **λ (relevance vs. diversity weight):** documented placeholder range
  **0.5–0.7**, but **seed the starting value at 0.7 (relevance-leaning),
  NOT the 0.5 midpoint** (Eval) — a recall-first blend where over-
  diversifying can drop distinct facts should weight relevance over
  diversity until calibrated. Labeled uncalibrated-pending-Eval, same
  seed-then-calibrate posture as `confidence_bar`/priors.
- **Instrumentation (Eval, required for v1):** two counters on the dedup
  step — (1) pairs merged, (2) whether a merged-away chunk carried a
  must_fact the survivor didn't. That turns "is TF-IDF sufficient" and "is
  λ right" into measured decisions I calibrate post-blend-output, not
  guesses. **Answering the open question directly:** TF-IDF works for the
  same-fact-different-wording case *in this domain* (rare-token anchors),
  so v1 does NOT need embeddings to start — but ship the counters so the
  upgrade trigger is a measured miss/over-merge rate, not a hunch.

## 5. Control-flow boundary (confirmed, load-bearing)

**Synthesis stays a pure compiler — zero control-flow role.** Confirmed by
both Router and Eval independently:

- Router: control flow (continuation, pool expansion, deepening a k_i)
  remains entirely the orchestrator's loop calling `decide_continuation()`.
  Synthesis MAY emit a coverage-gap diagnostic discovered while compiling
  (data, same pattern as filler verdicts) that flows INTO the next
  continuation decision — but Synthesis never triggers filling itself.
  Signals in, decision at the loop.
- Eval: their reward signal depends on cleanly attributing "this
  strategy's chunks survived rerank AND got cited" to Router's retrieval
  decision vs. Synthesis's fusion, separately. If Synthesis also triggered
  filling, that attribution seam collapses.

This matches `synthesis-module-spec.md` §5 exactly, as already built — no
change needed.

## 6. Standing tensions this dissolves

- **s's supplement-vs-substitute tension** (Router's own planning-time
  rule + Observer's execution-time fix, both landed 2026-07-24): in a
  portfolio, s contributes its certified fact (~150 tokens) AND corpus
  strategies contribute policy text — nobody substitutes anybody. The
  supplement gate becomes unnecessary in the end state (keep until
  cutover). **s's near-zero-on-content result still holds regardless of
  blending** (Eval) — s only earns a slot on genuinely fact-shaped queries.
- **The parked §12 hedging design** (parallel-rungs execution): under
  blend, "parallel rungs" IS the default execution model — the park
  dissolves rather than needing revival. Its data-gate concerns transfer
  to q-calibration quality instead.

## 7. Retention mechanics

- Orchestrator unions all retained rungs' `FilledChunk`s into the SAME
  `FilledSlot.chunks` list per `slot_id` before calling `compile_synthesis`
  — no new dataclass shape. `FilledShape`/`FilledSlot`/`FilledChunk` stay
  exactly as already signed off by all 9 parties. **Full `FilledChunk`
  objects retained, not references** (Synthesizer's vote — a
  reference-based design would need a second resolution step and buys
  nothing).
- Payload accounting: MAX-over-rungs → **SUM-over-retained-rungs**
  (already designed in `observer-module-spec.md` §8, unblocked exactly as
  written).
- Dedup: **no change needed** — already correct for an arbitrary-provenance
  flattened list (chunk_id + content-key, not strategy-aware).
- **Neighbor-completion reordering (Synthesizer, endorsed by Router):**
  today neighbor completion runs BEFORE any trim. Under retention (2-3
  rungs' worth of candidates per slot instead of 1), that wastes DB calls
  fetching neighbors for candidates about to be trimmed away. New order:
  **dedup → provisional trim-to-budget-estimate → neighbor completion on
  survivors only → final trim** (neighbors add their own tokens).

## 8. Ladder/continuation contract reshape (Router)

`RoutingLadder.per_slot`: ordered chain → **portfolio `{strategy: k_i}`**
(+ scheduling hint). `decide_continuation`'s aggregation (verdicts → one
query-level call) stays structurally the same, but "turn" now means
**expanding the pool** (add a strategy / deepen a k_i) when the blended
pool's verdict says insufficient and budget remains — per-strategy
verdicts still decide WHICH expansion. Under retention,
`decide_continuation` gains **retained_tokens/token_allowance inputs and a
`token_budget_exhausted` stop reason** (per observer-spec §8: retained
volume is what SUM accounting budgets; the retention cap ≡ token_budget,
one number, never two). EXECUTED/shadow allocator comparison transfers
unchanged (allocators emit portfolios instead of chains).

## 9. Sequencing (agreed)

1. ~~Persist schema~~ — done, verified live.
2. ~~Grade single-winner baseline~~ — done, frozen (`single-winner-baseline.md`:
   arm A clean = 0.146, oracle = 0.55). **Caveat carried forward:** this
   baseline has the early-stop-before-d defect baked in — blend lift will
   conflate "blending helped" with "the escalation fix helped" unless
   controlled for. **Measurement rules (Eval, ratified):** lift is claimed
   against BOTH bars — the floor 0.146 (did we beat real single-winner) AND
   the oracle 0.55 (did the portfolio beat perfect single-selection);
   grading is MODE-CONSISTENT (baseline is chunk-only/synthesis-OFF — grade
   the blend identically, or re-grade both with synthesis; no mixed-mode
   claims); and the blend run captures per query the five-field must-list:
   **{dispatch_path, depth_bucket, per-slot ladder/portfolio, per-strategy
   chunk count, skip-reason distribution}**.
3. ~~This doc~~ — converged; all sections either RESOLVED or explicitly
   flagged open (§10).
4. Build:
   - ~~Retention~~ (Retriever) — done, verified live: `orchestrator.py`
     unions every executed rung's `FilledChunk`s into `FilledSlot.chunks`.
   - Portfolio allocator math (Router) — in progress, tracked separately.
   - ~~RRF + MMR fusion (Synthesizer)~~ — **done, wired into the live
     `compile_synthesis` path, not just standalone**, 2026-07-24. Per-slot:
     group by strategy (derived via `assignment_reason`, retention's real
     shape confirmed to carry no explicit strategy tag) → RRF fuse → MMR
     select to a per-slot token sub-budget (Router's
     `per_slot_payload_tokens`, reused as split weights per Router's
     ruling, falling back to an effectively-unbounded per-slot budget +
     the existing global trim when not supplied) → `CoverageDiagnostic`
     captured per slot (including empty ones) → forward to the EXISTING,
     unchanged neighbor-completion/dedup/citation-building/token-trim
     steps. Circular import between `synthesis.py` and `fusion.py`
     resolved by extracting the shared chunk-identity key logic into a new
     `chunk_identity.py`; `CoverageDiagnostic`/`POOL_VERDICT_*` moved to
     `synthesis_contracts.py` for the same reason. Reconciliation guard's
     identity extended with two new drop-path counters
     (`fusion_dropped_redundant`, `fusion_dropped_budget`) so it doesn't
     false-positive now that fusion legitimately drops chunks before
     dedup/neighbor-completion ever run. 6 new integration tests
     (cross-strategy TF-IDF redundancy caught where literal dedup
     wouldn't, genuinely distinct strategies both survive, every slot gets
     a diagnostic, per-slot budget split actually changes citation counts,
     legacy None-safe path still works, reconciliation holds with a real
     fusion drop) on top of the 32 already covering `fusion.py` in
     isolation. 83/83 in the combined synthesis+fusion suite.
   - Re-run against the frozen baseline — not yet done; needs Router's
     portfolio math live first (today's real-data test still plans via the
     old ladder/chain allocator, a rougher MAX-over-rungs payload proxy per
     `per_slot_payload_tokens`'s own docstring).

## 10. Open items (not yet resolved)

- ~~Does the cheap text-overlap heuristic work for "same fact, different
  wording"~~ **RESOLVED (Eval, §4):** yes in this domain via TF-IDF (not raw
  Jaccard) — facts are rare-token-anchored. v1 does not need embeddings.
  The real risk is over-merging distinct facts (recall), mitigated by a
  conservative threshold + λ=0.7 + dedup counters. Upgrade trigger is a
  measured over-merge/miss rate, not a hunch.
- Exact λ value — seeded 0.7 (Eval, §4), real calibration needs blend
  output that doesn't exist yet.
- `authority_requirement` has no threading path into `run_retriever_partial`
  (found 2026-07-24, unrelated to this doc but still open — see fleet
  schematic).
- Contract's `chosen_slot`/`score` cross-strategy comparability bug
  (deferred, same root cause as the fusion problem this doc solves for
  citations — worth revisiting once RRF/fusion lands, may share a fix).
- **Coverage-gap diagnostic shape — RESOLVED (Synthesizer ↔ Router, direct, 2026-07-24).**
  Router's proposed v1 shape:
  ```
  CoverageDiagnostic {
    slot_id: str,
    pool_verdict: "gaps_remain" | "saturated" | "budget_full",
    reason: str,                      # prose, flows to telemetry VERBATIM (Eval's no-collapse rule)
    saturated_strategies: [str],      # deepening these won't help
    uncovered_aspect_count: int|null  # v2; null = unknown in v1
  }
  ```
  Synthesizer's response, derived (not guessed) from `fusion.py`'s output —
  required one real fix along the way: `MmrSelection` didn't previously
  distinguish "rejected as redundant" (`merged_away`) from "never evaluated,
  budget ran out first" (`budget_cutoff_remaining`, added 2026-07-24) — that
  distinction is exactly what keeps `saturated` and `budget_full` from
  collapsing into each other.
  - `uncovered_aspect_count`: confirmed null in v1 -- no per-fact/aspect
    granularity below chunk-level redundancy.
  - Honest limit: can't distinguish "a strategy ran genuinely dry" from
    "its candidates happened to overlap with a stronger strategy's picks" --
    only that deepening it wouldn't add anything new to THIS slot's
    current selection.
  **Router CONFIRMED (2026-07-24): the honest limit is SUFFICIENT for v1** —
  decide_continuation only needs "deepening this strategy won't add to the
  current selection" to rule deepening out; WHY it saturated (dry vs
  overlapped by a stronger strategy) matters for v2 expansion-sizing, not
  the deepen-vs-add decision. Shape locked as above; Synthesizer clear to
  build CoverageDiagnostic construction.

  **CORRECTION post-build (Synthesizer, 2026-07-24): the originally-agreed
  `saturated_strategies` definition was mathematically unreachable, found
  while writing tests, not by inspection alone.** Original definition:
  "(strategies contributing to `merged_away`) − (strategies contributing
  to `selected`)," with pool-level `saturated` requiring this to cover
  EVERY contributing strategy (nobody survived into `selected`). Proof
  this can't fire on a non-empty pool: `mmr_select`'s `kept_because_of`
  chunk in any redundancy merge is, by construction, always drawn from
  `selected` (`closest_selected_idx` only ever indexes into
  `selected_idx`) -- so whichever strategy "wins" a redundancy comparison
  always lands in `contributing_to_selected` and can never be counted
  saturated. For ALL contributing strategies to be saturated,
  `contributing_to_selected` would have to be empty -- impossible whenever
  `mmr_select` has any input at all, given its own "always keep ≥1
  selection" guarantee. Router would never have seen this verdict fire in
  practice, silently defeating the reason it was added.
  **Corrected definition**: `saturated_strategies` = strategies with AT
  LEAST ONE candidate rejected as redundant (appearing anywhere in
  `merged_away`'s dropped half) -- not "every one of that strategy's
  candidates rejected." A strategy whose single candidate wins outright,
  never having been compared against anything, shows no evidence either
  way and is correctly NOT counted. Pool-level `saturated` unchanged in
  spirit: every contributing strategy shows this sign. Reachable and
  tested (`test_saturated_when_every_contributing_strategy_shows_
  redundancy`).

  **Router RE-CONFIRMED (2026-07-24): correction accepted, and the
  corrected bar is the RIGHT signal for a marginal decision, not just a
  reachability fix.** The deepening decision is about the strategy's
  FRONTIER (would its NEXT candidates add value), not its total output --
  "≥1 candidate rejected as redundant" is exactly the diminishing-
  marginal-novelty signal that question needs; "zero survivors" measured
  the wrong quantity (total value) even before being proven unreachable.
  **Residual risk, named and bounded, not dismissed**: the corrected bar
  can over-exclude on one incidental cross-strategy loss (this strategy's
  chunk merely lost a comparison to a stronger strategy's near-duplicate,
  not real frontier exhaustion) -- bounded for v1 by (a) a saturated
  strategy only loses DEEPENING, the ADD-a-strategy path stays open, so
  worst case is a suboptimal expansion choice, not a wrongly-terminated
  slot, and (b) pool-level `saturated` still requires EVERY contributing
  strategy showing the sign. **Router's follow-up ask, implemented**:
  `CoverageDiagnostic.per_strategy_counts` (`strategy_id -> {n_selected,
  n_merged_away}`) -- structured, not folded into `reason` prose, so Eval
  can later measure the over-exclusion rate (1-of-6 rejected reads very
  differently from 5-of-6) and calibrate a v2 threshold instead of
  treating the binary bar as ground truth. 4 new tests (distinguishing
  1-of-6 from a clear majority-redundant case, populated even in the
  `budget_full` branch since partial data is still informative, empty for
  an empty selection). 32/32 in `test_fusion.py`.
- Scheduling-hint semantics for portfolio execution (Router ↔ Retriever):
  execution order is scheduling not fallback-priority (§11 reordering
  contract already proves order-invariance of enforced quantities).
- token_budget consumer-sourcing (Chat + Retriever + Eval, in flight):
  Chat's context-window math per caller_mode replaces static values;
  Eval ruling on record — token_budget is NOT a calibration-cell dimension.

## 11. Data-collection posture + return-to-blend gate (Eval, 2026-07-24)

**Status: the blend is DEACTIVATED (allocator weight 0), not deleted.** Ananth's
call after Eval's counsel: the blend was built ahead of its data (all priors are
hand-set seeds, no measured recall curves, no real q_i/λ). We pull back to a
data-collection posture and return ONLY when the curves are real. The scaffolding
(RRF, MMR, capacity transform, portfolio allocator) stays parked and tested.

**What we collect (the curve source):** OFFLINE, a 100→150-200 question labeled
bank, FULL forced matrix (a/b/c/d/s on EVERY query — not router-selected, to kill
selection bias), top-X = max fetch depth, PREFIX-GRADED at K∈{1,3,5,10} (the
rubric score on a top-K prefix == recall@K; no LLM index self-reporting). Curves
stratified by depth_bucket — a pooled curve averages opposite shapes and is a lie.
Deterministic strategies (a/b/s) grade prefixes once; c/d need repeats for variance.
Tool: `scripts/prefix_grade.py` → `eval/artifacts/recall_curves.json`.

**What prod-forced (1-in-5) buys:** representativeness + fill-depth + latency/cost
ONLY. Production traffic has no must_facts, so it yields NO recall curve — recall
comes exclusively from the offline labeled bank. Do not degrade prod traffic to
"collect data" that can't be labeled.

**Return-to-blend gate (all three required — written so this posture has an exit):**
1. **Coverage:** every (strategy, depth_bucket) cell has N ≥ ~50 real observations
   (the fleet's own priors_bootstrap convention). ~20-30 suffices to LOCATE a
   plateau; 50 to trust its LEVEL.
2. **Structure:** the curves show real plateau structure (recall@K flattening) —
   the precondition that makes "top-3 of a + top-2 of b" a data-grounded claim
   rather than a guess.
3. **Out-of-sample proof:** a SIMULATED blend, built from the curves and evaluated
   on HELD-OUT queries with the same judge, BEATS the best single strategy. If it
   doesn't, we've learned the blend was the wrong bet and we ship the best single
   strategy instead — the collection was still worth it.

Only when 1∧2∧3 hold does the allocator weight come off 0. Until then, single
strategy (safe serving) + forced matrix (data engine).

## Who to talk to

- **Router** ("4c - Router"): portfolio allocation math, ladder/continuation
  reshape, q-calibration inputs.
- **Synthesizer** ("4f - Synthesizer"): fusion implementation (RRF, MMR,
  neighbor-completion reordering), retention mechanics on the Synthesis side.
- **Eval**: RRF/diversity-floor ruling, λ calibration, reward-signal
  implications, baseline management.
- **Retriever** (this session): coordinating, orchestrator-side retention
  wiring, cross-team alignment.

Contribute directly by editing this file — it's the live record, not a
snapshot of chat messages.

## Build progress

- **RRF fusion (Synthesizer, 2026-07-24): built, standalone, NOT wired.**
  `app/services/retriever/fusion.py`'s `rrf_fuse()` — takes an explicit
  `strategy_id -> that strategy's own rank-ordered FilledChunk list`
  mapping (deliberately not deriving strategy identity from
  `assignment_reason` or any other existing field, since retention's real
  integration shape for "which strategy produced this chunk" on a slot's
  unioned list isn't settled yet). Identity merging across strategies
  reuses `synthesis.py`'s `_content_keys` directly (imported, not
  reimplemented) so the two modules can never drift on "same chunk."
  11 new tests in `test_fusion.py`, including the exact incomparable-
  scales scenario from Eval's ruling (a huge raw score at rank 2 does not
  outrank a tiny raw score at rank 1 -- rrf_fuse never reads
  `original_score` at all) and cross-strategy consensus merging (same
  identity surfaced by 2 strategies gets summed reciprocal-rank
  contributions, outranking a single-strategy hit). Not touching
  `synthesis.py`'s live `compile_synthesis` path per Retriever's explicit
  ask — integration wiring waits for retention's real shape to land.

- **MMR selection (Synthesizer, 2026-07-24): built, standalone, NOT
  wired.** Same `fusion.py`, `mmr_select()` -- realizes RRF's ranking into
  an actual fill-to-budget selection per S4's now-RESOLVED ruling (TF-IDF
  not embeddings, λ seeded 0.7, conservative redundancy threshold,
  required merged-pair instrumentation). Built once S4's blocking question
  resolved, same "settled pieces don't queue behind unrelated open ones"
  logic Retriever applied to RRF.
  - **TF-IDF cosine similarity, dependency-free** (`_tf_idf_vectors`/
    `_cosine_similarity`) -- no external ML library; only ever runs over
    one slot's candidate set (tens of chunks), so a from-scratch
    vectorizer is cheap and doesn't add a new fleet dependency, matching
    the whole reason TF-IDF was chosen over embeddings in the first place.
  - **`DEFAULT_MMR_LAMBDA = 0.7`** and **`DEFAULT_REDUNDANCY_THRESHOLD =
    0.85`** — both explicit, documented, uncalibrated placeholders per
    Eval's seed-then-calibrate posture, not tuned constants.
  - **Eval's required instrumentation implemented**: `MmrSelection.
    merged_away` returns the actual `(dropped, kept_because_of)` pairs,
    not just a count — `pairs_merged` is the count, `merged_away` is what
    lets offline calibration check whether a merged-away chunk carried a
    must_fact the survivor didn't (that specific check needs Eval's
    must-fact bank and happens downstream; this module only guarantees the
    pairs aren't thrown away before that check can run).
  - **9 new tests**, including the two cases Eval specifically flagged as
    the real risk: a near-duplicate pair correctly merges (`180 days to
    file claims` phrased identically twice), and two chunks sharing topic
    anchors but stating DIFFERENT facts (different procedure codes, same
    payer/topic) are correctly BOTH kept, not merged — the over-merging
    failure mode Eval called worse than under-merging.
  - Still not wired: needs a real fused/ranked candidate list from
    `rrf_fuse()` plus `synthesis.py`'s real `_estimate_tokens` (injected
    via the `estimate_tokens` param, not imported, so this module doesn't
    reach further into `synthesis.py` than the one `_content_keys` helper
    it already shares).

20/20 tests passing in `test_fusion.py`; full retriever+router suite
confirmed clean aside from one stale assertion in `test_synthesis.py`
(fixed — `segment_ms` grew a `budget_enforcement_ms` key since that test
was written, not a regression) and two pre-existing, out-of-scope
failures in `test_integration_production_shapes.py` (Router
planning/ladder-collapse regression guards, unrelated to Synthesis/fusion
work — likely gated on this doc's own §8 portfolio work landing, not
something Synthesizer is fixing).

- **CoverageDiagnostic construction (Synthesizer, 2026-07-24): built,
  standalone, NOT wired.** `fusion.py`'s `derive_coverage_diagnostic()` —
  implements the RESOLVED shape above, but with the corrected
  `saturated_strategies` definition (see "CORRECTION post-build" note in
  the resolved section) found while writing tests, not caught by
  inspection. `POOL_VERDICT_GAPS_REMAIN`/`_SATURATED`/`_BUDGET_FULL`
  constants exported. Priority order exactly as agreed: `budget_full`
  first (checks `MmrSelection.budget_cutoff_remaining`), then `saturated`
  (corrected definition), then `gaps_remain`. 7 new tests, including one
  proving the vacuous-truth trap (empty selection must read `gaps_remain`,
  not `saturated`, despite an empty set being a trivial superset of
  another empty set). 29/29 in `test_fusion.py`. Awaiting Router's
  re-confirmation on the corrected definition before this is fully
  settled — flagged directly, not silently landed.

- **RRF+MMR wired live into `compile_synthesis` (Synthesizer, 2026-07-24):
  DONE, then immediately followed by the §11 pullback the same day.**
  Retention landed upstream, so the standalone pieces above got wired into
  the real per-slot pipeline (strategy grouping via `assignment_reason`,
  per-slot token sub-budget from `per_slot_payload_tokens` as split
  weights, `coverage_diagnostics` populated per slot). 83/83 in the
  combined `test_synthesis.py`+`test_fusion.py` suite; full retriever+
  router suite re-checked clean (607 passed/2 skipped, the only failures
  an unrelated shared-DB connection-pool exhaustion, verified in isolation
  not a fusion regression). Reported to Router/Eval same day; both
  confirmed no objection and the wiring was sound to grade against.

- **§11 pullback — `data_collection_mode` guard + log-only instrumentation
  (Synthesizer, 2026-07-24, same day): BUILT, the fusion above SHELVED not
  deleted.** Added an explicit `data_collection_mode: bool = False` param
  to `compile_synthesis` (default off — every existing call site is
  unaffected). When `True`, per slot: skip MMR's real redundancy-drop/
  budget-cutoff entirely (take the RRF-fused list in full, unchanged
  order), so a forced strategy's true top-X reaches Chat/Eval
  uncontaminated by MMR's still-uncalibrated `λ`/`redundancy_threshold` —
  exactly the contamination this pullback exists to avoid. MMR still runs
  once per slot as a **probe** (real per-slot budget, output never applied
  to the real citations): feeds a new log-only telemetry counter
  `fusion_redundant_detected_not_dropped` (near-duplicate density per
  slot, a real future λ/threshold calibration input, per Retriever/Eval's
  ask) and a genuine `budget_full`-vs-`gaps_remain` split on
  `coverage_diagnostics` (did the forced strategy's own content exceed its
  per-slot share — a real fill-depth signal even single-strategy).
  `saturated` deliberately never fires in this mode (no redundancy is ever
  actually applied to the real output, so reporting it would misrepresent
  what happened) — confirmed as the intended, not accidental, degradation.

  **Real bug caught and fixed before this shipped, not by inspection but
  by running the existing test suite**: the guard was first implemented
  as `if len(grouped_by_strategy) <= 1`, inferring "data collection" from
  chunk shape rather than an explicit flag. That broke
  `test_per_slot_payload_tokens_splits_budget_across_slots` immediately —
  a slot organically having only one strategy's chunks is a completely
  normal outcome in regular blend-mode operation too (e.g. filler_a alone
  satisfies a slot), and shape-inference would have silently disabled real
  per-slot MMR budget-splitting for that case, not just the intended
  forced-single-strategy data-collection posture. Fixed by making the mode
  an explicit caller-declared parameter instead, with a defensive warning
  log (not a silent wrong branch) if a slot ever has >1 strategy while the
  caller declares `data_collection_mode=True` — shouldn't happen per
  Router's design, but worth surfacing if it ever does. 4 new tests added
  (`TestDataCollectionMode`): bypass keeps all chunks despite a starved
  per-slot share, `budget_full` fires without dropping, near-duplicate
  chunks survive with `saturated` correctly never firing and the log-only
  counter incrementing, and the multi-strategy defensive-warning path. 87/
  87 passing in the combined suite; full non-integration retriever suite
  (352 passed/2 skipped) re-confirmed clean.

  Orchestrator-side wiring (threading Router's forced-strategy state into
  `data_collection_mode=True` on the `compile_synthesis` call) is
  Retriever's side of this, not done here — flagging as the next
  coordination step.
