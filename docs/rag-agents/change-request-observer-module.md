# CHANGE REQUEST — Add Observer Module, Make Router Two-Phase

**✅ FULFILLED 2026-07-24 — the module exists, but built against a simpler, later design than this proposal originally described.** Observer was added (the core ask here — a confidence-check between Fillers attempts and the retry decision), but the "make Router two-phase" framing and the mechanical `ObserverVerdict{satisfied, confidence_score, speed_budget_exceeded}` shape this doc originally proposed sign-off for were both superseded before being built (first by a Bayesian-confidence redesign, itself abandoned, then by the actually-built discrete-verdict design). See `observer-module-spec.md` (v2) for what's real. This file stays as the historical record of why the module was proposed in the first place — that reasoning still holds — not as a description of what got built.

**Status (as originally proposed):** PROPOSED — awaiting explicit sign-off from Chat/UX/Eval/DB/TECH before any spec or code changes land. Nothing described here is built or edited yet.
**Raised by:** Ananth, formalized by Retriever, 2026-07-23.
**Why this needs a formal change-request, not a quiet edit:** `module-sequence.md` already carries every architect's sign-off ("This is the contract Retriever builds to"). This proposal changes Router's contract in that doc, not just adds a new module — that's a revision to something already ratified, and needs the same rigor as the original ratification, not a silent patch.

---

## 1. What's being added: Observer (new module, between Fillers and the loop-continue decision)

**The gap it closes:** Structure's `ResourcePosture` already carries `max_attempts` and `confidence_bar` — clear signals that a retry/escalation loop exists (mirrors legacy's untimed escalation loop, `corpus_search_agent.py:3137-3399`). But no doc assigns ownership of *checking* whether an attempt succeeded and deciding whether to retry. Putting that logic directly in `orchestrator.py` would bloat Retriever's own code with real business logic it was never meant to hold (orchestrator's whole design principle: "thin glue, no business logic of its own").

**Observer's job:** after each Fillers attempt for a slot, check the result against Structure's `confidence_bar` (and whatever else "was this good enough" requires). Reports satisfied/not-satisfied. If not satisfied and attempts remain, the orchestrator advances to the next strategy in Router's ladder (see §2) and loops Fillers again for that slot.

**Not Observer's job:** deciding what to retry with (that's Router's ladder, planned upfront) or doing the actual fill (that's Fillers).

## 2. What's changing about Router: two phases, not one

**Current signed-off contract** (`module-sequence.md` row 4): Router's input is `filled_shape` (i.e., Router only runs after Fillers has already filled everything, once).

**Proposed contract — Router now runs twice, for different reasons:**
1. **Early phase (NEW):** per slot, before the loop starts, plan an ordered strategy ladder (e.g., `a>b>c>d`) sized to that slot's `max_attempts` (from `resource_posture`). This tells the orchestrator/Fillers what to try, in what order, if earlier attempts don't satisfy Observer.
2. **Late phase (UNCHANGED from original spec):** once every slot is Observer-satisfied or attempts are exhausted, Router does its originally-scoped job — rank across slots, produce `chosen_slot`/`confidence`/`alternatives`, log the one bandit row (`rag_query_decisions`, ONE-WRITER, unchanged).

**Not changing:** Router still never decides what to retrieve in the sense of doing the actual retrieval — Pool already fetched everything once, up front (see §4, why Pool is unaffected). The "ladder" is about which slice of the already-fetched pool / which fill strategy Fillers tries next, not a new retrieval call.

## 3. Loop mechanics (for completeness, not itself a new module — orchestrator-owned)

Per slot: Fillers attempts a fill using the current rung of Router's ladder → Observer checks confidence against `confidence_bar` → satisfied: slot done; not satisfied + attempts remain: orchestrator advances to the next rung, loops Fillers again → attempts exhausted: slot marked under-filled, moves on. Once all slots resolve (satisfied or exhausted), Router's late phase runs once across all slots.

## 4. What's explicitly NOT affected

- **Shape (Gate/Reformat/Structure, all closed)** — untouched. `ResourcePosture.max_attempts`/`confidence_bar` already exist and already anticipated exactly this use; nothing about their own logic changes.
- **Pool (closed, 5/5)** — untouched. Pool's whole design already fetches the union ONCE, up front — the target-structure-spec's own punch-list even names this exact scenario ("L5: memoize pool across escalation attempts... pool reuse can shift chunks — measure"). The ladder/loop consumes Pool's single fetch differently per attempt; it does not trigger new Pool fetches.
- **Slots (mid-sign-off, 2/5)** — one additive field only (see §5). No redesign.

## 5. What Slots needs: NOTHING — Router's early phase produces its own new structure, not a mutation

**REVISED 2026-07-23, per UX's sign-off review.** The original §5 proposed adding `strategy_sequence: list[str]` directly onto `AnswerSlot`, populated by Router. UX correctly flagged this as a contract violation: it would mean Router *mutates* Slots' output, breaking the immutable/read-only pattern every other module in this chain follows (Fillers doesn't mutate Pool's output — it produces a new `FilledShape`; Structure doesn't mutate Reformat's output — it produces a new `StructureResult`). Slots' `AnswerShapeResult` should stay exactly what Slots produced, untouched, forever.

**Corrected design: Router's early phase produces its own new, separate output — a `RoutingLadder`, keyed by `slot_id`:**
```python
@dataclass
class SlotLadder:
    slot_id: str                          # matches AnswerSlot.slot_id, correlated by id, not mutation
    strategy_sequence: list[str]          # e.g., ["a", "b", "c"], sized to that slot's max_attempts

@dataclass
class RoutingLadder:
    """Router's early-phase output — one ladder per slot. Does NOT touch AnswerShapeResult."""
    ladders: list[SlotLadder]
```

**Slots needs ZERO changes** — no new field, no touch to `AnswerSlot` at all. Fillers' Input Contract needs a THIRD input alongside `PoolResult` + `AnswerShapeResult`: this `RoutingLadder`, correlated to slots via `slot_id` (same string-key correlation pattern already used elsewhere, e.g. Chat's own normalizer decoupling vocab across a seam). Router's late phase reads `FilledShape` (from Fillers) to do its final ranking — it does not need `RoutingLadder` echoed back, since it's the one that produced it.

## 5.5 Chat's approval note — carry into Observer's kickoff spec

Chat approved (✅ 2026-07-23) with one non-blocking but important note: the retry loop adds internal latency per attempt, and while the fan_out SSE event covers the "still working" UX signal, **Structure's `speed_budget` must be an explicit hard ceiling Observer enforces on the loop, not just an informational label.** A slow-corpus query with `max_attempts=3` could otherwise push total turn latency past Chat's SSE stream timeout and kill the connection. Observer's kickoff spec must address this directly, not leave it to be discovered at load-test time.

## 6. Process — same rigor as every prior spec change

1. Circulate this change request to Chat/UX/Eval/DB/TECH (+ Broadcast for tracking) for explicit approval before any doc or code edits.
2. On approval: update `module-sequence.md` (Router's row + new Observer row), add the additive field to `AnswerSlot` (land before Slots' sign-off closes, not as a breaking change after).
3. Draft Observer's own kickoff spec (same format as every other module: input/output contract, what's undesigned, process, open questions) and fork a dedicated Observer-owning session.
4. Amend Router's kickoff briefing (already sent to "4c Router") to reflect the two-phase role.
5. Build Observer + Router's early-phase logic with the same verify-before-trust discipline as every prior module.
