# RAG Answer-Engine — Target Structure Spec

**Status:** in progress 2026-07-22. Co-authored: **Technical Review agent** (structural/technical gate) + **Eval agent** (outcomes/measurement gate). **RAG agent** implements. This is the pulled-forward Technical Day for RAG (Sunday brought forward because the refactor needs the structural guidelines shaping it from line 1).

**Companion:** `mobius-rag/docs/answer-engine-contract-freeze.md` (the frozen 12-field response contract — must stay byte-compatible). Baseline tag: `answer-engine/baseline-v0`. Flag: `RAG_ANSWER_ENGINE=legacy|shape` (instant flip-back).
**Eval-owned sections (fold in / reference):** `docs/rag-eval-boundary-and-outcomes.md` — §A the 3-tier scorer boundary (maps my 3 machine-checks verbatim) + §B the numeric outcomes gates A–E + R. My byte-compat check implements **Gate C exactly** (12-field clean + `routing.{feature_vector,scores,leaf_key}` non-null on non-s rows, NULL on s-rows — s-aware).

**Distinct corpus arms = {a, b, s}, not a/b/c/d.** Per Eval's measurement (`:4405-4410`), forced c/d redirect to a under `skip_synthesis` — so "fillers a/b/c/d" is imprecise; the real distinct arms the pool/union spans are **{a, b, s}** (c/d = redirects to a). Union/oracle is computed over {a, b, s}, never double-counting a.

---

## 1. Why (the two goals, one root cause)

Two hard goals, 2-day clock:
- **Latency** — forced corpus arms take 10–40s; large untimed DB segment; `c` takes 40s to return 1 chunk.
- **Accuracy** — oracle recall ~0.47 (was ~0.6 pre-corpus-wedge); recover 0.6, then router → 0.65.

**One structural root cause (verified in code 2026-07-22):** strategies a/b/c/d run as **independent, redundant, non-unioning arms** — each re-embeds and re-scans the DB, building its own candidate pool.
- `strategy_c`: 42 DB queries · 6 embeds · 18 candidate-builds
- `strategy_d`: 49 DB queries · 6 embeds · 14 candidate-builds
- `corpus_search_agent` (5.5k LOC): 138 embeds · 84 DB queries · 295 candidate-builds
- No shared pool builder exists.

Independent arms = repeat scans (**latency**) **and** non-union (**accuracy ceiling** — oracle capped at single-best-arm). The same modularization fixes both.

## 1.5 Sequencing — TWO phases (revised per Eval's audit 2026-07-22)

**The 2-day numbers do not come from the rebuild.** Eval's audit scored refactor-first 3/10 vs. surgical+data-first 7.5/10, and the reasoning is sound structurally as well as by measurement:
- **Latency** is fixed by a **surgical punch-list** (§8) — discarded compute, dedup, seq-scan fixes; L5 (memoize the pool across escalation attempts) captures the pool-sharing win *without* the rebuild. Git-revertible, zero contract touch.
- **Accuracy 0.47 → 0.60** is a **corpus/data heal** (the 424-phantom), not code. Union lifts *router_recall toward the oracle ceiling* but **cannot lift the oracle ceiling** — which is corpus-bound. The rebuild's real prize is **0.60 → 0.65 router recall, A/B'd on a healed corpus.**

Therefore:
- **Phase 1 — the 2-day window: surgical latency punch-list (§8) + data heal.** Delivers forced-arm <5s and 0.47→0.60. Low-risk, revertible.
- **Phase 2 — deferred structural sprint (behind the flag): the 7-module rebuild (§2).** Delivers 0.60→0.65. Governed by the same gates (§4), on a healed corpus. **Needs a committed roadmap slot — not "someday."**

**Structural guardrail (Technical Review):** during Phase 1, changes to `corpus_search_agent.py` are **subtractive-only** — remove/fix, add NO new structure to a file slated for the Phase-2 rebuild.

**P2 open contract decision (I track as P2 lead; needs Eval sign-off BEFORE P2 build):** per-slot vs per-query routing in the bandit row. Lean = keep the per-query `routing` shape the bandit reads, log per-slot detail in a NEW additive sub-key. Per-slot routing would change `leaf_key`/`feature_vector` semantics = a **telemetry migration, not a transparent flag flip** — my byte-compat gate would catch it as a diff, but the design must be decided, not drift in. (Detail: `docs/rag-eval-boundary-and-outcomes.md` §A.)

## 2. Target structure (Phase 2) — 7 concern-modules (replacing the corpus_search_* tangle, ~13k LOC)

| Module | Responsibility | Kills |
|---|---|---|
| `pool/candidate_pool` | Build ONE shared candidate pool, ONCE. Vector + keyword + payer-authority feed it. Single embed pass. Every segment timed. | repeat scans (latency) · non-union (accuracy) |
| `shape/answer_shape` | The slot model that drives escalation (AnswerShape). | the a→b→d ladder |
| `fillers/` | a/b/c/d reborn as **pure slot-fillers**: `fill(pool, shape) -> slots`. | arm-owned pools |
| `router/` | ONE router. Picks filler order from shape + features. Owns the bandit decision-row (feature_vector / leaf_key). | v1/v2 duplication |
| `synthesis/` | Reads the filled shape → one synthesis pass. | multi-path synth |
| `contract/envelope` | The frozen 12-field emitter. Every path emits through it. | contract drift |
| `timing/` | Spans on every retrieval/DB segment. | untimed segments |

## 3. Modularization guidelines (what "good structure" is — the technical gate)

1. **One shared pool, built once, fully timed.** No arm builds its own pool.
2. **Fillers are pure over the pool.** A filler may **not** open a DB connection, embed, or build candidates — it only reads the pool. Enforce by signature (no db handle passed in). *This inversion is the whole fix.*
3. **One router, one decision-row.** Delete the v1/v2 duplication.
4. **The 12-field contract is a hard boundary.** One emitter; byte-compatibility is a P0 check.
5. **Every DB/retrieval segment is timed.** Untimed = defect.
6. **No file > ~800 LOC without a boundary reason.** The 5.5k agent splits by *concern* (pool/shape/fillers/router/synth), never by arm.
7. **Forward-only, flag-gated.** Build the shape path behind `RAG_ANSWER_ENGINE=shape`; legacy stays until both gates pass; flip is instant-reversible.

## 4. The two gates (both green before the flag flips)

**Technical/structural gate (Technical Review agent — RED/quarantine = P0):**
- (a) **Contract byte-compat** — 12-field envelope diffed on the eval bank; ANY drift = RED. *Non-negotiable P0 (chat + bandit depend on it).*
- (b) **Single-pool** — no arm opens a DB conn / embeds / builds candidates (structural).
- (c) **One router** — no v1/v2.
- (d) **Every DB + retrieval segment timed — INCLUDING the escalation/answer-path loop** (`agent:3137-3399`, currently untimed — only a global `t0`). *(Retriever re-verify 2026-07-22: pre-route span + leaf-SQL ms are ALREADY emitted; the untimed target is the loop-level orchestration — dtag counts, c/d→a re-runs, union. L0 is partial, not open.)* Untimed loop segment = RED.
- (e) No reintroduced god-file; module boundaries respected.
- (i) **Pool DB access EXPLICITLY DECIDED + timed** (DB gate, folded from §10): the pool-build picks ONE — pool-first (vector/keyword → apply tag `?` on the small pooled id-set) OR GIN-index `chunk_{d,p,j}_tags` (proven 268× on `document_tags`). **Never seq-scan `rag_published_embeddings` (1.94M rows) on a `?` predicate.**
- (f) **ONE-WRITER** — exactly one function may `INSERT INTO rag_query_decisions`. *(Verified 2026-07-22: today there are TWO sites — `corpus_search_agent.py` + `eval/calibrate.py`. Post-refactor a 2nd INSERT site = RED.)*
- (g) **ONE-IMPORTER** — `check_facts` imported only from the single versioned scorer package; a forked/inlined second definition = RED.
- (h) **VERSION-PIN** — `FACT_CHECKER_VERSION` stamped in every decision row on both prod + eval paths (exists today; gated).

*(f)(g)(h) are the structural enforcement of the Tier-2/3 seam in §5.1 — versioning is a convention until a check makes it machine-checkable: one scorer symbol, one writer symbol, one version stamp = "eval-judge == prod-scorer == bandit-reward = one source of truth."*

**Outcomes gate (Eval agent):**
- Forced arm **< 5s**; new-path recall **≥ old → 0.6 → 0.65**; baseline pinned.
- Every **NUMBER-MOVING** module (§7): RAG cannot merge the cut until Eval posts before/after forced-arm calibration with recall-delta ≥ 0.

**Closure is joint:** Technical Review re-runs the structural checks, Eval re-runs the measurement. **If the structural gate can't go green in the 2-day window, the flag does NOT flip — legacy stays. No rushed half-refactor merged.**

## 5. Scope discipline

**On the 2-day critical path:** the engine only — `corpus_search_*` → the 7 modules.

**NOT on the 2-day path (ticketed for the full Technical Day):**
- `main.py` 14k-LOC god-file (149 routes / 8 domains) → decompose into `app/routers/*`. Orthogonal to latency/accuracy.

### 5.1 The RAG/Eval seam — THREE tiers, not one (Eval-owned; verified in code 2026-07-22)

The eval/scorer code in RAG is **not one bucket that "extracts to Eval."** It's three tiers with different physics — the middle one runs in production and **cannot leave RAG's process:**

| Tier | What | Disposition |
|---|---|---|
| **1 — Harness** | `eval/` (calibrate/run/judge orchestration), `routers/eval.py` (1,586 LOC of /api/eval/* + EvalTab), `rag_eval_runs/results` storage | **EXTRACT** to the Eval service (offline orchestration + UI + storage; not on the serving path). |
| **2 — Scorer** | `fact_checker.py` (`check_facts`) + locked judge-model config + `FACT_CHECKER_VERSION` | **STAYS in RAG's process** as an **Eval-owned versioned library**. *(Verified: `check_facts` is `await`ed on the live path in `corpus_search_agent.py` — it IS the bandit's reward. A service hop here would be prod-critical.)* RAG (and Chat) import the pinned version; Eval owns the code + version. |
| **3 — Decision-row writer** | `rag_query_decisions` writer + schema (leaf_key=arm, feature_vector=context, grades=reward) | **ONE versioned writer** (part of the Tier-2 library) called by both prod-observe and offline-eval → byte-identical rows by construction. *(Verified: today TWO writers — `corpus_search_agent.py` + `calibrate.py` — drift risk.)* Table stays RAG-hosted (bandit reads it); schema + reward semantics are an Eval-owned contract. |

**The clean seam = a versioned SCORER CONTRACT:** one package, version-stamped, called identically by prod-observe, offline-eval, and bandit-reward. The boundary is enforced by **versioning** (§4 checks f/g/h), not by which process it runs in. *(Eval owns the detail of this section.)*

## 7. Per-module risk tag — SAFE vs NUMBER-MOVING (the "measure the bug not the change" guard)

Every cut is tagged. **SAFE** = pure code-org, guarded by a characterization test (same input → byte-identical output before/after; no calibration). **NUMBER-MOVING** = changes behavior; MUST run forced-arm calibration before/after and gate on recall-delta ≥ 0, behind the flag. Eval owns the measurement on NUMBER-MOVING; Technical Review owns structural review + closure on all.

| Cut | Tag | Gate |
|---|---|---|
| Split `main.py` → routers | SAFE | characterization test |
| Extract Tier-1 harness out of RAG | SAFE | characterization test |
| ~~Delete the dead router~~ **← CORRECTED: no dead router exists** | — | v2 imports v1 (`corpus_search_router_v2.py:24`); v1 is the prod default *and* v2's base. Neither is deletable. |
| **Router consolidation (v1 vs v2)** | **NUMBER-MOVING · HIGH** | **Serving router determined (2026-07-22):** selection = `ROUTER_VERSION=="v2"`; **default unset → v1 serves**; v2 is a layer on top of v1. Consolidation is a MERGE, not a delete. **Blocker: confirm the deployed prod `ROUTER_VERSION` (deploy-config, RAG/DB) before any merge** → then baseline both → calibrate before/after. |
| **Candidate-pool unification (core)** | **NUMBER-MOVING** | new-path per-arm recall ≥ old, behind flag (the intended change) |
| **Scorer packaging (Tier 2)** | **NUMBER-MOVING** | scorer characterization test: fixed (query, must_facts, chunks) → identical scores old/new at same `FACT_CHECKER_VERSION` |
| **Cascade / neighbor-expand removal** | **NUMBER-MOVING** | measure — removing a redundant scan can drop recall-contributing chunks |

The engine refactor must keep `fact_checker`'s contract intact throughout.

## 6. Run order (pulled-forward Technical Day for RAG)

1. **AUTO baseline now** — Technical Review snapshots current structure (god-file, dup router, untimed segments, 12-field contract shape); Eval pins the measurement baseline.
2. **Refactor builds against both gates from line 1** — these guidelines shape scope, not review-after.
3. **Flip gate** — structural GREEN + outcomes GREEN → flag flips to `shape`.
4. Eval folds this + the code audit into a file-level 2-day scoped plan; Technical Review + Eval brief RAG together.

## 8. Phase-1 latency punch-list (Eval audit, file:line — surgical, git-revertible, zero contract touch)

| # | Fix | Location | Tag |
|---|---|---|---|
| L0 | Add ms-timing to the pre-route block (the untimed segment — today only `logger.info`) | `corpus_search_agent.py:3931-3963` | SAFE |
| L1 | Gate `_estimate_internal_recall` OFF when `explicit_strategy` set — override at :4076-4079 never reads its self_assessments, so ~7 seq-scans (incl. leading-wildcard ILIKE :1598-1607) are computed then DISCARDED on every forced arm | call site `:3955` | **NUMBER-MOVING** — forced arms discard it (safe), but ILIKE pool-scoping changes `_estimate_internal_recall`'s natural-path self-assessment → can move `router_recall` withdrawal. **Eval posts before/after on the NATURAL cell**, not just a characterization test. |
| L2 | Dedup double AHCA fetch — `_doc_ids_with_tag(_AHCA_TAG)` fires at both :1822 and :1836 | `:1822 / :1836` | SAFE |
| L3 | `asyncio.gather` the serial per-tag loop | `:1768-1775` | SAFE |
| L5 | Memoize partition_pre/pool_pre across escalation attempts (`:3091` re-enters up to `_MAX_TRIES=4`, rebuilds pool each time) | `:3091` | **NUMBER-MOVING** (pool reuse can shift chunks — measure) |
| L6 | c=40s case: forced-c/d→a redirect runs BM25 k-of-n + strict→relaxed FULL re-run over ~2052-doc AHCA pool; raise the ≤20-doc short-circuit | `:4405-4410` · `corpus_search.py:1244-1254` | **NUMBER-MOVING** |
| L7 | `document_id::text = ANY(CAST(:ids AS text[]))` seq-scan anti-pattern — cast PARAM to `uuid[]` per repo rule at :540-550 | `corpus_search.py:2662-2694` | SAFE |
| — | SAFE-DELETE: `_domain_fallback_pool` (:1990, no callers) · collapse 3 wrappers (:992/1005/1063) · multi_invoke debug dict (:4155-4174, verify not read by bandit) | — | SAFE (characterization test) |

## 9. MUST-PRESERVE — the frozen contract / bandit surface (Technical Review byte-compat gate enforces this)

- **`routing_dump`** built once at `:4111-4141`, threaded to 8 return sites — ONE clean projection point. Byte-compat diff anchors here.
- **`_observe_async` INSERT** `:3539-3566` — `leaf_key :3515`, `feature_vector :3519`, `scores :3520` must stay non-NULL for non-s rows (a shape-loop regression here = db8f597-class silent bandit break).
- **`_persist_routing_decision_async`** `:3363-3416`; `_with_chain :3130-3139`; strategy_used/invoke_all/strategy_chain accumulation `:3122-3168`.
- **CONTRACT EDGE:** s-rows write **NULL `feature_vector` BY DESIGN** (`:3842-3888`) — the shape loop must NOT fabricate feature vectors for s (that's s-contamination at the data layer).

## 6. Run order

**Phase 1 (2-day):** AUTO structural baseline (Technical Review) + measurement baseline (Eval) → surgical punch-list §8 + data heal, each item gated SAFE (characterization test) or NUMBER-MOVING (Eval before/after) → forced-arm <5s + oracle 0.47→0.60.
**Phase 2 (deferred, committed slot):** the 7-module rebuild §2 behind the flag, on a healed corpus → router 0.60→0.65. Flip gate = structural GREEN (§4) + outcomes GREEN. If not green, legacy stays.

*Audit landed 2026-07-22 — §8/§9 are the real file:line map. Signoff artifact (RAG+Eval+Tech, Ananth veto) owned by Eval; DB agent added for the data layer (decision-row schema, pool DB-query perf, migrations).*

## 10. Alignment-board lens conditions (governance sign-offs → the contract)

The Platform Architects reviewed the future-state through their lenses (`reports/techday/retriever-alignment-board.html`). Each returned **conditional green**; these conditions are now part of the contract Retriever builds against.

### UX / experience (conditional ✓)
- **Field coverage:** the 12-field envelope MUST carry the 9 fields the Chat surface binds to — `strategy · outcome · s_top · s_avg · chunks_retrieved · source_types[] · grounding_badge · cited_source_indices[] · query_decision_id`. Confirm coverage against the freeze doc, or map where each originates.
- **Grounding-badge seam — RULING: Retriever derives it (Option A).** The `contract` module computes the badge from `s_top + source_types + outcome`; Chat reads it verbatim. Retrieval semantics live in the module with retrieval context — Chat does not re-derive.

### DB / data-layer (conditional ✓)
1. **Pool DB access — DECIDE GIN-vs-pool-first explicitly + time it.** The pool-build hits `rag_published_embeddings` (1.94M rows) and `chunk_{d,p,j}_tags ? :tag_code` with **NO GIN** on those jsonb cols. Either (a) vector/keyword-first → apply tag `?` on the small pooled set (pool-first), OR (b) GIN-index the tag cols (proven 268× on `document_tags`). **Never seq-scan 1.94M on `?`.** Gate (d) times it.
2. **Decision-row (Tier-3) — one writer + populate-everything.** The single writer MUST populate `feature_vector` + `strategy_scores` (were silently NULL → db8f597; a regression blinds the bandit), stamp `corpus_version` from the cached read (never compute-at-query), emit deterministic `leaf_key`, and write fire-and-forget + idempotent (`ON CONFLICT DO NOTHING`). `rqd_prod_not_eval` enforces prod/eval split.
3. **Access-contract carryover:** shared pool never per-call connects; the `idle_in_transaction_session_timeout=120s` guardrail stays (the leak that blocked payor); cross-service pushes persist to shared DB/Redis, never in-memory turn state.
- **SCOPE FLAG:** externalizing the in-process job-state (→ `max>1` horizontal scale) is a **SEPARATE follow-on**, NOT delivered by the 7-module cut. The refactor *enables* scale; it doesn't ship it. Don't let anyone flip `max>1` assuming the rebuild handled it.
- DB endorses gate (d) timing-on-every-segment as the highest-value gate — **untimed = RED, non-negotiable.**

### Product-Awareness / product-promise (conditional ✓) — 3 SAFE characterization checks
Byte-compat freezes the *shape*, not the *grounding semantics* — an answer can pass byte-compat while quietly becoming less-grounded/more-confident-but-uncited. Add these SAFE checks:
1. **Grounding fidelity:** `llm_answer`'s claims trace to `chunks` (answer ⊆ evidence); synthesis grounds in the pool, never fabricates beyond it.
2. **Honest-gap terminal:** shape escalation can END in an honest `gap` (unfilled slots → gap outcome); never force a confident fill when documents don't support it.
3. **Status/provenance passthrough:** chunk `status` (planned/live) + `source_type` survive pool→shape→synthesis→contract, so reality-gating + the provenance badge still work.

*Full green on each lens pending: Retriever's current-state column filled + these conditions reflected in §4/§7.*

### Eval / outcomes (SIGNED — scope aligned; 4 verify-at-build conditions)
1. **Latency-under-load is coupled to DB's externalized-job-state.** The pool module kills per-query cost; the under-load/single-core saturation only clears when `max=1` in-process state is externalized → `max>1`. The under-load gate needs BOTH — the pool module alone does not clear it.
2. **Recall 0.65 is the MECHANISM, not a guaranteed number.** Union-over-one-pool is the lever, but 0.65 is only reachable if the healed corpus has complementary chunks to union (`union_oracle_proxy` was 0.35 pre-heal). Eval certifies structure + measures; a corpus-bound ceiling below 0.65 is a corpus/tagging gap, not the refactor's miss.
3. **Routing decision must resolve BEFORE the router builds** (below).
4. SAFE/NUMBER-MOVING tags finalized once the current-state column is filled (delivered — `docs/rag-agents/retriever-current-state.md`).
- **Process:** Eval's sign-off is scope→outcomes ALIGNMENT; outcome VERIFICATION is per-cut DURING build (SAFE→characterization, NUMBER-MOVING→before/after), behind `RAG_ANSWER_ENGINE=legacy|shape`. Build can proceed behind the flag once scope is aligned.

### Master RAG / functionality (conditional ✓) — one critical acceptance criterion
- **The `shape` module's acceptance criteria MUST explicitly forbid fabricating `feature_vector` for s-rows.** The new shape loop is the highest-risk silent regression: a loop that populates `feature_vector` for s-rows would corrupt the bandit **without tripping the 12-field byte-compat check** (s-row NULL is emergent from the null-guard, not an explicit branch — see current-state). This constraint lives in the shape module's acceptance, not assumed by the contract module. *(Verify-first note: Retriever confirmed s-row NULL is EMERGENT from null-guards `:3586/:3632`, not an explicit s-branch — a fragile edge to preserve deliberately in the rebuild.)*

### The open routing decision (P2 lead + Eval sign-off, BEFORE the router module builds)
Per-slot vs per-query routing in the `routing` dict + decision row. **Proposed: Option (a)** — keep the per-query `routing` shape the bandit reads; log per-slot detail in a NEW additive sub-field. Back-compatible, bandit unchanged, not a telemetry migration. **Needs Eval's explicit sign-off before the router module changes the row shape** (per-slot semantics changing `leaf_key`/`feature_vector` = db8f597-class silent bandit break).

### ⚠️ Spec-anchor drift (verify-first, Retriever 2026-07-22)
The §8/§9 line anchors have DRIFTED — **`docs/rag-agents/retriever-current-state.md` is the authoritative current-state map** (re-verified in live code). Corrections: `routing_dump` @ `:4200-4263` (not :4111); INSERT `rag_query_decisions` @ `:3606`; c/d→a redirect @ `:4494` (not :4405); s-row NULL emergent @ null-guards `:3586/:3632`; **L0 "untimed pre-route" appears ALREADY LANDED** (pre-route now timed `:4005-4036`) — recheck before carrying L0 open. `_domain_fallback_pool :2040` confirmed DEAD.
