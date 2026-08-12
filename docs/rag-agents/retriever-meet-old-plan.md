# Retriever — Meet-Old Plan (LIVE design doc)

**Status:** LIVE / in progress — paired design (Ananth × Retriever). **Steps 1–2 detailed; 3–7 pending.**
**Method:** *meet-old first* — assemble the new structure so it is **byte-identical to legacy** on the cmhc bank behind `RAG_ANSWER_ENGINE=shape` (instant-revertible), **then exceed** (each enhancement an Eval-gated NUMBER-MOVING change on a proven structure).
**Process:** build the **entire chain** first, then **one-pass signoff** (TECH + Eval + DB + Master RAG). No piecemeal gating of a moving design.
**Companions:** `retriever-current-state.md` (verified current map) · `module-map.md` · `module-sequence.md` / `module-gates.md` (architect gates — see order correction below) · `curated-chunk-contract.md` (Curation seam).

**Tags used below:** `[refactor]` clean lift from current code · `[stub]` identity/passthrough for net-new, meet-old · `[⋯exceed]` deferred enhancement · `[P0]` ship-gate.

---

## The chain (whole shape)

```
intent/SHAPE → POOL → ROUTER → FILLERS → SYNTHESIS → (OBSERVE ↺) → CONTRACT     [TIMING cross-cut]
   reason        act     reason    act        observe/act        observe          emit
```

- **reason → act → observe is a loop**, not a line. The escalation loop wraps POOL→FILLERS→SYNTHESIS (≤ `_MAX_TRIES=4`); shape plans once and re-drives each attempt.
- **Order correction to `module-sequence.md`/`module-gates.md` (must land in the one-pass signoff):** the gate docs have *fillers → router*. Correct order is **ROUTER (select strategy) → FILLERS (execute strategy)** — it matches today's code (`pool_pre :4008` → features → `router_decide :4161` → arm executes) **and** keeps routing **per-query byte-identical** (the gate doc's "rank filled slots" is *per-slot* = a telemetry migration we are NOT doing in meet-old).
- Meet-old reproduces today's primary path (route-to-one + escalate). The **fill-all-then-union** (oracle-recall) pattern is `[⋯exceed]`.

---

## Step 1 — SHAPE (the reason phase) = gate → reformat → structure

All three sub-phases run **before any retrieval**. Shape is cheap; the full reformat runs **only on "proceed."** Shape = step 1 (no separate 8th module).

### (a) Gate — "can / should we answer?"
- A **cheap normalize** precedes the gate (needed to cache-lookup / coverage-check).
- Classifies intent + **confidence = J/P/D tag completeness + selectivity** (grounded, not hand-wavy), sets overlay flags, picks the aperture.
- **A cheap PRIOR, not a verdict** — pool/observe can revise it (predicted-exact but empty pool → honest-gap). Corpus-gap in particular is *predicted* here, *confirmed* at pool/observe.
- Three underlying questions: **can I understand it? · should I retrieve at all? · can I answer it (already)?** — three genuinely different failures that today collapse into one mushy response.

**Contour taxonomy** (by response posture):

| Posture | Contour | Behavior | Tag |
|---|---|---|---|
| **Answer** | Exact | clear + servable → fast, precise, lean path | `[refactor]` |
| **Clarify (aperture)** | Vicinity | right area, fuzzy intent → offer options | `[⋯exceed]` +Chat |
| | Underspecified | clear intent, missing slot → "which payer/state?" | `[⋯exceed]` +Chat |
| **Short-circuit** (no retrieval) | Repeat / cached | answered before → serve from cache | `[⋯exceed]` wire cache |
| | Corpus-gap | in-scope, no content → honest gap + log for sourcing | `[refactor+]` |
| | Out-of-scope | not our domain → decline / redirect | `[refactor]` |
| | Unclear | can't parse → fast exit | `[refactor]` |
| | **Duplicate re-invoke** | chat re-invoked, no significant rewrite → "same query" loop-guard | `[refactor]` `_query_signature :3174` (internal today → lift to chat↔RAG boundary) |
| **Redirect** (not a retrieval Q) | Action / command | "file the appeal" → tool/skill (task, interact) | `[refactor]` `redirect :439` |
| | Social / meta | "hi", "what can you do" → s path / product-help | `[refactor]` `s :3929` |
| | Feedback | "that was wrong" → feedback agent | `[refactor]` |

**Overlay flags (ride any branch):**
- 🔒 **PHI / sensitive — `[P0]`** — HIPAA gate, fail-closed, mask evidence; **wire the existing classifier** (fires on *any* contour, even out-of-scope/social).
- ⧉ **Multi-intent** — compound question → hand sub-questions to shape decompose `[⋯exceed]`.
- ⏱ **Freshness** — "current/latest" → prefer freshest source, flag staleness.

**Duplicate-reinvoke caveat:** must NOT block *intentional* retries ("regenerate"/"try again" = same signature, but the user wants a fresh attempt). Chat must pass the **re-invoke reason** (auto-loop vs deliberate retry). Needs a conversation-scoped recent-signature store in a **shared** store (not in-process — separate calls), keyed by `conversation_id`, + a `same_query` response-mode.

### (b) Reformat — "how do we translate to answer best?" (the tricky piece)
- Maps the query onto **J/P/D tag slots**; **tag-completeness drives the posture**:
  - **All slots clear + selective → PRECISE** — one strict query.
  - **Partial (answerable) → FAN-OUT** — expand the missing/ambiguous axis: **bounded** (top-K plausible tag-fills × top-M domain aspects) → `rewritten_queries[]`.
  - **None → UNCLEAR** — nothing to reformat onto → exit.
- Example: *"eligibility for medicaid"* → `P:medicaid ✓ · D:eligibility ✓ · J:state ?` → fan out states × aspects (income / categorical / process) → explore.
- **Explore-before-clarify:** for answerable-but-underspecified, fan out + explore *first*; clarify only if results **diverge**. Two clarify triggers:
  - *gate-time* — can't even form a fan-out → ask up front.
  - *observe-time* — explored, results genuinely split by the missing axis → **informed** aperture ("depends on your state — FL vs TX"), which beats a blind "which state?".
- **Meet-old primitive:** the strict→relaxed **k-of-n tag cascade** (`_run_with_kofn_cascade :1225`, strict→relaxed `:1338/:1348`) already tightens/relaxes on tag under-fill. Full multi-query fan-out + observe-time converge/clarify = `[⋯exceed]`.
- **Also the per-attempt reformulate site** — on escalation, shape re-fires (b) with retry context (= shape.escalate).

> **Fan-out width = one knob across three modules.** Reformat *sets* N, pool *pays* N× (parallel builds), observe *reaps* convergence. Bounded + Eval-tuned. **reformat width = pool cost = the recall/latency tradeoff.**

### (c) Structure — "set up for downstream"
Emits the single contract the rest of the chain reads:
- `rewritten_queries[]` · `answer_shape` + slots · **scope/auth context** (which of the 4 pool sources this user may see) · flags (PHI/freshness/scope) · posture (exact→lean). `[refactor]` (request-shape exists).

---

## Step 2 — POOL (the act/gather phase) — the single recall authority

Guarantee: **"not in any of your scoped sources (match ∪ neighbors) ⇒ nowhere."** Everything after pool is pure selection over what pool produced.

### Two tiers
| Tier | What | Anchor | Notes |
|---|---|---|---|
| **① Match pool** | big-K **union** of {bm25 + vector + inheritance} — the recall ceiling | `build_candidate_pool :1762` · `_bm25_arm :806` | `[refactor]` |
| **② Neighbor sub-pool** | positional siblings around each match (±2 para / ±1 page), `is_neighbor=True` + `_neighbor_text` | `_expand_with_neighbors() :3079` (corpus_search.py) — **STALE ANCHOR CORRECTED 2026-07-23 by Pool agent**: this doc previously cited `_fetch_sibling_chunks_batch :2560`, which no longer exists at that name/location. `_fetch_sibling_chunks_batch()` is still present but nested, called from `_expand_with_neighbors()`, not a top-level anchor itself. | `[refactor]` — **NUMBER-MOVING**, reproduce window exactly |

**Output split (keeps ranking clean):** **matches** drive routing + ranking (which chunk answers); **neighbors** attach as synthesis context (complete the answer). `_expand_with_neighbors()` dedupes siblings against seeds by both `id` AND content (`content_sha`/normalized-body prefix), inherits a fractional score from the nearest same-doc seed, and applies caps — this supersedes the stale `is_promoted_neighbor :2210`/`_NEIGHBOR_SCORE_FLOOR :2553` citations below (verify current behavior against `_expand_with_neighbors()` directly, not these line numbers). Both tiers are **DB ops** → they belong in pool, not the pure-over-pool fillers.

### Four sources (federated — same engine per source)
| Source | Scope | Backing | Status |
|---|---|---|---|
| **PUBLIC** | global | `rag_published_embeddings` (1.94M) | **BUILD NOW** `[refactor]` |
| **ORG** | org-tenant | `mobius_org_docs` | `[⋯exceed]` reflect |
| **INSTANT-RAG** | user-private + PHI | uploads / Vault | `[⋯exceed]` reflect |
| **CACHE** | scoped · prior *answers* | `mobius_cache` | `[⋯exceed]` reflect (may short-circuit, not union) |

- **Source-adapter seam:** pool talks to a `SourceAdapter` interface; **public = adapter #1**. Each adapter owns `{bm25 + vector + inheritance + neighbors}` for its section under a scope/auth context. Meet-old public build goes *through* the seam (not hardcoded to `rag_published_embeddings`) so org/instant/cache slot in later without touching pool core. **Designing the seam now is ~free; retrofitting is the security-hole path.**
- **Scope guard `[P0]`:** federate, **never leak** — scope/auth rides every adapter; public=global, org=tenant, instant-RAG=user+PHI; **no global fallback**.

### Pool build workflow (meet-old) — search + rerank + neighbors

Pool runs **once per rewritten_query**. For each of the N queries from shape, pool executes:

#### Phase 1: SEARCH (strict → relaxed fallback)
Both a (BM25) and b (vector) follow this pattern:

**Strategy a (BM25):**
- Search `rag_published_fts_gin` (tsvector) with ts_rank_cd
- **Strict:** within `pool.document_ids` (J/P/D tag match from shape)
- **Fallback (if strict under-fills):** expand to full corpus via `_run_with_kofn_cascade :1225`
- **Result:** chunk_ids + ts_rank_cd scores
- Anchor: `_bm25_arm() :806`, strict `:3347`, relaxed `:3417`

**Strategy b (vector):**
- Embed query (1536-d) via `embed_with_cache() :456`
- Search `rag_published_embeddings_vec_hnsw` (HNSW cosine) over `embedding_vec`
- **Strict:** within `pool.document_ids` (J/P/D tag match)
- **Fallback (if strict under-fills):** expand to full corpus via k-of-n `:1225`
- **Result:** chunk_ids + cosine similarity scores
- Anchor: vector arm `:562`

#### Phase 2: RERANK (tag-coverage + threshold filter — shared a/b)
- Normalize scores (both to 0–1)
- Apply `_TAG_COVERAGE_FLOOR` `:2553` — chunks with complete J/P/D tags score higher
- Flag `is_promoted_neighbor` `:2210` — **anchor stale, see §"Two tiers" correction above; verify against live `_expand_with_neighbors()` instead**
- Filter & order: keep only ≥ threshold, sort descending
- **Result:** ranked chunk_ids + scores + is_neighbor flags

#### Phase 3: ASSEMBLE_NEIGHBORS (±2 para / ±1 page context)
- For each match: fetch ±2 paragraph + ±1 page context
- Create `_neighbor_text` field (full neighborhood for synthesis)
- Mark siblings as `is_neighbor=True`
- Anchor: `_expand_with_neighbors() :3079` (corpus_search.py) — corrected 2026-07-23, was stale `_fetch_sibling_chunks_batch() :2560`
- **Result:** one pool per query, ready to consume

**Pool output per rewritten_query:**
```python
{
  "pool_result": [
    {
      "chunk_id": "chunk_001",
      "is_neighbor": False,  # match
      "score": 0.82,
      "_neighbor_text": "...context...",
      "tags": {...}
    },
    {
      "chunk_id": "chunk_000",
      "is_neighbor": True,   # sibling
      "score": None,
      "_neighbor_text": None
    },
    ...
  ],
  "metadata": {
    "strategy_hint": "a" or "b",  # which search worked best
    "match_count": 145,
    "rerank_count": 23,
    "fallback_triggered": False
  }
}
```

### Verified pool facts (DB + code)
- `rag_published_embeddings` 1.94M rows · 0 NULL vecs · HNSW (`rag_published_embeddings_vec_hnsw`) + FTS-GIN (`rag_published_fts_gin`) healthy.
- ⚠️ `chunk_{d,p,j}_tags` have **NO GIN** → the `?` predicate seq-scans 1.94M (so the tag-IDF/selectivity signal is a seq-scan today). §10 future decision: **pool-first vs GIN** (DB gates, must be timed).
- Match "double-build" = arm-level strict→relaxed `_bm25_arm` (`:3347→:3417`), a conditional 2nd keyword fetch (not two pool builds). Agent single-build per call (`pool_pre` reused `:4784`); **rebuilt across escalation attempts** (loop re-invokes impl, no pool threaded) = spec L5 (real but rare). Meet-old preserves per-attempt rebuild; L5 memo = `[⋯exceed]`.

---

## Meet-old vs Exceed — the split at a glance
- **Meet-old (build now):** intent gate (classify/redirect/s/dup-guard), reformat via k-of-n strict→relaxed, structure contract, pool public (match+neighbors, per-attempt rebuild), route-to-one + escalate. Byte-identical to legacy on cmhc.
- **Exceed (Eval-gated, later):** real query decomposition (multi-intent), clarify apertures (vicinity/underspecified), cache serve, org/instant/cache pool adapters, fan-out + observe-time clarify, union/oracle fill-all, L5 memo, GIN, per-slot routing.

## Final Decisions (v1 feedback round, all blockers resolved)

**Locked by Eval + Master RAG + TECH + DB (2026-07-22):**

1. **Confidence threshold:** `0.50` global, per-query, Eval-gated (tunable via forced calibration)
   - Gate: measure cmhc 22-query baseline; if precision drops >5%, raise to 0.55
   - Config: `synthesis_confidence_threshold: 0.50`

2. **Two-writer collapse on rag_query_decisions:** Option B (ID pre-allocation)
   - Eval creates `decision_id` (UUID), passes to agent
   - Agent receives and INSERTs with provided ID (no uuid.uuid4() in agent)
   - Schema: add optional junction table `eval_run_decisions(eval_run_id, decision_id)`
   - Code review gate: verify agent has ZERO uuid.uuid4() calls

3. **Pool fallback threshold:** `_MIN_STRICT_RESULTS = 5`
   - Cascade triggers if strict results < 5 (adaptive balance vs seq-scan cost)
   - Test matrix: {0→cascade, 1→no, 4→cascade, 5→no, 6→no}
   - Flag: `# TAG: pool-fallback-threshold` at cascade trigger

4. **Observe neighbor + NULL-tag handling:**
   - Skip neighbors during cross-lens validation (context scaffolding, not results)
   - NULL-tag policy: "neutral" (skip validation, measure frequency)
   - If >5% NULL tags → escalate to "strict" policy
   - Code: `for chunk in pool: if chunk.is_neighbor: continue`

5. **Escalation order:** Follow linear formula ranking (alternative_scores)
   - `escalate_to = sort(alternative_scores, descending=True)[1]` (next-best)
   - Deterministic per-query, testable, leverages router model
   - Validation: on held-out escalations, confirm rank order matches performance

6. **Multi-intent handling:** Fail-fast, defer to planner
   - Gate detects multi-intent → return "one question at a time" response
   - File task: planner must emit `multi_intent=True` + decomposed sub-queries before Retriever
   - Retriever blocks on planner task

7. **Empty pool + synthesis:** Fail-close, structured escalation
   - All strategies {a,b,c,d,s} return empty + gate.corpus_gap=True → "no information available"
   - Return escalation options (rephrase, support, payor link)
   - Log corpus_gap_for_content_team (area_tags=["retriever", "corpus"])
   - No freeform synthesis when pool={}

---

## Open items for the ONE-PASS signoff (cross-agent)
1. **Response-mode set** in the 12-field contract: `{answer, clarify, decline, redirect, cached, same_query}` — **Chat** renders/handles; **Master RAG** owns business-logic preservation. *(Byte-compat P0: new modes must be additive.)*
2. **Order correction** fillers↔router → **TECH + Master RAG** amend `module-sequence.md`/`module-gates.md`.
3. **PHI gate** wiring at the intent gate — **PHI Classifier agent** (fail-closed contract).
4. **Source adapters** (org / instant-rag / cache) — **Org / Instant-RAG / Cache** agents; scope/auth interface.
5. **Curated-chunk seam** (pool input) — **Curation**; tag JSONB shape pinned (object keyed by tag_code; value = bare int count; `[⋯exceed]` per-chunk match strength).
6. **Chat↔RAG handshake** for duplicate-reinvoke (`conversation_id` + re-invoke reason) — **Chat**.

## Step 2b — ROUTER (the decide phase) — N strategy decisions, one per rewritten query

After POOL and SHAPE, router runs **N times in parallel** (once per rewritten_query) — each selects ONE strategy from the meet-old set {a, b, c, d, s}.

### Meet-old strategy set (N choices per query)
| Strategy | Mode | Anchor | Notes |
|---|---|---|---|
| **a** | corpus BM25 (specific, fast) | `:806` | `[refactor]` |
| **b** | corpus vector (narrow, semantic) | `:562` | `[refactor]` |
| **c** | LLM synthesis (general fallback) | `:2673` | `[refactor]` answers anything |
| **d** | Google search (general fallback) | `:4633` | `[refactor]` answers anything |
| **s** | cached answer (payor platform API) | `:3929` | `[refactor]` pre-route short-circuit |

**Future strategies (exceed, deferred):** e (delegate to tool), u (external redirect), others. Not in meet-old linear formula.

### Two decision modes (same as today, frozen in meet-old)

#### Mode 1: Forced (calibration, offline — Eval only)
- **Trigger:** `explicit_strategy` set via Eval override
- **Path:** `decide_override() :4166` → forces strategy {a,b,c,d,s}
- **Purpose:** Eval calibration — force each strategy in turn, measure outcomes (recall, latency, converge/diverge/empty rates), derive **priors** (initial weights for linear formula)
- **Output:** one decision-row per forced run

#### Mode 2: Linear (production, meet-old — frozen weights)
- **Trigger:** normal queries (no explicit_strategy override)
- **Path:** `_router_decide_v1() :4161` → linear formula
  ```
  score_a = features · weights_a
  score_b = features · weights_b
  score_c = features · weights_c
  score_d = features · weights_d
  score_s = features · weights_s
  
  chosen_strategy = argmax(scores)
  ```
- **Features:** query complexity, tag completeness, pool match_count, strategy affinity (corpus-native vs fallback)
- **Weights:** **frozen at meet-old** (derived from calibration baseline `:4161` `_LINEAR_WEIGHTS`)
- **Output:** one decision-row per query (chosen strategy + all scores + confidence)

### Decision-row logging (one-writer, meet-old)
- **Inserted at:** `:3606` (one INSERT site)
- **Schema:** `{query_id, attempt, chosen_strategy, alternative_scores[], feature_vector, latency_ms}`
- **s-row edge:** if strategy=s, `feature_vector` NULL by design (no features scored for cache strategy)
- **One-writer guarantee:** all N decision-rows from one request written by single INSERT → scales to N rows

### Observe outcomes (post-filler, loop control)
After fillers executes the chosen strategy:
- **Converge** — got a meaningful answer → exit loop, move to synthesis
- **Diverge** — N queries split on missing axis → inform aperture (observe-time clarify)
- **Empty** — strategy returned nothing → escalate or rerun (if budget)
- **Escalate** — answer needs human judgment → log task

### Bandit feedback loop (exceed, deferred)
- **Trigger:** post-observe, after outcome is known
- **Input:** decision-row (feature_vector + scores) + observed outcome (converge/diverge/empty/escalate)
- **Output:** reward signal (e.g., converge=+1, empty=-1)
- **Update:** feed reward back to **weight optimizer** → derive new weights
- **Scale:** includes new strategies {e, u} and others
- **Gate:** Eval re-calibrates, NUMBER-MOVING validation before deployment
- **Status:** `[⋯exceed]`, out of scope for meet-old

## Step 4 — FILLERS + OBSERVE (the act/check pair) — execute and score, loop on rerun

Fillers executes the router-selected strategy per query (in parallel). Each strategy has its own core flow. All converge into observe, which checks the outcome and decides to converge/diverge/empty/escalate or rerun (next attempt).

### Seven strategy flows (each funnels to observe)
| Strategy | Flow steps | Implementation notes |
|---|---|---|
| **a** (BM25) | search (BM25) → rerank → assemble neighbors | pure corpus, `[refactor]` |
| **b** (vector) | search (vector) → rerank → assemble neighbors | pure corpus, `[refactor]` |
| **c** (LLM) | create prompt → LLM choice (fast/thinking) → get answer | grounded or general, `[refactor]` |
| **d** (Google) | formulate query → call Google API → parse results | external, `[refactor]` |
| **e** (delegate) | check if MCP server needed → recommend to Chat | no invoke unless required; Chat handles as recommendation, `[⋯exceed]` or pass-to-chat |
| **s** (cache) | call payor-platform agent API → return cached answer | `mobius_cache` backed by Payor Platform, `[refactor]` |
| **u** (redirect) | reformat to sitemap concepts → investigate sitemap, retrieve link | two-step: normalize + lookup, `[refactor]` |

### Observe (validate per-strategy via cross-lens) — generates confidence score

After each filler executes, observe **validates the result through a different lens** per strategy. This cross-validation builds **confidence** in the answer.

#### Observe a (BM25 validates via vector cross-check)
- **Questions:**
  1. Did we get enough data? (match_count ≥ threshold?)
  2. What's the strength of reweighted scores? (tag_completeness_bonus applied? scores ≥ threshold?)
  3. **Cross-lens:** does the result also match via vector embedding to the query? (semantic coherence)
- **Output:** confidence_score (a + vector validation lens)

#### Observe b (vector validates via J/P/D cross-check)
- **Questions:**
  1. Did we get enough data? (match_count ≥ threshold?)
  2. What's the strength of scores? (vector cosine ≥ threshold?)
  3. **Cross-lens:** do the results match via J/P/D tags from the query? (domain language coherence)
- **Output:** confidence_score (b + tag validation lens)

#### Observe c & d (LLM/web validates via multi-lens)
- **Questions:**
  1. Authenticity: is the website/citation reliable? (domain reputation check)
  2. **Vector lens:** do the responses semantically match the query? (embedding distance check)
  3. **Tag lens:** do the responses use J/P/D domain language? (tag presence in text)
- **Output:** confidence_score (c/d + vector + tag lenses)

#### Observe s (cache validates via tag + vector)
- **Questions:**
  1. Is the cached answer still fresh? (age check)
  2. **Vector lens:** does cached answer still match current query embedding? (semantic drift)
  3. **Tag lens:** do cached answer tags match current query J/P/D context? (domain shift)
- **Output:** confidence_score (s + vector + tag validation)

### Loop control (confidence-driven)
After observe generates confidence_score:
- **Converge** (high confidence) — sufficient data, validated via cross-lens → exit loop, proceed to synthesis
- **Empty** (no data) — filler returned nothing → escalate or rerun with next strategy (if budget)
- **Low confidence** (weak validation) — data exists but cross-lens validation weak → rerun same strategy or next attempt
- **Diverge** (N queries split on axis) — different rewritten queries diverge (e.g., state-specific) → inform aperture

## Step 5 — SYNTHESIS (compose + decide reroute, post-loop) — one pass after loop converges

Synthesis runs **once, after loop converges with converged + confidence-validated results**. Decides: synthesize answer, reroute (rerun attempt), or escalate.

**Input:** 
- converged fillers result(s) (from step 3/4 loop)
- confidence_score(s) from observe (per-strategy validation)
- N rewritten queries + results

**Logic:**
1. **Check confidence:** are the results confidence-strong enough to synthesize? (observe cross-lenses validated them?)
   - **High confidence:** proceed to synthesize
   - **Low confidence:** signal reroute (rerun escalation attempt with different strategy)
   - **Diverge:** N queries split → need clarify aperture (inform chat)

2. **If synthesizing:** compose final answer
   - Ground answer in pool chunks (verify grounding ⊆ pool via `check_facts` Tier-2 scorer)
   - Include thinking trace (which strategy, which chunks, why)
   - Mark grounding confidence (high/medium/low per chunk)

3. **If not synthesizing:** return control to escalation loop
   - Attempt counter increment
   - Next strategy picked (if budget remaining)
   - Loop re-runs (steps 3–4 again)

**Output (if synthesizing):**
- answer_text (grounded in pool)
- thinking_trace (reasoning, strategy used, confidence)
- grounding_markers (chunks used, confidence per chunk)
- finalize attempt_count (how many loop iterations)

**Output (if rerouting):**
- decision = "REROUTE" (escalation loop takes over)
- reason = "low_confidence" or "diverge"

- `[refactor]` existing `_synthesize_internal_answer :2673`
- Tier-2 scorer (check_facts) **untouched**

## Step 6 — CONTRACT (emit, post-synthesis) — one 12-field response envelope, byte-compat P0

One emitter for all code paths. Frozen schema, no field order changes.

**Input:**
- converged filler result(s) (from steps 3–4 loop)
- synthesis output (answer_text, thinking_trace, grounding_markers)
- routing decision (strategy, confidence_score, alternative_scores)
- observe outcome (converge/diverge/empty/escalate/reroute)
- all timing data (per-segment spans)

**Schema (12-field, frozen):**
```python
{
  "query_id": str,                              # request-scoped ID
  "rewritten_query": str,                       # the actual question asked
  "chosen_strategy": str,                       # "a", "b", "c", "d", or "s"
  "strategy_score": float,                      # confidence_score from observe
  "alternative_scores": {a, b, c, d, s},       # all 5 strategy scores
  "chunks": [                                   # grounded evidence
    {
      "chunk_id": str,
      "document_id": str,
      "is_neighbor": bool,
      "score": float,
      "_neighbor_text": str,
      "tags": {…}
    }
  ],
  "answer_text": str,                             # synthesized answer (or null if escalate)
  "thinking_trace": str,                       # reasoning, strategy, why
  "grounding_markers": [                       # back-reference to chunks
    {chunk_id, confidence, evidence_strength}
  ],
  "latency_ms": {                              # per-segment timing
    "shape_ms": int,
    "pool_ms": int,
    "router_ms": int,
    "fillers_ms": int,
    "observe_ms": int,
    "synthesis_ms": int,
    "total_ms": int
  },
  "attempt_count": int,                        # escalation loop iterations
  "status": str,                               # "answer" | "diverge" | "escalate" | "empty"
  "feature_vector": float[] | null             # null if strategy=s (by design)
}
```

**Emission logic:**
- All code paths (converge/diverge/escalate/reroute) funnel through one canonical encoder
- Anchor: `routing_dump() :4200-4263` (refactor into one emitter)
- **s-row NULL edge:** if strategy=s, `feature_vector` NULL (do NOT populate)
- **Byte-compat P0:** no field reorder, no format changes, NULL semantics preserved

**Meet-old refactor scope:**
- Extract routing_dump into standalone `emit_contract()` function (currently threaded to 8 return sites)
- Wire all code paths to single emitter
- Preserve field order, format, NULL semantics
- Safety: byte-diff clean on cmhc baseline

## Step 7 — TIMING (cross-cut instrumentation) — every segment timed, no untimed code paths

**Goal:** per-segment latency visibility for observability + gate verification. "Untimed = defect."

**Segments to time (all mandatory in meet-old):**

| Segment | Start | End | Anchor | Status |
|---|---|---|---|---|
| **shape** | intent gate start | structure emitted | agent :3066 | `[refactor]` add spans |
| **pool** | per-strategy search start | neighbors assembled | :1762 → :2560 | `[refactor]` split by arm (a_search_ms, b_search_ms, rerank_ms, neighbors_ms) |
| **router** | decision start | chosen_strategy decided | :4161 | `[refactor]` add span |
| **fillers (a/b/c/d/s)** | per-strategy start | filler result ready | :4390+ | `[refactor]` per-strategy spans |
| **observe (per-strategy)** | validation start | confidence_score emitted | (new module) | `[stub]` new spans |
| **synthesis** | compose start | answer_text ready | :2673 | `[refactor]` add span |
| **contract** | emit start | JSON ready | :4200 | `[refactor]` add span |
| **escalation loop attempt N** | attempt start | converge/reroute decided | :3137 loop | `[refactor]` per-attempt span (t_attempt_start, t_attempt_end) |

**Meet-old current state:**
- ✅ **Timed:** pre-route span `:4037` (partition/pool/inheritance), leaf-SQL ms (`:3298-3411` bm25/vector/rerank/neighbors)
- ❌ **Untimed:** escalation/answer-path orchestration (`:3137-3399` only has global t0, no per-attempt)
- ❌ **Untimed:** pool rerank, dtag selectivity, c/d→a redirect re-runs, observe step (doesn't exist yet)

**Meet-old refactor:**
- Extract pool segment timing (break :806 + :562 into a_search_ms, b_search_ms, rerank_ms, neighbors_ms)
- Add per-attempt span (t_loop_attempt_N_start, t_loop_attempt_N_end) inside escalation loop `:3137`
- Wire all 9 segments into one trace telemetry row (rag_query_traces :3737)
- Preserve existing ms columns, add new ones (observe_ms, per_attempt_ms[])

**Schema (latency_ms in contract):**
```python
{
  "shape_ms": int,
  "pool_bm25_search_ms": int,
  "pool_vector_search_ms": int,
  "pool_rerank_ms": int,
  "pool_neighbors_ms": int,
  "router_ms": int,
  "fillers_a_ms": int | None,  # only if strategy a chosen
  "fillers_b_ms": int | None,
  "fillers_c_ms": int | None,
  "fillers_d_ms": int | None,
  "fillers_s_ms": int | None,
  "observe_ms": int,
  "synthesis_ms": int,
  "contract_ms": int,
  "per_attempt": [
    {"attempt": 0, "duration_ms": 1200},
    {"attempt": 1, "duration_ms": 850},
    …
  ],
  "total_ms": int
}
```

**Test for meet-old (timing):**
- **cmhc 22-query baseline:** measure per-segment latency (p50, p95)
- **Before/after:** no missing segments, all traces have full schema
- **Per-attempt:** escalation loop fires on budget/abstain → measure per-attempt ms per query
- **No silent gaps:** grep for untimed code paths (must be zero in refactored pool/shape/fillers/observe/synthesis)

---

## Step 3 — FILLERS (thin consumption, run in parallel) — one per rewritten_query

After router decides the strategy for each query, all N fillers execute **in parallel**. Each filler is **thin** — consumes its pre-built pool, formats output.

### Filler logic per strategy (meet-old)

**Filler a (BM25):**
- **Input:** pool_result (from step 2, already searched/ranked)
- **Logic:** take top-K matches (not is_neighbor=True chunks) from pool result
- **Output:** strategy="a", chunks[:K], metadata {search_mode, match_count}
- Anchor: dispatch `:4390`
- `[refactor]`

**Filler b (vector):**
- **Input:** pool_result (from step 2, already searched/ranked)
- **Logic:** take top-K matches from pool result
- **Output:** strategy="b", chunks[:K], metadata
- Anchor: dispatch `:4390`
- `[refactor]`

**Filler c (LLM):**
- **Input:** pool_result (corpus context), rewritten_query
- **Logic:** pass pool + query to synthesis LLM; LLM generates answer grounded in pool or freeform if pool empty
- **Output:** strategy="c", answer candidate
- Anchor: `:4500` imports `strategy_c`
- `[refactor]`

**Filler d (Google):**
- **Input:** rewritten_query
- **Logic:** call Google API (external), parse results
- **Output:** strategy="d", web results + links
- Anchor: `:4633` imports `strategy_d`
- `[refactor]`

**Filler s (cache):**
- **Input:** query signature
- **Logic:** call payor-platform agent API (mobius_cache) for prior answer
- **Output:** strategy="s", cached answer or NULL
- Anchor: short-circuit `:3929`
- `[refactor]`

### Filler output (common interface)
```python
@dataclass
class FilledResult:
  strategy: str              # "a", "b", "c", "d", or "s"
  chunks: list[Chunk]        # from pool (a/b/c) or web/cache (d/s)
  answer: str | None         # for c/d/s only (synthesized or cached)
  metadata: dict             # strategy-specific diagnostic data
  latency_ms: int            # filler execution time
```

All N results feed into **OBSERVE** (step 4).

### Meet-old refactor scope
- **a/b:** extract pool consumption into named functions (thin consumers)
- **c/d/s:** already separate implementations; wire for thin dispatch
- **Safety:** byte-identical filler outputs on cmhc baseline

---

## Step 4 — OBSERVE (loop control, after fillers)
