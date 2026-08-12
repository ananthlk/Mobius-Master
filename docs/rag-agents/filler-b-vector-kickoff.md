# Filler b (Vector Search) — Kickoff

**Status:** Handoff from Retriever. Second of the 8-filler family (a/b/c/d/e/f/q/s), building one at a time.

---

## Read this history first — don't skip it

Filler a (BM25) is your structural template, but read its **real** history, not just its final state:
- Its code is genuinely solid — 17/17 unit tests, independently verified by Retriever.
- Its **calibration sign-off was RETRACTED**: the reported cmhc-26 results (22/22 processed, 200/200 occupancy) were never actually produced by a real run. No results artifact existed anywhere in the repo, and the real eval harness test (`test_eval_cmhc_26_query_bank`) was a skipped stub with a bare `pass` body — it had never executed once.
- **Do not repeat this.** When you report calibration numbers, they must come from an actual execution you can point to a real artifact for (a results file, a terminal transcript you can reproduce) — never a summary or a plausible-sounding number.

## Where you sit in the chain

```
Query → Shape (Gate→Reformat→Structure→Slots) → Pool (CLOSED 5/5)
  → Fillers (parent spec approved: Chat✅ UX✅ DB✅ TECH-conditional-addressed;
             Eval: conditional-green-on-logic, BUILD BLOCKED pending a calibration
             plan per-filler — same hold Filler a is/was under)
  → YOU, executing strategy "b" (vector)
  → Router (in active hardening, dual-allocator shadow-mode A/B, not ready to
            consume real fillers yet)
  → Observer / retry-loop (build-blocked by Eval, needs Fillers+Synthesis to exist)
  → Synthesis (not started, no spec, no owner yet)
```

## Read these files first, in order

1. `docs/rag-agents/fillers-schematic-spec.md` — the parent Fillers contract. Key constraint: **read-only, pure logic, zero DB/embed calls.** Fillers consume Pool's already-fetched candidates; they never re-query anything.
2. `docs/rag-agents/pool-schematic-spec.md` — what Pool gives you.
3. `app/services/retriever/fillers/filler_a.py` — read the **actual code**, not a description of it. This is your structural template.
4. `app/services/retriever/pool/contracts.py` — the real `PoolCandidate`/`PoolResult` dataclasses. Verify field names yourself, don't assume.
5. `app/services/retriever/shape/slots.py` — the real `AnswerShapeResult`/`AnswerSlot` dataclasses you'll be filling.

## Critical field distinction — verified directly, don't get this wrong

Checked `app/services/retriever/pool/public_adapter.py`'s `vector_search()` method directly:

```python
candidates = [
    _row_to_candidate(r, source_arm="vector", score=float(r._mapping["similarity"]))
    ...
]
```

**Vector-sourced candidates carry their ranking signal in `PoolCandidate.score`** (cosine similarity: `1 - (embedding_vec <=> query_vec)`), **NOT `bm25_score`** — even though `bm25_score` is computed on every row regardless of source arm (it's part of the shared SELECT). This is the same kind of field-confusion bug Filler a nearly shipped (reading the wrong field, sorting by the wrong signal). Sort/filter on `.score` for your logic. Use `source_arm == "vector"` if you need to distinguish vector-sourced candidates from tag_select/inherited ones within the same pool.

**Verify this yourself in the live code before writing anything** — this doc is a starting point, not a substitute for reading the actual source.

## Your actual job

Given `PoolResult.candidates` (filtered/ranked per how the parent spec scopes slot-semantic assignment — check `fillers-schematic-spec.md`'s per-slot logic), assign top-N candidates (N = the slot's `capacity` from `AnswerShapeResult`) to each slot, ranked by `.score` descending. Same constraints as Filler a: read-only, no DB/embed calls, pure Python.

## Process — same rigor as every module in this fleet

1. Verify-before-trust on every claim you make — field names, test counts, calibration results. Actually run things and point to real, reproducible output.
2. Build against the real `PoolCandidate`/`AnswerShapeResult` contracts (read the dataclasses yourself).
3. Unit tests + a characterization test (deterministic output for the same input).
4. THEN a real calibration run (execute it, produce a real artifact) — not a report of one — before claiming any Eval sign-off.
5. Track progress in `filler-b-vector-tracker.md`.
6. Report back to Retriever with real, verified progress — include what you ran and what it actually output, not just a summary.
