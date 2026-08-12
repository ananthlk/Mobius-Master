# Retriever — Cross-Module Metrics Scoreboard

**Owner:** Retriever agent (accountable to TECH/architects for overall answer-engine health, not just per-module process sign-off).
**Purpose:** track latency, accuracy/recall, and test coverage across ALL modules as they ship — a rollup TECH can query at any point, not something reconstructed after the fact.
**Status:** STARTED 2026-07-23 (gap identified by Ananth — process tracking existed, metrics rollup didn't).

---

## STANDING TRACKED FOLLOW-UPS (do not let these quietly disappear once a module ships)

Per Ananth's explicit instruction 2026-07-23: items here survive past module sign-off and get revisited on their own trigger condition, not forgotten once "shippable" status is reached. Both Retriever and the relevant sub-agent own remembering these.

| Item | Owner(s) | Trigger to revisit | Status |
|---|---|---|---|
| **Lexicon-embeddings cache** (fixes both FAN_OUT cold-start ~10-14s AND ~9.2s warm-state embed cost) | DB (design) + Shape-Reformat (consumer) | **Ananth's explicit call 2026-07-23: NOT now.** Accepted current FAN_OUT latency as livable short-term; fix ships bundled with the Curation refactor whenever that lands. This is a deliberate deferral, not neglect — revisit when Curation refactor starts, don't build early. | 🔵 DEFERRED (by decision, not oversight) |
| **Fan-out cost distribution across domains** | Shape-Reformat | Before "4× Pool cost" becomes a firm Pool-planning number — only `eligibility` (80 siblings) tested repeatedly so far | 🔵 OPEN |
| **DB claims requiring correction (2026-07-23, Reformat verified, didn't accept at face value):** (1) DB claimed `reformat.py` already has a placeholder for a future `lexicon_embeddings` JOIN — **checked directly, false, does not exist.** (2) DB's cold-start improvement projection (7.5s→3.5-4s post-cache) assumes payload size drives the cost — **more likely the Vertex auth handshake itself (a fixed cost, not proportional to batch size), unverified extrapolation.** Do not let this projection harden into a monitoring threshold until actually measured post-cache. | Shape-Reformat (caught), Retriever (holding record) | When the cache actually lands and cold-start can be re-measured for real | 🟡 Correction on record, not yet re-measured |

---

## Chain-wide latency budget (target, not yet fully measured end-to-end)

| Segment | Target | Measured | Source | Status |
|---|---|---|---|---|
| Shape: Gate | part of <500ms shape-phase budget (per `module-gates.md` §1, scope corrected by DB — budget is whole-phase, not gate-alone) | **~52ms true server-side** (isolated EXPLAIN ANALYZE); app-layer 213ms-5906ms range due to dev-proxy tunnel overhead, won't reproduce in production | Shape-Gate, independently re-verified by Retriever | ✅ well within budget |
| Shape: Reformat (non-FAN_OUT postures) | shares the same shape-phase budget | 9ms–1.5s (PRECISE/CLARIFY/RELY_ON_EXTERNAL/DECLINE, DB-only), independently re-verified | Shape-Reformat, re-run by Retriever | ✅ fine |
| Shape: Reformat (FAN_OUT posture) | shares the same shape-phase budget | **MAJOR FIX 2026-07-23 — root cause found: shared `embedding_provider.py` hard-codes `batch_size=5` for non-gemini Vertex models (confirmed live, line 89), not a real API limit. Real Vertex ceiling is 250 instances/call (confirmed via actual `400` error at 294).** Reformat bypasses the shared abstraction, batches at the real limit. **TWO regimes — track separately, do NOT collapse into one number:**<br>• **Warm** (same long-running process): Reformat n=7 = 2277-2629ms (median 2422ms). Retriever's 2 follow-up calls = 4143ms, 3885ms. **These do NOT tightly match (~1.5-1.7x apart, not noise-level) — logged as UNRESOLVED, not smoothed over.** Possible causes, neither isolated yet: cross-session network/environment variance, or dev-proxy-adjacent variance (documented pattern of unpredictable degradation in this environment). **Neither number should be cited as "the" warm figure until this gap is understood.**<br>• **Cold** (fresh process / instance spin-up): 3 independent observations — Reformat 7538ms, Retriever 10398ms + 14398ms. **Real range 7.5-14.4s, not a single artifact** — recorded as genuinely variable. | Reformat (n=7 warm + 1 cold) + Retriever (2 warm + 2 cold, independent) | 🟡 **Embedding batch-size bug FIXED** (rough order-of-magnitude improvement, exact warm-state multiplier still unresolved per above). **Caching's effect on cold-start: reduces, does NOT eliminate** (corrected from an earlier overclaim) — the query itself always needs one live embed call regardless of what's cached, and if the Vertex auth handshake (not payload size) dominates cold-start (unverified, flagged to DB), caching helps less than hoped. Don't let "caching solves cold-start" harden as an assumption before it's measured. |
| Shape: Structure | shares the same shape-phase budget | Pure/sync, zero DB calls (verified in DB's sign-off) — negligible, folds into whichever of Gate/Reformat's numbers apply | Shape-Structure, wired + verified live by Retriever | ✅ zero added cost |
| **Full chain (Gate+Reformat+Structure via `orchestrator.py`)** | n/a — first standing measurement | 5-case spot-check, re-verified twice: non-FAN_OUT cases 22ms–5.9s total (Gate's dev-proxy variance dominates), FAN_OUT case 9.3s–10.4s total (Reformat's embed cost dominates). **Not yet a proper sample (n=1 per case)** — this is a first log entry, not a characterized distribution. | Retriever, 2 independent runs | 🟡 Structurally correct on all 5 postures; latency **not yet a standing sampled metric**, logged as a known gap |
| Pool | separate budget, TBD | not yet built | — | — |
| Router / Fillers / Synthesis / Contract / Timing | separate budgets, TBD | not yet built | — | — |

## Accuracy / recall (per module, rolling)

| Module | Test set | Result | Notes |
|---|---|---|---|
| Shape: Gate | cmhc 22-query bank | 20/22 exact, 2/22 underspecified (both real Curation-filed lexicon gaps, not gate bugs) | Answer-quality-anchored bank |
| Shape: Gate | contour bank v2 (26 queries) | 25/25 scored pass + 1 documented xfail | Contour-diversity-anchored bank, co-built with Eval |
| Shape: Gate | code_expand follow-on | 3/3 claimed contour corrections verified live (H0019 cases) | No regression on either bank above after this landed |
| Shape: Reformat | `queries_reformat_postures.yaml` (13 cases) | **13/13 fully matched**, re-confirmed again 2026-07-23 (Reformat's own status update quoted 12/13 — that number is now stale; their reformat005 bank fix has been live since my first re-run and I re-verified 13/13 a second time just now) | Theme clustering (reformat003, 80 real eligibility siblings) verified: k-means, 3 semantically distinct themes (31/32/17 split) + 1 catchall, replaced average-linkage after it collapsed 78/80 into one cluster live |

## Test coverage (unit + integration)

| Module | Pure unit tests | DB-integration tests | Known issues |
|---|---|---|---|
| Shape: Gate (`test_shape_gate.py`) | 33/33 pass | Pass individually; known pytest-asyncio batch-flakiness (event-loop/pool scoping) when run as a full class together — logged, not a gate defect | Non-blocking, needs a fix eventually |
| Shape: Gate (`test_code_expand.py`) | 8/9 pass in batch, 9/9 pass individually | Same known batch-flakiness pattern | Same as above |
| Shape: Reformat | `tests/test_shape_reformat.py`, **30 tests** — verified independently: 28/30 pass as a batch, the 2 failures are the same documented pytest-asyncio order-dependent flakiness as Gate's suite (confirmed: both pass in true isolation) | Matches Gate's bar now (pure unit + DB-integration split, same pattern) | Gap closed — went from 0 tests to a real suite covering dispatch logic, cosine/clustering math, union-prevalence correctness, and a narration regression guard |

## Sign-off status (process — this part IS tracked)

| Module | Chat | UX | Eval | DB | Curation | TECH |
|---|---|---|---|---|---|---|
| Shape: Gate | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ CLOSED |
| Shape: Reformat | ✅ | ✅ | ✅ | ✅ | n/a so far | ✅ **CLOSED 2026-07-23** — TECH confirmed live: "Shape module is production-ready. Caller_mode vocabulary is a separate fleet-level fix, already tracked by Broadcast." |
| Shape: Structure | ✅ | ✅ | ✅ | ✅ | n/a | ✅ CLOSED (covered by TECH's whole-Shape ruling above) |

**SHAPE IS FULLY CLOSED 2026-07-23. All three sub-modules (Gate, Reformat, Structure) signed off by all six architects.**

| Pool (Step 2) | ✅ | ✅ | ✅ | ✅ | n/a | ✅ **CLOSED 2026-07-23** — all gates (b/d/e/i) confirmed, neighbor-truncation fix validated as structurally sound |

**POOL IS FULLY CLOSED 2026-07-23. 5/5 signed off. Next: real cmhc-26 before/after calibration run (Eval), then Router (Step 3) kickoff.**

**Pool build underway, real code (not just spec):** `app/services/retriever/pool/{contracts,dedup,public_adapter,pool}.py`. 9/9 pure unit tests pass; 8/8 DB-integration tests pass individually (3/17 fail only under a pre-existing cross-suite pytest-asyncio event-loop artifact, also independently reproduced on Reformat's tests — not a Pool defect, flagged for test-infra owner). Two real bugs found+fixed verifying against live data: a JSON-null-literal crash on `chunk_{d,p,j}_tags` (~55k rows) and a serious latent truncation bug in the shared legacy `_expand_with_neighbors()` (silently drops real seed matches, not just neighbors, past its hardcoded `_NEIGHBOR_TOTAL_CAP=50` — Pool's real 378-candidate union would have silently lost 328 matches uncaught). Live EXPLAIN ANALYZE confirms the chunk-tag query stays bounded (0.277ms, bitmap index scan) even ahead of DB's GIN migration landing.

---

## Fan-out cost signal (for Pool's future budget planning)

Hard-capped at `MAX_FANOUT_THEMES=4` by design (3 named themes + 1 catchall). Every live run so far produced exactly 4 rewritten_queries — **but only one domain tested repeatedly (eligibility, 80 siblings), not a diverse sample.** Treat "4× Pool cost per FAN_OUT" as a safe planning upper bound, not yet a measured distribution across domains. Revisit once more domains are exercised.

## Open asks (as of 2026-07-23)

1. **End-to-end latency** — Gate+Reformat now combinable via `orchestrator.py` (committed `6cb9603`); no Structure/Pool yet, so still not a full-chain number.
2. **Embedding bottleneck** — the one remaining FAN_OUT blocker (~9.2s), DB's call on a precomputed lexicon-embedding cache (design + refresh-trigger ownership).
3. **Fan-out cost distribution** — only 1 domain sampled so far; get a second/third domain (e.g. `health_care_services`, 631 siblings) exercised before treating "4×" as a firm Pool-planning number.
4. **This scoreboard is now a standing habit**, not a one-time catch-up — updated live as each module reports, verified independently each time (not just recorded at face value).
