# RAG restructure — EVAL-owned sections

_Owner: EVAL. Slots into `docs/rag-target-structure-spec.md` as the eval-boundary + outcomes-gate sections. Written to a separate file to avoid clobbering TECH's in-progress spec edit in the shared checkout — fold in or reference at your pace._

---

## §A · The EVAL / RAG boundary — a versioned scorer contract (3 tiers)

**Invariant:** `eval-judge == prod-scorer == bandit-reward` = ONE source of truth. The seam is a **versioned contract, not a location** — enforced by version stamp + machine checks, not by which process runs the code.

### Tier 1 — Harness → EXTRACT to the EVAL service
`eval/` (calibrate.py · run.py · judge.py), `app/routers/eval.py` (1586 LOC), the EvalTab dashboard, and the `rag_eval_runs` / `rag_eval_results` storage. This is **offline orchestration + UI + result storage** — no reason to sit in RAG's request-serving deploy. Extraction shrinks RAG's boundary and removes the "eval bloats the serving process" smell.
- **Metric risk:** low (off the serving path). **Tag:** SAFE (characterization test on the endpoints).

### Tier 2 — Scorer → stays in RAG's process, EVAL-owned versioned library
`fact_checker.py` (`check_facts`) + the locked judge-model config + `FACT_CHECKER_VERSION`. **This is the correction to any "just extract it" framing:** `check_facts` runs on the PROD path — the grounding/synthesis grade fires as a background `create_task` on live queries (corpus_search_agent.py:3438/3444/3483) and is the source of the bandit's reward. Extracting it to a service would put a **network hop + a new prod-critical dependency** on the grounding/reward path.
- **Resolution:** package it as a versioned library the EVAL agent OWNS and versions; RAG (and Chat) import the pinned version and run it **in-process**. "One source of truth" = one package version; drift is made visible by the `FACT_CHECKER_VERSION` stamp already in every decision row (same mixed-build guard used for calibration).
- **Tag:** NUMBER-MOVING (any behavior change moves every grade). **Gate:** scorer characterization test — a fixed set of `(query, must_facts, chunks)` → identical scores old/new + identical `FACT_CHECKER_VERSION`.

### Tier 3 — Decision-row writer → shared versioned contract
`rag_query_decisions` is written by BOTH prod (`is_prod=true`, corpus_search_agent) AND eval (`is_prod=false`, calibrate.py). It is the bandit training row: `leaf_key=arm`, `feature_vector=context`, `grades=reward`. Today the writer LOGIC is **forked across two files** — real drift risk. DB's `rqd_prod_not_eval` CHECK enforces the row-level `is_prod XOR eval_run_id` invariant, but not writer-logic identity.
- **Resolution:** unify to ONE writer function both paths call → byte-identical rows by construction. **Schema + reward semantics = EVAL contract; the table is RAG-hosted** (the online bandit reads it for routing); **the CHECK constraint is DB-owned.** ⇒ Tier-3 closure is a **joint TECH + DB gate.**

### Enforcement (TECH's 3 machine checks — the seam made checkable)
1. **ONE-WRITER (RED):** exactly one function may `INSERT INTO rag_query_decisions`.
2. **ONE-IMPORTER (RED):** `check_facts` imported from a single versioned symbol — no forked/inlined copy.
3. **VERSION-PIN:** `FACT_CHECKER_VERSION` stamped on every decision row, both paths.
> "one scorer symbol, one writer symbol, one version stamp."

### Open contract decision (needs EVAL sign-off BEFORE any P2 build)
Per-slot vs per-query routing in the `routing` dict + bandit row. **Lean option (a):** keep the per-query `routing` shape the bandit reads; log per-slot detail in a NEW additive sub-key. Per-slot routing changes `leaf_key`/`feature_vector` semantics = a **telemetry migration, NOT a transparent flag flip** — do not let it drift in silently.

---

## §B · Outcomes gates (EVAL-owned) + measurement method

### The gates (numeric, phased)
| id | phase | gate | threshold |
|---|---|---|---|
| **A** | P1 · day 1 | accuracy (data heal) | forced-arm `oracle_recall` via calibrate.py ≥ 0.58, recovering to 0.60, on the **healed** corpus |
| **B** | P1 · day 1 | instrumentation | pre-route block emits per-step ms; Σ(pre-route ms) + logged retrieval ms == black-box wall clock ±10% |
| **C** | P1 · day 1 | contract byte-compat _(shared w/ TECH)_ | 12-field diff legacy-vs-patched clean; `routing.{feature_vector, scores, leaf_key}` non-null on every non-s response; s rows NULL by design |
| **D** | P1 · day 2 | latency | forced arms a/b/d **p50 AND p95 < 5s** (payer + non-payer, `skip_synthesis`); forced c/d(=a) worst case < 5s |
| **E** | P1 · day 2 | accuracy hold | `oracle_recall` ≥ 0.60 sustained; `router_recall` baseline recorded (do **NOT** gate on 0.65 in the 2-day window) |
| **R** | P2 · pre-flip | refactor gate | shape response passes Gate C byte-diff; `router_recall` ≥ 0.63 trending 0.65 on healed corpus; A/B shows no latency regression → **only then** flip `RAG_ANSWER_ENGINE=shape` |

### Measurement method (so any actor can reproduce a gate)
- Harness `eval/calibrate.py`; bank `eval/queries_cmhc.yaml` (**NOT** `queries.yaml` — 0 golden). Forced modes `a/b/c/d/s` + `natural`.
- **Recall is chunk-level** — `check_facts(query, must_facts, chunks)`, answer-independent (synthesis never gates the chunk set). `correct ≥ 0.67 / partial ≥ 0.34 / wrong`.
- `oracle_recall` = per-query max over forced arms; `union_oracle_proxy` = mean(1 if ANY arm recall ≥ 0.67) — tells us if router 0.65 is routing-reachable (union ≥ ~0.72) or corpus-bound.
- Judge `gemini-2.5-pro` (locked adjudicator). Per-attempt timeout 40s, outer 90s.
- **Caveat baked into the numbers:** forced c/d redirect to a under `skip_synthesis` (corpus_search_agent.py:4405-4410) → c/d cells measure arm a. Read them as "a (redirected)"; compute the union over the DISTINCT real corpus arms **{a, b, s}**, not double-counting a.

### SAFE vs NUMBER-MOVING — the gate on RAG's merges
Every cut is tagged. **RAG cannot merge a NUMBER-MOVING cut until EVAL posts the before/after.**
- **SAFE** (characterization test; no calibration): main.py split · Tier-1 harness extraction · dead-code delete (`_domain_fallback_pool`, the 3 `_derive_*` wrappers, `multi_invoke_considered`) · pure pre-route instrumentation (L0).
- **NUMBER-MOVING** (forced-arm calibration before/after, recall-delta ≥ 0, EVAL posts first): candidate-pool unification · router v1/v2 MERGE · scorer packaging (Tier 2) · cascade / neighbor-expand removal (L6) · **ILIKE pool-scoping (L1-adjacent)** — gated off for forced arms, but it changes `_estimate_internal_recall`'s self-assessment on the natural path → can move `router_recall` withdrawal; measure the natural cell before/after.

---

_Cross-refs: [module schematic](https://claude.ai/code/artifact/5c5eca99-21aa-442e-9a94-8b65bf5daaba) · [live board](https://claude.ai/code/artifact/f61e4b92-a71d-4687-bc32-981cf0cab436) · contract freeze `docs/answer-engine-contract-freeze.md`._
