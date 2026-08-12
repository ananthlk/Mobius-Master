# Real (depth_bucket, strategy) Priors — from the 22-query forced-filler bank run

**Source:** `mobius-rag/eval/artifacts/forced_filler_bank_run.json`, merged with real `pool_metadata` (top_score_percentile/pool_size/distinct_content_topk) backfilled by Retriever via Gate+Pool-only re-run (no re-hit on c/d/s external calls). `depth_bucket` computed via the real `priors.compute_depth_bucket()` — same function Router uses in production, not a hand-derived approximation. cmhc016/cmhc021 correctly excluded (zero-slot CLARIFY short-circuits, no depth signal — see corrected note in `forced-filler-bank-grading-report.md`).

## Real per-(bucket, strategy) recall + latency

| bucket | strategy | n | mean recall | mean latency |
|---|---|---|---|---|
| 2 (moderate) | a | 11 | 0.952 | 686ms |
| 2 (moderate) | b | 11 | 0.727 | 619ms |
| 2 (moderate) | c | 11 | 0.121 | 14,308ms |
| 2 (moderate) | d | 11 | 0.970 | 11,455ms |
| 2 (moderate) | s | 11 | 0.000 | 769ms |
| 3 (broad-mod) | a | 9 | 0.927 | 637ms |
| 3 (broad-mod) | b | 9 | 0.592 | 647ms |
| 3 (broad-mod) | c | 9 | 0.258 | 17,962ms |
| 3 (broad-mod) | d | 9 | 0.963 | 11,938ms |
| 3 (broad-mod) | s | 9 | 0.000 | 874ms |

## Honest limitations, before anyone treats this as final

1. **Only buckets 2 and 3 are represented.** Zero real observations for buckets 0, 1, 4 — this bank's queries all land in the moderate/broad-moderate range (pool_size 335-836, mostly hundreds not tens). Buckets 0/1/4 must stay on seed priors (n=8 pseudo-count) until a bank with genuinely tight and genuinely broad queries produces real data for those cells.
2. **Sample size per cell is small (9-11), comparable to the n=8 seed pseudo-count, not dramatically better.** Real, but don't treat this as a large-N empirical result — it's a first real data point, not a converged measurement. Wilson/Beta LB math should still apply real n here (9 or 11, not the seed's 8), which will already meaningfully tighten the bound vs. the seed.
3. **Precision is not differentiated by this bank at all** — zero `forbidden_facts` triggered across all 110 (query, strategy) cells in the original grading. This bank isn't adversarial enough to measure precision; recall is the only real signal here. Don't read "0 forbidden hits" as "these strategies are equally precise" — it means this bank doesn't test precision.
4. **`s` correctly reads 0.000 in both buckets** — none of these 20 queries are payor-tag-relevant, consistent with `s`'s scoped eligibility (tag-gated to `j:payor.*`). This isn't evidence s performs poorly; it's evidence this bank doesn't exercise it. A payor-tag-relevant bank is needed for real `s` priors.
5. **Bucket 3's weaker `b` recall (0.592 vs bucket 2's 0.727)** is the one directionally-sensible real signal here — broader pools are harder for the vector arm, consistent with the general depth-vs-recall intuition the seed priors encode. Worth noting as the one place this small sample actually confirms the expected shape, not just measures noise.

## Reconciliation, RESOLVED (Eval, 2026-07-23, per Router's ask) — "slot satisfied" event definition

Router correctly identified that folding raw graded-recall fractions into `recall_lift` cells would mix two different random variables: `recall_lift`'s operational meaning is `P(this rung satisfies the slot)` — a binary event the LB math and chain composition condition on — while my grading produced a continuous "fraction of must_facts found." Reconciling requires a ratified binarization threshold, and this is the same underlying question as the Observer §3 evidence-proxy design (what counts as "this attempt succeeded"), so it's being resolved once, here, for both.

**Ratified definition: slot satisfied ≡ recall == 1.0 (ALL must_facts found), not a partial threshold.** Justification: `must_facts` are explicitly the facts required for the answer to be considered correct in this domain (payer rules, timely-filing windows, PA thresholds) — a partial match (e.g., stating the 180-day participating-provider window while omitting the 365-day non-participating window) is not a merely-incomplete-but-acceptable answer, it's a materially wrong one in a compliance-sensitive context. A lenient threshold (e.g., ≥0.5) would launder genuinely incomplete answers into "success" for bandit-reward purposes. Full-recall is the right bar.

**Binary success counts, buckets 2/3, strategies a/b/c/d only (s excluded per Router's do-not-fold ruling):**

| bucket | strategy | n | successes | success_rate |
|---|---|---|---|---|
| 2 | a | 11 | 9 | 0.818 |
| 2 | b | 11 | 8 | 0.727 |
| 2 | c | 11 | 1 | 0.091 |
| 2 | d | 11 | 10 | 0.909 |
| 3 | a | 9 | 7 | 0.778 |
| 3 | b | 9 | 5 | 0.556 |
| 3 | c | 9 | 0 | 0.000 |
| 3 | d | 9 | 8 | 0.889 |

This is what Router should feed as (successes, n) into the Beta update (α += successes, β += n − successes) per cell, per the mechanism already described in their message — not the earlier fractional-recall table, which mixed the wrong quantity.

## Comparison to seed priors (priors_bootstrap.yaml)

Seed depth_2/depth_3 `a`/`d` recall_lift values (0.50-0.55 range) are noticeably lower than what real data shows here (0.93-0.97) — but seed `recall_lift` and this table's `recall` aren't quite the same quantity (recall_lift is P(strategy alone clears the slot), this is fraction of must_facts found across occupied chunks) — a real methodology reconciliation is needed before treating this as "seeds were wrong by 2x," not just eyeballing the gap. Flagging as a real open question for whoever owns the seed→empirical transition, not resolving it here.
