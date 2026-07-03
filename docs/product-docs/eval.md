# Evaluation & Quality
> How Mobius measures retrieval and answer quality — the calibration harness, the two adjudicators, the current baseline numbers, and the methodology that keeps a "lift" from being a plumbing bug.

## Purpose
The eval system answers two questions: **"is retrieval finding the right facts?"** and **"is the answer correct?"** — and, crucially, **"did a change actually help, or did we fool ourselves?"** It runs labeled query banks against the deployed agent, scores them with LLM adjudicators, and stamps every run with a version fingerprint so a metric move can be attributed to the thing that changed.

## Audience
Developers / RAG engineers tuning retrieval, routing, the lexicon, or the corpus — and anyone asking "what's our current quality number and can I trust it?"

## What we measure (the harness)
- **Calibration harness** — `mobius-rag/eval/calibrate.py` (`run_calibration`). Runs each query × 5 strategies (a/b/c/d forced + `natural` = the router's choice) = **110 cells** against the deployed agent, scores retrieval, and persists results live.
- **Test banks** — `eval/queries_cmhc.yaml` (22 CMHC queries, each with golden `must_facts`) + a 3-query smoke bank. **Gotcha:** the legacy `eval/queries.yaml` has **no `must_facts`**, so running it yields all-zero scores — always use the cmhc bank.
- **Two adjudicators, two different questions:**
  - **Retrieval fact-checker** — `app/services/fact_checker.py` (`check_facts`). An LLM critic that checks whether the golden `must_facts` are **present in the retrieved chunks** (chunk-only recall) and flags contradictions. Scores **retrieval**, not the answer.
  - **Answer-quality judge** — `eval/judge.py` (`adjudicate`). A correct/partial/wrong verdict for the **full chat pipeline**, used on legacy banks without `must_facts`.
- **Metrics (5-axis)** — computed in `app/routers/eval.py::_summarize_cells`: answer_rate, **recall** (facts found in chunks), **precision** (indexed: cited / min(n_chunks, n_facts), a true [0,1]), latency, cost, plus contradiction-per-cell. **Weighted composite = 0.45·recall + 0.30·precision + 0.25·speed** (speed = 1/(1+lat_s)).
- **Storage** — Postgres `rag_eval_runs` (one row per run + `config_dump.fingerprint`) and `rag_eval_results` (one row per cell with the full retrieval trace).
- **Read APIs** — `GET /api/eval/runs/{id}/calibration_summary`, `/api/eval/timeline`, `/api/eval/compare?a&b`, `/api/eval/drift`.
- **UI** — a "Run Calibration" button + summary panel (`EvalTab.tsx`); the timeline/compare UI is planned.

## Current baseline (source of truth)
- **Authoritative: run `2ecb72ab`** (v2.1 canonical-blend + retrieval fixes; 21/22 queries; judge **locked to gemini-2.5-pro**; fact-checker recall):
  - **router_recall 0.448 · oracle 0.507 · composite 0.529 · routing efficiency 88% of oracle · strategy b picked 5×** (was 0).
- **Prior clean baseline: run `41b5c5e7`** (v2.0, pre-blend) — router 0.392, oracle 0.590. The blend lift = Δrouter **+0.056**.
- **Corpus vs external:** corpus-only oracle (a/b) 0.469 vs full oracle (with web/c/d) 0.507 → external adds only **+0.038**; the router captures **96% of the corpus-reachable ceiling**. **Routing is near-solved; the corpus is the frontier.**
- **Two metric regimes — never mix them in a comparison:** (a) fact-checker **retrieval recall** (current calibration, **0.448**) vs (b) chat-pipeline **answer-quality verdict** (older, **~0.28**, run `c24ac27a`). They answer different questions.
- **Superseded — do NOT cite:** the "lexicon regressed −0.08" run (`75524dd1`) was a retrieval **bug**, not a regression; the 0.505 avg was **void** (adjudicator bug era).

## Methodology
- **Forced-strategy calibration** — force each of a/b/c/d per query to measure its true performance. **oracle** = per-query max over the forced arms; **router** = the bandit/prior choice; **headroom** = oracle − router. This is the correct method (not the oracle-path shortcut).
- **Adjudicator locked** — the judge silently scored 0 for a period due to 5 stacked bugs + a `max_tokens` truncation (all fixed). It's now **locked to a single model (gemini-2.5-pro)** so deltas reflect real lift, not judge variance.
- **Fact-check F1 (honesty-weighted)** — F1 = recall × accuracy: full credit for honest abstention, credit for grounded facts, penalty for contradictions/hallucinations. Historical arm ranking d > b > a > c; answer-accuracy ceiling ~0.31.
- **Lift vs Drift (eval observability)** — every run stamps a version **fingerprint** {priors_version, lexicon_revision, agent_revision, corpus_snapshot_at, judge_model, bank_hash} captured *inside* `run_calibration` (invocation-agnostic). **Lift** = metric moved **and** fingerprint changed → attribute to the changed dim. **Drift** = metric moved **and** fingerprint unchanged → alert. **`fingerprint_stable`** flags runs whose cells straddled a deploy (mixed-build confound → excluded from attribution). Spec: `eval/calibration/EVAL_OBSERVABILITY_SPEC.md`. (σ-band + UI planned.)

## Recent changes (~last 2 weeks)
- Fixed the 5-bug adjudicator → the judge scores real verdicts again; locked it to gemini-2.5-pro.
- Built the reusable fact-checker retrieval critic + indexed precision.
- Retrieval-path fixes: BM25 now runs on the full candidate pool (was collapsing wide pools to ~6 vector-picked docs); the cascade now keeps the router's chosen strategy when it returns well-ranked chunks.
- Canonical/factual prior blend (priors v2.1): strategy b now wins its niche → router 0.392 → 0.448, efficiency 66% → 88%.
- Eval observability shipped (fingerprint + timeline/compare/drift endpoints).
- **Key finding:** routing is near-optimal; the lever is now **corpus findability** — table-of-contents / navigation chunks pollute retrieval (they match titles but answer nothing), and some "corpus gaps" are keyword/term mismatches, not missing content.

## Caveats (read before quoting a number)
- **Judge independence** — the adjudicator is locked to one model; never change it mid-comparison or deltas become judge noise.
- **The corpus is the bottleneck, not routing** — oracle ceiling is low (~0.47 corpus recall, ~0.31 answer accuracy); routing can only surface the best answer that *exists* in the corpus. External/web adds only +0.038.
- **Mixed-build confound** — comparing runs across a deploy is invalid; hold the agent build constant across a baseline/final bracket (`fingerprint_stable` catches violations).
- **σ not yet established** — need ~5 same-config runs for the noise floor; until then small lifts aren't distinguishable from run-to-run noise (esp. strategy d = web).
- **Meta-lesson:** three times a "moved metric" turned out to be a plumbing bug, not the change under test — **always trace a delta to the mechanism before believing it.**

## Doc-readiness notes
- **Primary audience tag:** dev.
- **Source:** authored 2026-07-03 from the EVAL agent's inventory (numbers as of 2026-07-02). Exact run IDs and query-level examples available on request via the docs_gap loop.
- **For the loop:** this doc's `module` slug is `eval` (new — add to the feedback agent's `MODULE_SLUGS` so docs_gap area_tags join cleanly).
