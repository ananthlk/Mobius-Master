# FILLERS — Schematic Spec (Step 3) — v1

**Status:** DRAFT — design doc, no code written yet. Drafted by UX, corrected once by Retriever (an earlier draft had Fillers re-deriving slot structure from scratch instead of consuming Slots' actual output — fixed before this version).
**Owner:** to be assigned — no dedicated "Fillers Agent" session exists yet; needs to be forked to actually build this once sign-off clears, same pattern as every prior module.
**Companions:** `shape-slots-module-spec-v1.md` (Slots, Step 1d, upstream), `pool-schematic-spec.md` (Pool, Step 2, upstream), `docs/rag-agents/module-sequence.md` (authoritative 7-step sequence).

---

## Module Identity
- **Role:** Pure chunk-to-slot assignment orchestrator.
- **Sequence:** Step 3 (Pool → **Fillers** → Router).
- **Upstream dependency:** Fillers consumes Slots' `AnswerShapeResult` directly — it does **not** re-derive slot structure, capacity, priority, or semantics. Those are already computed by Slots.
- **Contract:** read-only over Pool + `AnswerShapeResult`; zero DB/embed side effects.
- **Emit pattern:** diagnostic-only (v1); narrate layer deferred.

---

## Input Contract

**`PoolResult`** (from Pool, Step 2, closed 5/5):
```
candidates[]{
  chunk_id: string
  score: float [0.0, 1.0]
  source_type: enum (document|product_docs|web|external|...)
  tags: string[]
  segment_id: string (pool segment origin)
}
segment_ms: {pool_segment_1_ms, pool_segment_2_ms, ...}
strategy_hint: string (e.g., "dense", "sparse", "tag_only")
```

**Additive, live-external fillers only (c/d/f/s) — ADDED 2026-07-23, real gap found independently by 3+ filler sessions (c, d, f, s all hit this):**
```
tag_matches: list[str]   # from GateResult — d/j/p tag codes, needed for payor/domain gating (e.g. j:payor.* checks)
db: AsyncSession         # live external fillers make real calls (LLM/web/fact-store/sitemap DB queries);
                         # a/b remain pure-over-the-pool, this does NOT apply to them
```
Pure-over-the-pool fillers (a, b) do not receive `db`/`tag_matches` — they stay strictly `PoolResult` + `AnswerShapeResult` + `RoutingLadder`. This was a one-time gap at the parent-spec level (each of c/d/f/s independently rediscovered the same missing inputs), not four separate signature extensions — fixed here once.

**`AnswerShapeResult`** (from Slots, Step 1d):
```
slots[]{
  slot_id: string (e.g., "direct_answer", "fanout_0", "fanout_1", ..., "external_context")
  slot_semantics: enum (direct_answer | thematic_exploration | external_context)
  capacity: int (pre-computed: breadth // len(themes) for FAN_OUT, full breadth for others)
  rewritten_query: string (FAN_OUT only — the query this slot corresponds to, real field on AnswerSlot, verified in code)
  required: bool (False = optional/fallback for RELY_ON_EXTERNAL and CLARIFY_REPHRASE's best_guess slot)
  priority: int (ranking by theme score for FAN_OUT; 0 for others)
}
```

**`RoutingLadder`** (from Router's early phase — ADDED 2026-07-23 per `change-request-observer-module.md`, part of the Observer/two-phase-Router change, UX-approved):
```
ladders[]{
  slot_id: string (correlates to AnswerShapeResult.slots[].slot_id, same string-key pattern, no mutation of AnswerSlot)
  strategy_sequence: list[str] (e.g., ["a", "b", "c"], sized to that slot's max_attempts)
}
```
Fillers reads the current attempt's rung off the matching slot's `strategy_sequence` (which rung = which attempt number, driven by the orchestrator's loop, not by Fillers itself) to decide how to fill that attempt. This is Fillers' third input — `PoolResult` + `AnswerShapeResult` + `RoutingLadder`.

## Output Contract (`FilledShape`)

```
FilledShape:
  slots[]{
    slot_id: string
    slot_semantics: enum (direct_answer | thematic_exploration | external_context)
    capacity: int
    chunks[]{
      chunk_id: string
      document_id: string          # CORRECTED 2026-07-23 — dropped in earlier draft, Chat caught it (grounding badge/vault_sources identity)
      text: string                  # CORRECTED 2026-07-23 — dropped in earlier draft; Synthesis needs actual chunk content, not just an id
      document_status: string | None  # planned|live passthrough, Product-Awareness reality-gating (target-structure-spec §10) — must survive pool→fillers→synthesis→contract
      content_sha: string | None    # passthrough, dedup/provenance
      source_type: string
      tags: dict
      is_neighbor: bool             # passthrough — Synthesis treats neighbor context differently from a direct match
      original_score: float | None  # None for pure neighbors, same as PoolCandidate.score
      assignment_reason: string (e.g., "score_rank", "semantic_match", "fallback")
    }
    occupancy: int (actual chunks assigned)
    under_filled: bool (occupancy < capacity)
    over_filled: bool (occupancy > capacity)
  }
  total_chunks_assigned: int
  filling_strategy: string (v1: "score_rank" | "semantic_match")
  emit: {fillers_decision, ...}
```

## Filling Algorithm (v1) — Phase 2 onward, NO slot derivation

**Phase 2: Chunk assignment to pre-built slots**
1. Sort `Pool.candidates` by score descending.
2. For each slot in `Slots.slots` (in priority order):
   - Apply slot-semantic-specific logic:
     - `direct_answer` → assign top-N highest-score chunks; prefer direct-answer-semantic candidates.
     - `thematic_exploration` → assign diverse chunks within this theme (priority order from Slots already handles theme ranking); balance within-theme breadth.
     - `external_context` → assign highest-score chunks from Pool filtered by `source_type` (web, external); fallback if `required=False`.
   - Track occupancy vs capacity.

**Phase 3: Overflow handling**
- Candidates beyond total capacity → log as overflow (emit only). Do NOT truncate; pass overflow to Router for ranking.

**Phase 4: Under-fill detection**
- Flag `under_filled: bool` per slot, emit `under_fill_count` + shortfall per slot. Router handles the downstream consequence (fallback synthesis, etc.).

## Emit Contract (v1 — Diagnostic-only)

```
emit.fillers:
  slots_filled: int
  empty_slots: int
  under_filled: int
  over_filled: int
  total_overflow: int
  filling_strategy: string
  filling_ms: int
  per_slot_details: [{slot_id, slot_semantics, occupancy, capacity}]
```

**Narrate layer (future):** "Filled X/Y slots with semantic-aware strategy; Y under-filled; overflow N to Router."

## Seam Contracts

**Seam α (Pool → Fillers input):** Pool emits `candidates[]`/`segment_ms`/`strategy_hint`; Fillers assumes candidates are scored (sort order not assumed, Fillers re-sorts); if `candidates.length = 0`, `FilledShape` has empty slots.

**Seam β (Slots → Fillers input):** Slots emits `AnswerShapeResult` (pre-built slots, priorities, semantics, capacities, `rewritten_query` per FAN_OUT slot); Fillers assumes slots are definitive, no re-derivation.

**Seam γ (Fillers → Router output):** Fillers passes `FilledShape` (slots with assigned chunks, occupancy truth, semantics); Router assumes slots are pre-filled — Router ranks/orders, does not re-fill or re-assign.

## Constraints (Enforce in Code)

1. **Read-only:** Fillers reads Pool + `AnswerShapeResult` only. Zero writes to DB/cache/embed.
2. **No re-derivation:** Fillers consumes Slots' output as-is; does not re-compute slot structure, capacity, priority, or semantics.
3. **No side effects:** Pure logic. Timing wall-clock only (no async I/O).
4. **Deterministic:** Same inputs → same slot assignments (sort stability for tied scores).

## Resolved Design Questions (answered by Slots/UX/Retriever during scoping)

- ✅ Capacity formula: `breadth // len(themes)` for FAN_OUT (already computed by Slots, Fillers doesn't recompute).
- ✅ Thematic partitioning / priority: already computed by Slots (theme-score-derived), Fillers just consumes.
- ✅ Slot semantics vocabulary: posture-centric (`direct_answer`/`thematic_exploration`/`external_context`), locked, UX+Slots aligned.
- ✅ Rewritten-query correlation: `rewritten_query` is a real field on `AnswerSlot`, populated via an `id()`-based mapping that survives Slots' internal score re-sort (verified in code by Retriever).

## Open Design Questions

None outstanding as of this version — flag here if cross-agent sign-off surfaces new ones.

## What's explicitly OUT of scope for Fillers

- Slots' slot-derivation logic (Step 1d, closed/in sign-off — Fillers consumes, never recomputes)
- Pool's candidate-fetching (Step 2, closed — Fillers consumes, never re-fetches/re-embeds)
- Router's ranking/ordering/bandit-logging (Step 4, separate module)
- Synthesis/Contract/Timing (further downstream)

## Process — same rigor as every prior module

1. **First real task:** fork a dedicated Fillers-owning session once this spec clears sign-off — no such session exists yet.
2. Build with verify-before-trust discipline — same as Gate/Reformat/Structure/Pool/Slots.
3. Test: unit tests on pure assignment logic + characterization test (deterministic output) + eval-bank angle if Eval flags this as NUMBER-MOVING (new code, same weight class as Pool/Slots — likely yes).
4. Cross-agent sign-off: Chat, Eval, DB, TECH (UX already contributed the design and effectively signed off by finalizing it).
5. Track in a live scoreboard (`fillers-simulation-tracker.md`), same pattern as every other module.
6. Report back to Retriever once signed off — unblocks Router (Step 4, already kicked off, waiting on this).
