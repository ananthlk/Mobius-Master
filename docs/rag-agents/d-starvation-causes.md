> **Payor Policy Agent** doc (rebranded 2026-07-27 — this RAG module, corpus +
> retrieval logic together, is scoped to payor-policy Q&A: timely filing,
> prior auth, coverage rules). Was filed under "Retriever."

# Why `d` (web) rarely fires in live traffic — 4 distinct causes

Status as of 2026-07-26. `d` is the highest-recall single arm in Eval's forced-arm
calibration (0.67 marginal recall@K10, vs `a`'s 0.46) but was found to almost
never execute in live/router traffic. Root-caused across Retriever, Router, Eval,
Web Search — four SEPARATE, independent causes, not one bug. Capturing all four
together so nobody re-discovers #1-3 while chasing what looks like #4 on a
different payer, or vice versa.

## 1. Payload-budget / capacity mismatch — FIXED
`token_allowance_per_slot` (3000) was derived from a capacity-5 measurement
("a full d-slot at capacity=5 measured ~2,021 tokens"). Live slots run at
capacity=10 — `d`'s worst-case payload doubled (5,000 tokens) but the budget
never rescaled, so `d` got skipped `payload_over_token_allowance` at planning
time regardless of its (good) priors.
**Fix:** Router's `assign_chain_fills` (portfolio.py) — all-or-nothing payload
gate replaced with joint partial-fill assignment (diversity floor + value
knapsack). `d` now gets a budget-scoped partial fill instead of being excluded
outright. Deployed + orchestrator wired to consume the fill (capacity-capping
via `_capped_slot`, mobius-rag/app/services/retriever/orchestrator.py).

## 2. Bare-occupancy stopgap truncating chains before `d`'s turn — PARTIALLY FIXED
The old `_stopgap_verdict` treated ANY non-zero occupancy from an earlier rung
(e.g. `a`) as fully satisfying the slot, stopping the chain before it ever
reached `d`, regardless of whether `a`'s chunks actually contained the answer.
**Fix (2026-07-26):** replaced with `_observer_verdict` → `observer.py`'s real
per-strategy adequacy bars (capacity-aware for a/b/s, decay-floor score check
for d). This closes the `s`-alone-satisfies bug and the general "any occupancy
satisfies" bug. NOT yet a full fix for `d` reachability — Observer's bars are
still simpler (capacity/decay-floor) than a true content-adequacy judgment;
Eval's proposal to unify Observer's adequacy check with the mode-(c)
groundedness critic (same instrument in eval and prod) is the next step,
scoped as the Observer promotion gate (Chat Master).

## 3. Cold-start latency prior vs warm pre-pooled reality — IN PROGRESS
`priors_bootstrap.yaml`'s `d.latency_p50_ms=3000` is flat across all depth
buckets — a static seed number, never re-derived from real data. At 3000ms,
`d` frequently blows the interactive latency_allowance_ms (~5750) once
combined with other required strategies, excluding it from the PLAN entirely
(not just execution) — confirmed via direct trace inspection (`d` never even
skipped-for-latency in some cases, just never fit the winning combo).
Ananth confirmed live: `d`'s search now fires CONCURRENTLY with Pool
(pre-pooled/prescreen), so by the time the chain reaches `d`'s turn, real
marginal cost should be closer to fetch+extract only — the 3000ms number is
likely a cold-start-only measurement that no longer reflects reality.
**Status:** asked Web Search (owns filler_d/prescreen) for real warm-path
telemetry (prescreen-already-fired → delivered). Router flagged `d` may be
genuinely bimodal (cold vs warm) — a single averaged number would misrepresent
both regimes; may need a cold/warm split rather than one cell.
Once real data exists, it's a single-cell edit to priors_bootstrap.yaml
(Eval's file, code-free).

## 4. Payer-specific crawlability — ROOT-CAUSED, ownership: Payor Platform (fix pending)
Confirmed via direct trace reproduction (not guessed): for cmhc001 (Sunshine
Health FL Medicaid), `payer_crawlable=False` reproduces the live planned chain
EXACTLY (`['s','a','b']`, `d` skip_reason=`crawl_gated_payer_not_crawlable`).
Router's gate (`strategy_crawl_eligible`) is working as designed — fails
closed only on an EXPLICIT False, fails open on None. Not a Router bug.
Sitemap agent's client-side interpretation (`payer_context.py`) also verified
clean — it faithfully maps whatever the registry returns.

**RESOLVED 2026-07-27 (Sitemap agent) — NOT real/current data, a bug in mobius-payor's `robots.py`.**
Fetched Sunshine Health's live robots.txt directly (both hosts, real network
calls, not guessed): `https://sunshinehealth.com/robots.txt` → `307` →
redirects to `https://www.sunshinehealth.com/robots.txt` → `200`,
`User-agent: * / Allow: / ` (only 5 unrelated thank-you pages disallowed).
**Currently, definitively crawlable** — `crawlable=False` does not match live
reality.

Also found corroborating historical evidence: `filler-d-web-tracker.md:85`
recorded a real, live-network-verified `crawlable=True` for this exact payer
on 2026-07-23 — the same site flipping True→False within days is inconsistent
with a stable robots.txt policy change and consistent with a flaky check.

**MECHANISM CORRECTED 2026-07-27 (Payor Platform, verified empirically by
monkeypatching `urlopen` and actually running it — not by reading code, the
same discipline this doc asks of everyone).** The mechanism first proposed
below (an exception from `rp.read()` caching `None` forever) was **wrong**:
`_cache.get(origin)` returns `None` for both an absent key and a
cached-failure value, so `if rp is None` fires either way and a raise-path
failure **re-reads on every call** — Payor Platform ran it: transient
exception → `[False, True, True]` across three calls. It retries; it never
sticks. Fix #1 below (TTL the `None` cache) would have targeted a path that
already self-heals.

**The real permanent-poison path:** an HTTP `403`/`401` fetching
`/robots.txt` is handled by `urllib.robotparser` internally as
`disallow_all=True`, returned **without raising** — so it gets cached as a
*valid* (non-`None`) parser object, which the `if rp is None` retry check
never revisits. Reproduced: transient-403-then-healthy → `[False, False,
False, False]`, `read()` invoked exactly once. This is precisely the path a
bot-walled payer WAF trips — one transient 403 on the robots document itself
locks the origin to `crawlable=False` for the life of the process
(`min-instances=1`, so effectively indefinitely). Sunshine Health's flip
matches this exactly: a fresh process computes `ALLOWED` (confirmed, both
of us fetched live and got `Allow: /`), so a persisting `False` could only
come from a long-lived instance that ate a transient 403 at some point in
its life.

**Fix #2 below (the tri-state conflation) was correct as diagnosed** — that
part of the report held.

**Fixed (Payor Platform, 2026-07-27), deploy held for the freeze:**
`app/robots.py` rewritten to a status-aware fetch — `200`→parse real rules,
`404`/`410`→allow-all, `403`/`401`/`5xx`/timeout/DNS-failure→a genuine third
state (`UNKNOWN`), never coerced into a durable disallow. TTL cache: `200`/
`404` cached 6h, `UNKNOWN` cached 5min so a transient failure self-heals
instead of poisoning and doesn't hammer the origin either. `get_web_domain()`
tri-state precedence: `ALLOWED` on either host wins; else any `UNKNOWN` →
`crawlable=null` (unconstrained search, `d` stays available); only a
CONFIRMED `200`-disallow on every host → `crawlable=False`. `allowed()`
keeps its fail-closed bool contract for actual-fetch callers (correct — "may
I fetch" is a different question from "is this crawlable for routing").
6 new tests (`tests/test_robots.py`), zero prior coverage existed.

**Baseline-data note — RETRACTED (Payor Platform, same day), then INDEPENDENTLY CONFIRMED CLEAN (Eval, same day).** Originally relayed as "the current forced-arm baseline may understate `d`'s recall/availability for bot-walled payers poisoned by the caching bug." **Wrong** — see the "gate is DISABLED" section directly below, which was already documented in this file before the note was relayed: `crawlable` hasn't gated `d` in live traffic since 2026-07-24, so a poisoned `crawlable` value couldn't have understated anything in the current baseline. Should have been cross-checked against the section below before relaying to Router/Eval — flagging the process gap, not just the correction, so it doesn't repeat.

**Eval didn't just accept the retraction — verified it by execution, not assumption:** re-ran the three payer-tagged forced-arm queries (cmhc001/Sunshine — the confirmed-poisoned payer, cmhc019/Aetna, cmhc020/Simply). All three: `d` occupancy=10 (full fetch), judge recall=1.0. **Precise reason the forced numbers stayed clean despite the real poison** — corrected framing (Router, verified against `dispatch.py:124-140` before accepting): it's not just that the crawl-gate happens to be off right now — the forced/calibration dispatch path **structurally never reaches `strategy_crawl_eligible` at all**. `dispatch()` returns early with `bypass_kind="calibration"`/`"forced_strategy"` for `is_calibration`/`forced_strategy` requests (isolation mode: `per_slot={sid: [strategy_id]}` built directly), before the weighted-draw path that would call into `portfolio.py`'s allocator — `strategy_crawl_eligible` (`portfolio.py:292`) only ever executes from inside that allocator. So the forced/calibration path was never exposed to the crawl-gate check *at all*, independent of whether `CRAWL_GATED_STRATEGIES` holds `{"d"}` or `frozenset()`. **This is the more durable statement than "the gate is currently disabled" — the caveat wouldn't reopen even if the gate were re-enabled later, because the forced-arm path structurally bypasses the whole allocator (isolation-measurement mode), not just the crawl check specifically.** Priors/forced-arm `d` data for these payers is trustworthy, no calibration correction needed, permanently on this dimension. Eval will re-verify per-payer router-path `d` once the robots.py fix deploys post-freeze, but that's a router-path check, not a priors-data one.

The robots.py fix itself is still real and still deploying; it matters for other `crawlable` consumers and any future gate re-enable, just not as a live Router/Eval calibration input right now.

Original report (Sitemap agent) below, kept for the trail — mechanism
correction above supersedes the "most likely mechanism" paragraph, sitemap's
symptom finding + fix #2 both held up under Payor Platform's independent
verification:

**Router-side, SEPARATE decision — the gate is DISABLED regardless of the data
bug above (2026-07-24, Ananth via Retriever):** `payer_crawlable` measures
whether OUR fetcher can reach the payor's OWN domain directly, but `d` is a
general web search (Vertex+DDG) that can surface THIRD-PARTY sources even when
a payor's own site is genuinely non-crawlable — the gate's premise conflated
two different questions, independent of whether the payer_crawlable VALUE
itself is trustworthy. `CRAWL_GATED_STRATEGIES` in `allocation.py` is now
`frozenset()` (was `{"d"}`) — dormant, not deleted, one-line reversible.
**Important for whoever fixes the robots.py bug above: fixing the cache bug
does NOT reinstate the gate.** These are two independent decisions — "is the
DATA correct" (Sitemap's finding: no, was a caching bug) and "SHOULD d be
gated on this signal at all" (Ananth's call: no, general web search
shouldn't depend on the payor's own site being crawlable). Re-enabling the
gate after the data bug is fixed would require a SEPARATE, new decision from
Ananth, not an automatic consequence of the data being fixed. **Note even a
future re-enable wouldn't touch forced-arm calibration data** — see the
structural-bypass point in the baseline-data section above (Router,
verified against `dispatch.py`): the forced/calibration path never calls
the allocator at all, so it's exposed to `strategy_crawl_eligible` neither
today nor after any future gate re-enable. Eval's priors
comment for `d`'s cell (previously "P(success | not affirmatively
non-crawlable)") is stale for the same reason and needs re-stating, not a
value change (see `allocation.py`'s `CRAWL_GATED_STRATEGIES` comment for the
full rationale + reversal instructions).

## Verification method (for future reference)
Don't guess between hypotheses — reproduce the allocator call directly with
the query's REAL inputs and read `DecisionTrace.slots[i].steps` for the
strategy's `action`/`skip_reason`:
```python
from app.services.router.optimizer import optimize_allocation
from app.services.router.tracing import DecisionTrace
trace = DecisionTrace()
ladder = optimize_allocation([slot], pool_metadata, resource_posture,
                              bundle=bundle, allocator_name="optimizer", trace=trace)
for st in trace.slots:
    for step in st.steps:
        print(step.strategy_id, step.action, getattr(step, "skip_reason", None))
```
Real `depth_bucket` comes from `compute_depth_bucket(pool_metadata)` using the
query's actual pool_metadata (in `eval/artifacts/forced_filler_bank_run.json`
for the forced bank). `resource_posture` dict keys matter exactly —
`gate_j_codes` (not `j_codes`), `token_allowance_per_slot` (not `token_budget`)
— get these wrong and the reproduction silently diverges from live behavior
without erroring.
