# Filler s (Payor Platform Fact Store) — Module Spec v1

**Status:** DRAFT — ready for cross-agent sign-off (Chat/Eval/DB/TECH), same process every prior module used.
**Owner:** Filler s agent, reports to Retriever ("4 - Retriever").
**Companions:** `fillers-schematic-spec.md` (parent contract), `filler-s-payor-kickoff.md` (design history/rationale — read that for the *why*, this doc is the *what*), `filler-s-payor-tracker.md` (live status).

All open design questions from the kickoff doc are resolved as of this version:
- Architectural fork: **live-trigger**, same resolution as Filler d — confirmed by Retriever.
- Gate signal: ported marker-word heuristic is the best available signal in the new pipeline — confirmed directly against Gate's real `Contour` vocabulary, no better option exists.
- Query embedding: **v1 ships tags-only, no `embedding` sent** — deliberately deferred (see §6) after "3a - Payor platform" identified a real regression risk in the naive fix. Reuse-Pool's-embedding was independently verified as technically correct (same model/dimension/task_type) but is bundled into the same deferred fast-follow, not v1.

---

## 1. Module Identity

- **Role:** Live external call to mobius-payor's certified Payor Fact Store, for the query's primary factual-answer slot only.
- **Sequence:** Step 3 (Pool → **Fillers** → Router), same step as a/b/c/d — one of the 8-strategy filler family, fires only when a slot's current `RoutingLadder` rung is `"s"`.
- **NOT a `PoolResult` consumer** in the way a/b are — `PoolResult` is corpus-only (`pool-schematic-spec.md` §2, PUBLIC-via-`SourceAdapter`). The fact store is a separate, external, higher-confidence source. `pool_result` is still accepted as a parameter (matching a/b's signature convention, and so `routing_ladders`/future orchestrator wiring stays consistent across all fillers) but its `candidates[]` are not read by this filler's logic.
- **Signature convention:** mirrors a/b's actual shipped signature shape (`fill_shape_*(pool_result, shape_result, ..., routing_ladders=None) -> FilledShape`, operating over the whole `AnswerShapeResult`) rather than Filler d's still-unresolved per-slot proposal — a/b are the only fillers with real, shipped code, and both currently ignore `routing_ladders` (v1, marked "unused" in their own docstrings). Filler s follows the same precedent rather than inventing a new per-slot invocation contract for a fleet-wide orchestrator question ([[project-filler-d-web-agent]] flagged this as open and unresolved) that isn't mine to settle unilaterally.

## 2. Input Contract

- **`PoolResult`** — accepted, unused for v1 (see above).
- **`AnswerShapeResult`** — real dependency. Filler s only acts on slots where `slot_semantics == "direct_answer"` (covers both the EXACT-posture `direct_answer` slot and the CLARIFY_REPHRASE `best_guess` slot — both real, confirmed `slot_semantics` values in `shape/slots.py`). Slots with `thematic_exploration`/`external_context` semantics are left untouched by this filler — a fact-store hit answers one query's one fact, it doesn't have a natural per-theme or external-context analog. This is an intentional scope limit, not an oversight: legacy's strategy-s served the *whole query* as a single answer; the new pipeline's closest equivalent is the single `direct_answer`-semantics slot.
- **`raw_query: str`** — the actual query text (or `direct_answer` slot's own text if it differs — v1 uses the top-level `raw_query`, matching legacy's single-query-per-call model; no FAN_OUT-style rewritten-query fan-out applies here since fact-store lookups aren't theme-specific).
- **`tag_matches: list[str]`** — the query's `d:`/`p:`/`j:` tag codes (from Gate's `GateResult`), needed for both the gate condition (§4) and the request payload (§3).
- **`routing_ladders: list[RoutingLadder] | None`** — accepted for signature consistency, **unused in v1** (same as a/b).

## 3. Real Request/Response Contract (verified against the payor service's own code, `mobius-payor/app/fact_store.py`)

**Endpoint:** `POST {MOBIUS_PAYOR_URL}/api/skills/v1/fact_query` (`MOBIUS_PAYOR_URL` env var, default `https://mobius-payor-ortabkknqa-uc.a.run.app`).

**Request (v1, tags-only):**
```json
{
  "query": "<raw_query>",
  "d_tags": ["..."],
  "p_tags": ["..."],
  "j_tags": ["..."],
  "intent_scope": null,
  "k": 5
}
```
No `embedding` key in v1 (see §6 — deliberately deferred).

**Response (real shape, `fact_store.py:468-472`):**
```json
{
  "hit": true,
  "served": {
    "record_type": "atomic",
    "predicate": "...",
    "answer_text": "...",
    "value": {},
    "source_ref": {"doc_id": "...", "url": "...", "page": 1, "quote": "..."},
    "authority_level": "...",
    "scope": null,
    "freshness": {"last_verified_at": "...", "valid_until": "...", "stale": false},
    "cert": {"status": "accepted", "grades": {"retrieval": 0.9, "synthesis": null}},
    "score": 0.83
  },
  "shortlist": [...],
  "gate": {"payer_key": "...", "applied": true, "excluded_n": 12},
  "blend": {"alpha": 0.5, "beta": 0.5, "tau": 0.75, "version": "..."},
  "verify": null,
  "telemetry_id": "uuid"
}
```

**Two real, verified corrections vs. legacy's read of this contract, neither ported forward:**
1. Legacy reads `served.get("payer_key")` — this field does not exist in `served` (confirmed in `fact_store.py:434-446`; `payer_key` lives at top-level `gate.payer_key`). Payor has since added `payer_key` to `served` additively (server-side fix, pending their own deploy) — Filler s reads `served.get("payer_key")` and gets it correctly once that ships; reads `None` harmlessly until then (same as legacy did, just for the right reason now).
2. `intent_scope` is sent as `null` in v1 — no scope-resolution logic exists upstream in the new pipeline yet; matches legacy's behavior exactly, not a regression.

## 4. Gate Condition (ported from legacy, known limitation intact — see kickoff doc for the full analysis)

Only call the fact store when **all** of:
1. A payer tag matched: `any(t.startswith("j:payor.") for t in tag_matches)`.
2. The query is not conceptual: `not any(marker in raw_query.lower() for marker in _CONCEPTUAL_MARKERS)` — ported verbatim (`"philosophy", "approach", "why does", "why do", "how does", "how do", "explain", "tell me about", "overview", "describe", "understanding", "background on", "rationale"`).
3. The target slot's `slot_semantics == "direct_answer"` (§2 — new to this pipeline, not in legacy, since legacy had no slot concept at all).

If the gate fails, Filler s makes no HTTP call and returns the slot untouched (occupancy 0, `under_filled=True` if capacity > 0) — same as a miss, so Observer's downstream logic doesn't need to distinguish "gate rejected" from "fact store missed."

**Known, unsolved limitation (ported as-is, not fixed here):** this heuristic still over-fires on non-stored payers, payer-agnostic queries, and some process/conceptual intents even with the marker-list guard — documented in `[[project-payor-fact-store]]` memory as a PARKED issue. Confirmed directly (via Gate's real `Contour` vocabulary) that no better signal exists anywhere in the new pipeline today. Not this filler's job to solve; flagged for whoever eventually revisits query-intent classification fleet-wide.

## 5. Output Contract — `FilledChunk` mapping (one synthesized chunk per hit)

| `FilledChunk` field | Source | Notes |
|---|---|---|
| `chunk_id` | `f"fact_{telemetry_id}"` | Synthetic, matches legacy's naming intent (`fact_store_{telemetry_id}`). |
| `document_id` | `served["source_ref"]["doc_id"]` if present, else same synthetic id as `chunk_id` | Real corpus doc when the fact traces to one. |
| `text` | `served["answer_text"]` | |
| `document_status` | `None` | No Product-Awareness reality-gating concept applies to a fact-store hit. |
| `content_sha` | `None` | Not load-bearing for v1 (no dedup-across-attempts need identified yet). |
| `source_type` | `"fact_store"` | Matches legacy. |
| `tags` | `{"d_tags": [...], "p_tags": [...], "j_tags": [...]}` (the request's own tag_matches, passthrough) | Minor; not consumed by anything critical in v1. |
| `is_neighbor` | `False` | No neighbor concept applies. |
| `original_score` | `served["score"]` (real blend score) | Real signal, not a constant (unlike c/d, who had none) — still flows through Observer's existing percentile-within-pool normalization unchanged. |
| `assignment_reason` | `"fact_store_hit"` | New value, documented independently (no forced shared `assignment_reason` enum across fillers, per c/d's precedent). |
| `url` | `served["source_ref"]["url"]` if present | **Blocked**: `FilledChunk` has no `url` field yet in `contracts.py` (same shared gap Filler c/d already have open with DB) — omit until it lands, do not invent a workaround field. |

**Miss (`hit=false`) or HTTP/network error:** slot gets 0 chunks assigned (`occupancy=0`, `under_filled=True` if `capacity>0`). No `force_s`/fallthrough special-casing — Observer's existing per-slot Bayesian loop decides whether to try the next `RoutingLadder` rung. Simpler than legacy by construction (legacy needed this special-casing because strategy-s ran as a query-wide fast-exit *before* any other routing; the new pipeline already generalizes "try next strategy on miss" at the orchestrator level).

## 6. Deliberately deferred — the embedding-send fast-follow (NOT v1)

v1 sends **no** `embedding` field, matching legacy's current, already-calibrated, already-live operating point exactly (tags-only blend, `base = tag_overlap`).

**Why not v1, even though the technical fix (reuse Pool's query embedding) is verified correct:** "3a - Payor platform" identified that sending `embedding` rescales the payor service's blend formula itself (`base = overlap` → `base = 0.5·overlap + 0.5·vec`), which would silently drop some currently-good serves below `τ`, not just fix the known over-serve cases. This needs Eval's α/β/τ re-sweep against a fresh baseline, bundled with dropping RAG's `_CONCEPTUAL_MARKERS` band-aid (redundant once vec_sim vetoes conceptual mismatches directly) — one measured, sequenced change, not an independent ship. Eval has been looped in directly on this dependency.

**Fast-follow scope (tracked, not designed further here):** once Eval's re-sweep is scheduled, (a) Pool needs to expose `query_embedding` on `PoolResult` (new contract gap, same shape as c/d's `url` gap — verified same model `gemini-embedding-001`, same dimension `vector(1536)`, same task_type `RETRIEVAL_DOCUMENT` on both sides, so reuse rather than a fresh embed call is correct once Pool exposes it), (b) Filler s adds `embedding` to its request payload, (c) RAG drops `_CONCEPTUAL_MARKERS`, (d) Eval re-sweeps α/β/τ. All four ship together.

## 7. Emit Contract (diagnostic-only, matches `fillers-schematic-spec.md` pattern)

```
emit.fillers:
  fillers_decision: "fact_store_query"
  gate_passed: bool
  hit: bool | None          # None if gate_passed=False (never called)
  telemetry_id: str | None
  slots_filled: int         # 0 or 1
  under_filled: int
  fact_store_ms: int | None # None if gate_passed=False
```

## 8. Constraints

1. **Live external call, not read-only** — explicit, documented exception to the parent Fillers spec's "zero DB/embed side effects" (same exception c/d already have). No local DB access from RAG's side (unlike Filler d, no `db` param needed).
2. **Scoped to `direct_answer`-semantics slots only** — no thematic/external-context handling.
3. **Tags-only v1** — no `embedding` in the request (§6).
4. **Bounded blast radius** — the gate condition (§4) means this fires only on payer-tagged, non-conceptual queries targeting the direct-answer slot; not every query pays the HTTP round-trip.
5. **Timeout matches legacy** — `15.0s` (`corpus_search_agent.py:3869`'s `httpx.AsyncClient(timeout=15.0)`), same value, not re-derived.

## 9. Asks per collaborator

- **"3a - Payor platform"** — already reviewed the request contract informally (confirmed both findings in §3 and the §6 deferral); will ping with this doc per their ask.
- **Eval** — already looped in on the §6 re-sweep dependency; NUMBER-MOVING calibration plan for v1 (tags-only) still needed, same cmhc-bank pattern as every prior filler.
- **Chat/DB/TECH** — standard structural/contract review, same as every prior module. DB specifically: the `url` field gap (§5) is shared with c/d, not new.

## 10. Process, unchanged from every prior module

Spec → cross-agent sign-off (this doc) → build (`filler_s.py`) with verify-before-trust discipline → unit tests + real calibration run with a real artifact (standing requirement) → `filler-s-payor-tracker.md` kept live → report to Retriever.
