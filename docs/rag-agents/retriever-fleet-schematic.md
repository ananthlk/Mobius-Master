# RETRIEVER FLEET — Full Schematic (Live Status)

**Purpose:** one authoritative picture of the whole Retriever answer-engine chain — every module, its real build/sign-off status, what it consumes/produces, and who owns it. Kept current as the source of truth for both humans (Ananth, architects) and agents (any sub-session picking up work) — read this before assuming a contract, don't reconstruct it from memory.
**Last updated:** 2026-07-24 — full rewrite. The 2026-07-23 version was badly stale (described Fillers as "not started" when all five are built and shipped); this version reflects real, independently-verified state as of today, not a copy of the earlier draft.

---

## The chain, as it actually stands today

```
QUERY
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ SHAPE (Step 1)                                                │
│  ├─ Gate (1a)      CLOSED ✅  6-contour classify               │
│  ├─ Reformat (1b)  CLOSED ✅  contour → posture + rewrites      │
│  ├─ Structure (1c) CLOSED ✅  ResourcePosture — now 6 fields:   │
│  │                            breadth / confidence_bar /        │
│  │                            max_attempts / speed_budget /      │
│  │                            token_budget (2026-07-24, per-     │
│  │                            caller_mode, unbounded default) /  │
│  │                            authority_requirement (2026-07-24, │
│  │                            "any"|"citable_required",          │
│  │                            caller-declared, fail-open)         │
│  └─ Slots (1d)     CLOSED ✅  → AnswerShapeResult (slots[], each  │
│                       with slot_id/slot_semantics/capacity/       │
│                       rewritten_query/required/priority)         │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ POOL (Step 2)              CLOSED ✅                            │
│  Builds ONE shared candidate pool, once, per rewritten_query.   │
│  Strategies: tag-coverage, vector, inherited (AHCA).            │
│  Union + two-tier dedup + neighbor-expand.                       │
│  P0 FIXED (2026-07-24): public_adapter.py referenced a           │
│  nonexistent `authority_level` column instead of the real        │
│  `document_authority_level` — broke every query's tag_select/    │
│  vector/inherited arms. Verified against live schema, fixed.      │
│  _build_pool_metadata (orchestrator.py, Retriever's file) fixed   │
│  same day: tag_select's raw tag-COVERAGE COUNT was being clamped  │
│  into top_score_percentile as if it were a [0,1] score (a real    │
│  coverage=4 hit was reading as a fake "perfect" 1.0) — excluded    │
│  from the calc entirely; only vector's genuine cosine + bm25_score │
│  feed it now. Also added `distinct_content_topk` (top-10 candidate │
│  diversity, normalized-TEXT grouping — content_sha is NOT a        │
│  reliable text-dedup key in this schema, verified: 5 byte-identical │
│  chunks, 5 different content_sha values).                          │
│  → PoolResult (candidates[] with chunk_id/document_id/text/       │
│    source_arm/score/tags/document_status/source_type/...,         │
│    segment_ms, strategy_hint)                                     │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ ROUTER — "Reasoning + Strategy"                                  │
│  Dual-allocator shadow-mode (greedy + real constrained optimizer  │
│  + bayesian), A/B/C draw picks which executes, others log as      │
│  shadow (comparison-only, never run). Real priors, file-backed.   │
│                                                                    │
│  2026-07-24 additions, all independently verified:                │
│  - Payload/token gate: capacity × PAYLOAD_TOKENS_PER_CHUNK ≤       │
│    token_allowance_per_slot (posture-driven, default = no          │
│    behavior change). Per-chunk values a/b/c=1000, d=500(measured), │
│    s=150 — ESTIMATES except d, logged as WARNING on skip until      │
│    real corpus measurement lands.                                  │
│  - Authority/citability gate: `authority_requirement` field —      │
│    "citable_required" makes non-citable strategies (d) ineligible   │
│    for REQUIRED slots only; external_context keeps d (context, not  │
│    evidence). Fail-open default "any".                              │
│  - `app/services/router/continuation.py` (decide_continuation) —   │
│    NEW module. Aggregates N slots' (verdict, reason) pairs + the    │
│    time budget into ONE query-level "another turn, or done" call.   │
│    Verdict enum (Router's contract, Observer emits into it):        │
│    WOULD_BENEFIT / SATISFIED / EXHAUSTED_ATTEMPTS (permanently       │
│    ineligible) / EXHAUSTED_BUDGET (clock cutoff, conditionally       │
│    re-eligible, rides along free if a sibling justifies a turn) /    │
│    ERROR (infra failure, advances to next rung, no same-rung         │
│    retry). Ride-along observations get a `ride_along: true` flag     │
│    (Eval's required selection-bias segmentation — a ride-along        │
│    SATISFIED is sampled from "a sibling was struggling," not the      │
│    strategy's own merits).                                            │
│  - Execution-order permutation-invariance ruling (router-build-       │
│    spec.md §11): every §2a-enforced quantity is order-independent     │
│    over a slot's planned chain, so the orchestrator's execution        │
│    loop may run any PLANNED rung next based on live readiness (e.g.    │
│    a not-yet-ready speculative prefetch) without re-deriving Router's   │
│    plan-time math. Guarded by a contract test.                         │
│  → RoutingLadder (per slot_id: strategy_sequence[]) + ContinuationDecision (per turn) │
│  Spec: `router-build-spec.md`, `router-module-spec.md`                 │
└─────────────────────────────────────────────────────────────┘
  │
  ▼         (orchestrator.py drives this loop — thin glue, no business logic of its own)
┌─────────────────────────────────────────────────────────────┐
│ LOOP (per slot, multi-turn, orchestrator-owned control flow)       │
│                                                                     │
│   FILLERS (Step 3)     ALL FIVE BUILT AND REAL — a/b/c/d/s.         │
│     a (BM25)      — real, deterministic rerank over Pool. Authority-  │
│                      weight vocabulary fixed (canonical values).       │
│     b (Vector)    — real, deterministic rerank. Junk-cluster defense   │
│                      shipped: hard length floor (drop <50 chars,       │
│                      not soft-penalize) + exact-text dedup. Honest     │
│                      empty (0/10) beats silently-confident junk.       │
│     c (LLM Retrieval) — real quote-verification gate: a fetched        │
│                      chunk whose LLM-cited quote doesn't verify         │
│                      against the actual corpus text downgrades to      │
│                      doc_found_section_missing (0.5 confidence), not    │
│                      silently accepted as high-confidence. Confirmed    │
│                      real hallucination case caught this way (real      │
│                      doc/page, fabricated section+quote).                │
│     d (Web Search)  — real BM25-informed reranking over fetched         │
│                      passages (OR-joined to_tsquery fix — plain AND      │
│                      query scored a genuinely correct passage 0.0).       │
│                      Diversified search funnel (Vertex + Vertex-           │
│                      unconstrained + DDG, merged/deduped, 15-20            │
│                      candidates). SPECULATIVE PREFETCH (2026-07-24):        │
│                      cheap search-only step fires concurrently with          │
│                      Pool's build, gated on authority_requirement !=          │
│                      "citable_required"; fetch+synthesize stays sequential,    │
│                      paid only if Router assigns "d". Real measured savings:    │
│                      20.2%-53.2% (range, not a stable %  — Vertex search        │
│                      latency varies run to run, 5.4-9.7s observed).              │
│                      Execution loop won't COMMIT to "d" if its prescreen           │
│                      isn't ready yet (non-blocking .done() check) — defers          │
│                      (not drops) it behind a ready alternative for that turn;         │
│                      distinct `prescreen_not_ready_deferred_slots` emit label          │
│                      so this never gets folded into a failure signal.                   │
│     s (Fact Store)  — real Payor Platform lookup. chunk_id/document_id                  │
│                      fixed to a content hash (payer_key|record_type|                     │
│                      predicate|answer_text), not the fact-store's per-call                │
│                      telemetry_id — same fact now produces the same id                     │
│                      every call (was non-deterministic before the fix).                     │
│     Contract: FilledChunk now has `url: str|None` (external) alongside                        │
│     `document_id: str|None` (internal, mutually exclusive), plus                              │
│     `page_number`/`paragraph_index` — DB-landed 2026-07-24.                                     │
│     → FilledShape (slots[] with chunks[] assigned, occupancy,                                   │
│       under_filled/over_filled)                                                                  │
│     Spec: `fillers-schematic-spec.md`                                                              │
│                    │                                                                                │
│                    ▼                                                                                 │
│   ORCHESTRATOR EXECUTION LOOP (orchestrator.py, Retriever's file) — REAL,                             │
│     multi-turn, wired to Router's decide_continuation(). Per slot, per                                 │
│     attempt: run the planned rung (readiness-reordered if it's a                                        │
│     not-ready "d"), compute a (verdict, reason) via a STOPGAP (bare                                       │
│     occupancy check — real Observer logic not wired into production yet,                                  │
│     see below), hand all slots' verdicts + elapsed time to Router's                                        │
│     aggregation, which decides ONE query-level "another turn, or done."                                     │
│     DISCARD model today (a slot's result is REPLACED each retry, not                                         │
│     accumulated) — Ananth's ruling (2026-07-24): RETAIN superseded rungs'                                     │
│     outputs for a future Synthesis combine/choose step, once Synthesis has                                     │
│     a real consumer for it. Design-of-record in observer-module-spec.md §8,                                     │
│     build gated on Synthesis's own kickoff (now underway, see below).                                            │
│     NEW (2026-07-24): whole-loop retry on TECHNICAL failure — if any                                              │
│     unhandled exception reaches the top level (e.g. a dropped DB connection,                                       │
│     the real failure mode seen live this session), the ENTIRE pipeline retries                                     │
│     ONCE (`run_retriever_partial_with_retry`, "ask once, try our best to get                                        │
│     first-pass resolution" — Ananth's principle). Distinct from a legitimate                                        │
│     low-confidence result, which Observer/Router already handle honestly as a                                        │
│     real, gradeable outcome, not a failure. Each attempt gets a distinct                                              │
│     Router agent_id suffix so Eval's calibration can tell a technical retry                                           │
│     apart from an independent second query, not silently double-count it.                                              │
│                    │                                                                                                    │
│   OBSERVER (Step 4e) — BUILT + LIVE-VALIDATED, NOT YET WIRED INTO PRODUCTION                                            │
│     (build-gate: Fillers+Synthesis+a committed calibration plan, per Eval —                                              │
│     Synthesis now exists, calibration plan still pending). Scope, settled:                                                │
│     per slot, per attempt, a strategy-specific yes/no "would this benefit                                                  │
│     from another turn" — no shared confidence scale across strategies, each                                                │
│     filler defines its own "good enough" (Ananth's explicit call). Real logic                                              │
│     shipped for a/b/c/s (capacity-aware sufficiency bar, c's quote-verification                                            │
│     status); d still a placeholder (filled-to-capacity only, pending real                                                   │
│     junk/dedup-quality criteria with Web Search's session). Emits Router's                                                    │
│     verdict enum verbatim, with a reason string (Eval's non-negotiable —                                                      │
│     calibration keys off both, never a bare bool). Does NOT own cross-slot                                                     │
│     aggregation (that's Router's decide_continuation) — strictly per-slot.                                                      │
│     Live-validated: a real integration run caught a case the current                                                            │
│     production stopgap misses (an unverified LLM citation the stopgap would                                                      │
│     accept as "good enough," Observer correctly flags WOULD_BENEFIT).                                                              │
│     Spec: `observer-module-spec.md`                                                                                                 │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ SYNTHESIS (Step 5)          v1 BUILT, SPEC WRITTEN, SIGN-OFF IN     │
│                              PROGRESS. NOT wired into orchestrator.py │
│                              yet (needs a real AsyncSession threaded  │
│                              where Fillers already have one).          │
│  Scope correction (Ananth, 2026-07-24, before code was written against  │
│  the wrong framing): Synthesis does NOT author answer text — Chat does. │
│  Synthesis COMPILES: per-slot rerank, cross-slot dedup (two-tier,        │
│  mirrors pool/dedup.py), neighbor completion for internal chunks           │
│  missing sibling context (reuses corpus_search._expand_with_neighbors,     │
│  same helper Pool uses), document_name resolution (a real, confirmed       │
│  gap closed — neither PoolCandidate nor FilledChunk carried one; batched    │
│  rag_published_embeddings lookup, honest fallback chain, never silently    │
│  blank), verified/unverified + planned/live passthrough (byte-for-byte,     │
│  non-negotiable per Eval), and full cross-module telemetry compilation.      │
│  → SynthesisResult (slots: list[CompiledSlot], citations: flat                │
│    cross-slot-deduped list mapping field-for-field onto Chat's SourceRef,      │
│    telemetry: SynthesisTelemetry)                                              │
│  Sign-off status: Retriever ✅, Product-Awareness ✅ (with a build condition    │
│  attached: document_status has no default, every construction site must         │
│  explicitly decide it). Chat/Eval: informal design review done, formal spec       │
│  sign-off requested. UX/DB: not yet replied. Filler-family: routed to Filler c     │
│  (verified field's direct source) and Filler d (external-chunk shape owner) —      │
│  Retriever represents a/b/s's shared, already-stable contract stake.                 │
│  Spec: `synthesis-module-spec.md`, tracker: `synthesis-tracker.md`                     │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ CONTRACT (Step 6)           v1 BUILT, 14/14 tests               │
│  12-field byte-compatible response envelope (module-gates.md §6   │
│  version — retriever-build-checklist.md's 13-field draft was a    │
│  stale legacy schema, not used). One emitter: build_contract().     │
│  answer_text/thinking are optional, caller-supplied (Chat authors   │
│  these downstream of this pipeline, not Synthesis — Ananth's         │
│  correction) — None until threaded back, not a stub.                  │
│  → contract.py                                                          │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ TIMING (Step 7, cross-cut)  gap closed                            │
│  Every segment timed. The one concrete gate requirement that was    │
│  actually missing — per-attempt timing on the escalation loop         │
│  (t_attempt_start_ms/t_attempt_end_ms per rung executed, per slot)      │
│  — is now emitted via filled_shape.emit["attempt_spans"]. All other      │
│  segments (gate/reformat/slots/pool/router/fillers/synthesis/total_ms)    │
│  were already real, pre-existing timing.                                    │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
RESPONSE
```

---

## Ownership table (who to ask, who's building)

| Module | Status | Owning session | Spec file |
|---|---|---|---|
| Gate (1a) | CLOSED | "4a - Shape:Gate" | — |
| Reformat (1b) | CLOSED | "4a - Shape:Refactor" | — |
| Structure (1c) | CLOSED — now with token_budget/authority_requirement | "4a - Shape:Structure" | — |
| Slots (1d) | CLOSED | "4a - Shape:Slots" | `shape-slots-module-spec-v1.md` |
| Pool (2) | CLOSED, P0 fixed 2026-07-24 | "4b - Pool" | `pool-schematic-spec.md` |
| Router (Reasoning+Strategy) | Real, hardened, actively extended 2026-07-24 (continuation.py, payload/authority gates, permutation-invariance ruling) | "4c - Router" | `router-build-spec.md`, `router-module-spec.md` |
| Fillers: a (BM25) | ✅ Real, authority-weight vocab fixed | "4d - BM25" | `fillers-schematic-spec.md`, `filler-a-calibration-plan.md` |
| Fillers: b (Vector) | ✅ Real, junk-cluster defense shipped (length floor + dedup) | "4d - Vector search" | `filler-b-vector-kickoff.md`, `-tracker.md`, `-calibration-plan.md` |
| Fillers: c (LLM Retrieval) | ✅ Real, quote-verification gate shipped | "4d - LLM Retrieval" | `filler-c-llm-retrieval-kickoff.md` |
| Fillers: d (Web Search) | ✅ Real, BM25-reranked + diversified + speculative prefetch | "4d - Web Search" | `filler-d-web-kickoff.md`, `-tracker.md` |
| Fillers: s (Fact Store) | ✅ Real, chunk_id determinism fixed | Retriever (no dedicated session) | `filler-s-payor-module-spec.md` |
| Fillers: e/f/q | Not lettered-filler concepts — e (fast exit) and f (sitemap) resolved as orchestrator-level/helper concepts, not real fillers; q not started | n/a | — |
| Sitemap links (helper, not a lettered filler) | Built | "4d - Sitemap" | `filler-f-sitemap-kickoff.md` |
| Observer (4e) | v2 built + all 5 strategies (a/b/c/d/s) real logic confirmed. **Design sign-off CLOSED 4/4** (Retriever ✅, Chat ✅, DB ✅, TECH ✅ formal, 2026-07-24). Production wiring gated on Eval's calibration plan (drafted, blocked on a DB proxy restart, unrelated to the design itself) | "Observer 4e" | `observer-module-spec.md` (v2, rewritten 2026-07-24 — v1 and the Bayesian-confidence addendum both formally superseded, see doc lineage note), `observer-tracker.md` |
| Synthesis (5) | **CLOSED 2026-07-24 — 9/9 sign-off** (Filler c, Filler d, Observer, Retriever, Chat, Eval, Product-Awareness, UX, DB all ✅). Two real bugs found+fixed during DB's review pass (a live crash on every fact-store-sourced answer; an adjacent authority-misclassification bug, both verified fixed). **WIRED into `orchestrator.py`'s production path 2026-07-24** — `run_retriever_partial()` now calls `compile_synthesis()` after Fillers, real verdicts threaded through from `filled_shape.emit`, verified live against the real DB (not just unit tests) | "4f - Synthesizer" | `synthesis-module-spec.md`, `synthesis-tracker.md` |
| **Contract (6)** | **v1 built, 19/19 tests. Sign-off 4/6: TECH ✅, Chat ✅ (unconditional, after a revision pass adding routing_verdict/terminal_action/authority_requirement/model_trace/authority-in-chunks), Product-Awareness ✅ (document_status passthrough verified byte-for-byte), Eval ✅ (calibration-readiness: chunks[].verified/model_trace/routing_verdict/attempt_spans all confirmed sufficient; ride_along-persistence flagged as a wiring-time forward item, not a Contract gap). DB/UX in progress.** | Retriever | `contract.py` |
| **Timing (7)** | **Gap closed (per-attempt spans), covered under TECH's chain-level integration sign-off (2026-07-24) — no separate dedicated round run** | Retriever | `orchestrator.py` (`attempt_spans` emit) |

## What's blocking what, right now (the real dependency chain)

1. **Observer's production wiring** is gated on a committed calibration plan (Fillers ✅, Synthesis ✅ now exist — the calibration plan is the remaining piece, Eval's to draft).
2. **Rung retention** (superseded fillers' outputs kept for Synthesis to combine) is designed (`observer-module-spec.md` §8) but not built — gated on Synthesis actually needing it as a consumer, which is closer now that Synthesis v1 exists but still needs its own build authorization.
3. **Synthesis's cross-agent sign-off** (Chat/Eval/UX/DB/Filler-c/Filler-d) is the active gate before it's considered closed — see `synthesis-tracker.md` for live status.
4. **Contract and Timing** are now built (2026-07-24) — both gated only on cross-agent sign-off (Chat/Eval/DB/UX haven't reviewed `contract.py` yet), not on any remaining design work.
5. ~~Router's estimated per-chunk payload values need a real corpus measurement~~ — **RESOLVED 2026-07-24**: replaced the 1000-token guess for a/b/c with the real measured p95 (~230 tokens + margin → 250). See the payload-gate-collapse writeup below.

## Deferred, scoped follow-ups (logged so they don't get lost, not forgotten open questions)

- **Capacity as a joint planning variable + optimizer-as-primary** (Router/Eval design, 2026-07-24): recall-vs-capacity curve replaces a single recall_lift point per cell (no new calibration-cell dimension); Shape's `capacity` becomes a cap, Router chooses effective k ≤ cap jointly with strategy, subject to the token budget. Explicitly sequenced AFTER a measured baseline lands (zero real capacity-vs-recall data exists until persist is live) and scoped together with the Observer/candidate-pool redraw. Not started.
- **`authority_requirement` has no threading path into `run_retriever_partial`** — found 2026-07-24 while building integration tests. Structure supports the param; the orchestrator's top-level entry point never accepts or forwards it, so every live call silently defaults to "any." Documented as a live test (`test_integration_production_shapes.py::TestAuthorityRequirementThreading`), not yet fixed.
- **Contract's `chosen_slot`/`score` mixes incomparable cross-strategy scores** (s's external confidence vs a/b's vector/BM25) — same root cause as Pool's `top_score_percentile` fix. Narrow impact (diagnostic-only field, doesn't touch `chunks[]` or calibration). Eval's ruling: defer behind persist/capacity work, but documented in `contract.py`'s `_pick_chosen_slot` docstring so the fix direction (reuse Pool's normalization decision) isn't lost.
- **Pre-existing worker/utils/curator test failures** (test_utils.py, test_worker_db.py, test_worker_path_b.py, test_curator_service.py) — confirmed unrelated to the retriever chain, spawned as a separate tracked task.

## Fleet-wide production-readiness pass — real bugs found and fixed today (2026-07-24)

All independently verified (real code re-read, real tests re-run, real live queries), not taken on any session's self-report:

- **Pool P0**: `authority_level` column didn't exist (`document_authority_level` is the real name) — broke tag_select/vector/inherited on every query. Fixed.
- **Junk-poisoning chain**: a 669-row, 23-char corpus boilerplate cluster was (a) making Filler b return 100%-junk "full occupancy" and (b) separately corrupting Router's depth-bucket signal via a raw tag-coverage count clamped to a fake 1.0. Both root-caused and fixed same day; Filler b's fix is a real precision tradeoff (honest 35% under-fill beats silent 0% junk contamination).
- **Filler c grounding-integrity bug**: LLM hallucinated a citation section/quote that doesn't exist in the corpus (real title/page, fabricated content) — now caught by a quote-verification gate, downgrades to honest low-confidence instead of silently mis-grounding.
- **Filler d BM25 bug**: a straight AND-based tsquery scored a genuinely correct fetched passage 0.0 against the real question (didn't repeat exact query terms) — fixed with an OR-joined query.
- **Orchestrator posture-threading gap**: Structure computed `token_budget`/`authority_requirement` correctly, but a 3-layer break (missing dataclass fields, missing dict-bridge keys, missing orchestrator pass-through) meant neither field ever reached Router in production. All three layers fixed, verified end-to-end with a real query showing the payload/authority gates actually firing.
- **Speculative-prefetch stall bug**: the concurrent search prefetch was being awaited unconditionally before Router even ran, stalling the whole pipeline on the full search cost even for queries where Router never picks "d." Fixed — awaited lazily, only inside the "d" branch, only if Router actually assigns it.
- **Cross-cutting**: the pytest-asyncio event-loop-sharing batch flakiness (a handful of tests fail in full-suite runs, pass individually) remains a known, reconfirmed pattern across multiple modules today — never root-caused, still just documented as expected noise each time it's re-hit.

## Standing cross-cutting rules (apply everywhere above)

- **PHI fail-closed** — no raw query/user content ever persisted without explicit classification; established since Gate.
- **Verify-before-trust** — every claim (a field exists, a bug is fixed, a test passes, a percentage is stable) gets independently checked against real code/data/live runs before being relayed upward or reported as sign-off, not taken on a sub-agent's word. Applied literally, all day, and caught real things: a wrong test-count claim, a stale docstring, an overstated latency percentage, a genuinely serious depth-signal corruption bug.
- **Module-prefixed filenames in shared directories** — ping before touching a file another session owns in a shared dir.
- **"Ask once, try our best"** (Ananth, 2026-07-24) — a technical failure gets one whole-loop retry before surfacing broken; a legitimate low-confidence result is never treated as a failure to retry away.
- **caller_mode vocabulary bug** and **lexicon-embeddings cache** are both explicitly OUT of Retriever's scope (fleet-owned by Broadcaster / deferred to Curation refactor respectively) — do not re-raise from within this chain.
