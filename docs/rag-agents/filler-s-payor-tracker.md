# Filler s (Payor Platform Fact Store) — Progress Tracker

**Status:** v1 (tags-only) built AND calibrated against the real, live fact store. `filler_s.py` + `filler-s-payor-module-spec.md` written; 15 unit tests + real live-service calibration run all passing (`filler-s-payor-calibration-report.md`). Only remaining gate: cross-agent sign-off (Chat/Eval/DB/TECH).

---

## What was done

- Read and verified real prior art directly: `corpus_search_agent.py:3820-3965` (legacy strategy-s, fact-store fast-exit), `mobius-payor/app/fact_store.py::fact_query()` (346-473, the real server-side implementation), `app/routers/payor_skills.py` (real route path), `mobius-rag/docs/payor-fact-store-spec.md` (the ratified contract spec), `fillers-schematic-spec.md`, `pool-schematic-spec.md` §3.3 (inherited/AHCA — related but distinct from the fact store), `filler_a.py` + `fillers/contracts.py`, and Filler c/d's kickoff docs (the other two live-external-call fillers, already resolved several shared problems).
- Confirmed the architectural fork the same way Filler d already got resolved: Filler s is a **live-trigger, per-slot, per-attempt** filler, not a pure `PoolResult` consumer — fires when a slot's `RoutingLadder` rung is `"s"`.
- Found a **real, verified divergence** between the payor service's documented contract and legacy's actual call: legacy never sends `embedding` in its request despite the payor service's own docstring stating vec_sim requires it from RAG's side — this is an independently-real, RAG-side half of the documented "over-serve" bug (`[[project-payor-fact-store]]` memory), not fully explained by fact-embedding backfill status alone.
- Found a real, verified bug in legacy's response handling: `served.get("payer_key")` reads a field that does not exist in the real `served` dict (`fact_store.py:434-446`) — always `None` in practice. Not porting this forward.
- Mapped the fact-store hit onto `FilledChunk` (one synthesized chunk per hit, not per-passage like c/d) — real-score passthrough for `original_score` (unlike c/d's constants, since this filler has a genuine calibrated confidence signal), still flows through Observer's existing percentile-within-pool normalization, no special-casing needed.
- Checked Gate's real `Contour` vocabulary (`shape/contracts.py:15-23`) directly to answer whether the new pipeline has a better conceptual-vs-factual intent signal than legacy's marker-word list — it does not (Contour is a tag/doc-coverage classification, orthogonal to this question). Porting the marker list as the best available signal, with its known over-fire limitation intact and unsolved.
- Concluded the miss/error path is simpler in the new architecture than legacy's monolithic fast-exit: no `force_s`/fallthrough special-casing needed, a miss is just occupancy=0 for that attempt and Observer's existing per-slot Bayesian loop decides the next rung.

## Verified-before-trust notes

- Did not assume legacy's request payload was the real/complete contract — read the payor service's own `fact_query()` implementation and its module docstring directly, which is how the `embedding`-field gap and the `payer_key` non-field were found. Both are real, code-verified findings, not inferences from memory alone.
- Did not assume `original_score` needed a constant just because c/d used one — checked *why* they used constants (no native per-item signal) versus this filler's situation (a genuine calibrated blend score) before choosing to pass the real number through instead.
- Did not assume the marker-word conceptual gate was "good enough because it's in the legacy code" — checked Gate's actual `Contour` enum in `shape/contracts.py` before concluding there's nothing better to use in the new pipeline.

## Open — blocking code start

1. **`url` field on `FilledChunk`** — same shared blocker Filler c/d already have open (DB hasn't landed it in `contracts.py` yet, confirmed still absent). Not a new blocker, just inherited.
2. **Gate signal (open question #2)** — routed to Gate's session by Retriever; not yet replied. My own check of `Contour`'s vocabulary already suggests there's nothing better than the ported marker-word list, but leaving this open until Gate's own session confirms directly.
3. **Eval's α/β/τ re-sweep + `_CONCEPTUAL_MARKERS` removal, sequencing** — new (see reversal below), not a v1 blocker but gates when the embedding-send fast-follow can ship. Not yet sent to Eval as of this tracker update.

## RESOLVED — including a real reversal worth recording

**Query-embedding source (reuse vs. own call):** RESOLVED as reuse-Pool's-embedding, verified directly (same model `gemini-embedding-001`, same dimension `vector(1536)`, same task_type `RETRIEVAL_DOCUMENT` on both sides — confirmed via `deploy_cloudrun_dev.sh`, `fact_embed.py`, `embedding_provider.py:92`, `add_pgvector_columns.py:61`, `add_payor_fact_store.py:29/97`). New Pool contract gap surfaced (`PoolResult` needs a `query_embedding` field) — asked Retriever to route to Pool.

**But reversed the "just ship it" framing after "3a - Payor platform" flagged a real regression risk (2026-07-23):** sending `embedding` is NOT a monotone improvement. Payor's blend formula rescales entirely once `embedding` is present (`base = overlap` → `base = 0.5·overlap + 0.5·vec`), which would silently drop some currently-good serves below `τ`, not just fix the known over-serve cases. Payor's explicit ask: bundle the embedding-send fix with Eval's α/β/τ re-sweep AND dropping RAG's `_CONCEPTUAL_MARKERS` band-aid, as one measured, sequenced change — not three independent ships, and not during the current clean-tree freeze (payor is holding their own additive `payer_key` fix for the same reason).

**Revised v1 scope:** Filler s v1 ships tags-only (no `embedding` sent), matching legacy's current calibrated operating point exactly — no `query_embedding` plumbing needed from Pool for v1 either. The embedding-send fix + Pool's `query_embedding` reuse become an explicitly-tracked fast-follow, sequenced with Eval's re-sweep once the freeze lifts — not a v1 blocker, but not silently droppable.

**`served.payer_key` (finding 2):** CONFIRMED by payor directly, and fixed server-side additively (payor added `payer_key` to the `served` dict itself — zero client-side change needed once deployed). Held for the same freeze; deploying post-baseline.

## Built (2026-07-23)

- `filler_s.py` — `fill_shape_fact_store()`, tags-only v1, mirrors a/b's shipped signature convention (whole-`AnswerShapeResult`, `routing_ladders` accepted but unused v1) rather than Filler d's still-unresolved per-slot proposal. Only acts on `slot_semantics == "direct_answer"` slots. Gate condition reuses the fleet-shared `extract_payer_slug()` (`payer_context.py`, built anticipating c/d/f/s) rather than re-deriving the `j:payor.*` check inline — caught this mid-build by checking for existing shared infra before shipping a duplicate.
- `test_filler_s.py` — 15 tests: gate condition (direct_answer-only, payer-tag-required, conceptual-marker rejection), request payload (asserts `embedding` key is absent — a regression guard for the deliberate v1 scope decision), hit/miss/gate-fail/network-error/non-200 paths, synthetic-id fallback when `source_ref.doc_id` is missing, emit diagnostics, determinism. Real execution: `pytest app/services/retriever/fillers/` → 67 passed, 2 skipped, 0 failed.
- `filler-s-payor-module-spec.md` — formal spec for cross-agent sign-off, all design forks resolved (see kickoff doc history).

## Calibrated (2026-07-23)

- Real run against the live `MOBIUS_PAYOR_URL` (no mocks): 6/6 gate-condition predictions matched across 3 gate-pass + 2 gate-reject + 1 known-bug-repro case. Two reject cases verified to make **zero HTTP calls**. Full report: `filler-s-payor-calibration-report.md`; raw JSON: `filler-s-payor-calibration-results.json`; script: `mobius-rag/app/services/retriever/fillers/calibrate_filler_s.py`.
- Live-reproduced the documented PARKED over-fire bug (non-stored payer "Humana" still gets served a fact server-side) — confirmed real and current, not something Filler s can or should fix client-side.
- Honest caveat recorded in the report: `tag_matches` were hand-picked, not real Gate output — validates Filler s's own gate/parsing logic for real, does not yet validate the full Gate→Fillers integration (no such wiring exists yet to test against).

## Not started

- Cross-agent sign-off (Chat/Eval/DB/TECH).
- The embedding-send fast-follow (§6 of the module spec) — explicitly deferred, not a v1 gap.
- Full end-to-end calibration with real Gate-derived tags, once Gate/Fillers integration exists.
