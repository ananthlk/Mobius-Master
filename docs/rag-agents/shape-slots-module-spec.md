# SHAPE / Slots Module Spec (Step 1d) — v1

**Status:** DRAFT — kickoff artifact only. No code written yet. Prepared by Retriever for handoff.
**Owner:** to be assigned ("Shape:Slots Agent," fourth sibling under Shape, alongside Gate/Reformat/Structure — all three of which are CLOSED).
**Why this module exists:** a real gap surfaced while scoping Fillers (Step 3) — Structure was deliberately built WITHOUT a slot model, because none existed anywhere in the fleet to build against. That gap was flagged and left open at the time (`shape-structure-module-spec.md` §4.1: *"answer_shape + slots — no real design exists anywhere in this fleet yet. Legacy is a bare string hint."*). Fillers cannot assign Pool's candidates to "slots" that don't exist. Ananth's explicit decision 2026-07-23: **add this as a proper Shape sub-step, same rigor as Gate/Reformat/Structure — not a shortcut inside Fillers.**

---

## 1. Where Slots sits in the chain

```
Query → SHAPE [ Gate (DONE) → Reformat (DONE) → Structure (DONE) → Slots (THIS MODULE, NEW) ] → POOL (DONE) → FILLERS (blocked on this) → ROUTER → SYNTHESIS → CONTRACT → TIMING
```

Gate classifies. Reformat translates contour→posture. Structure resolves `ResourcePosture` (breadth/confidence_bar/max_attempts/speed_budget). **None of the three produce an answer structure** — they produce *how hard to search*, not *what shape the answer should take*. Slots is genuinely new work, not a refactor of existing logic (same class of module as Pool — Gate/Reformat/Structure refactored legacy logic, Pool and Slots build new code).

Pool already shipped and is 5/5 signed off — it does NOT depend on Slots (verified: `PoolResult`/`PoolCandidate` carry no slot references, Pool consumes `StructureResult.rewritten_queries[]` + `resource_posture` only). **Slots sits between Structure and Fillers, not between Structure and Pool** — Pool and Slots can be thought of as parallel consumers of `StructureResult`, both feeding Fillers.

## 2. Input — what Slots receives

`StructureResult` (verified live in `shape/contracts.py`): `query`, `rewritten_queries[]`, `posture` (`ReformatPosture`), `resource_posture` (`breadth`/`confidence_bar`/`max_attempts`/`speed_budget`), `reason`, `structure_ms`.

Plus, per the original request shape: the legacy `answer_shape` string hint (`corpus_search_agent.py:2939` — e.g. `"essay"`/`"structured"`/`"binary"`/`"any"`), which today is the ONLY existing signal about desired answer structure anywhere in the system. **First task: read this field's actual current usage/callers before assuming what it means or where it comes from in a live request** — don't invent semantics for it.

## 3. Output — the real Fillers input contract

A structure that tells Fillers what "slots" to fill and how many chunks each wants. Per `module-sequence.md`'s sketch (Step 1 output: `answer_shape, slots[]`) and UX's draft Fillers spec (input assumptions, now known to be fictional but a reasonable target shape to design toward): each slot needs, at minimum:
- `slot_id` — stable identifier
- `slot_semantics` — what kind of content this slot wants (e.g. `direct_answer`, `context`, `edge_case`) — **this vocabulary needs real design, not just copying UX's placeholder strings**
- `capacity` — target chunk count for the slot, **should derive from `resource_posture.breadth`**, not be hardcoded per slot type
- Whatever else Fillers genuinely needs to do "pure" scoring/assignment without doing its own semantic reasoning — the design goal is Fillers stays "read-only, pure slot-fill" (per `module-sequence.md`'s constraint), which only works if Slots gives it enough structure to fill mechanically.

**Explicitly NOT Slots' job:** actually assigning Pool's chunks to slots (that's Fillers). Slots defines the shape of the answer; Fillers populates it.

## 4. What's genuinely undesigned — Slots' real work

1. **How many slots, and what determines the count/type?** Does a PRECISE-posture query get exactly 1 slot (direct_answer)? Does FAN_OUT get one slot per theme (up to `MAX_FANOUT_THEMES=4`)? This is the first real design question — likely `posture` (from Reformat, carried through Structure) is the primary driver, since posture already encodes "how many distinct sub-questions does this query actually have."
2. **Slot semantics vocabulary** — UX's draft guessed `direct_answer`/`context`/`edge_case`. Is that the real taxonomy, or does it need its own design pass (same rigor as Gate's 6-contour taxonomy)? Don't inherit a placeholder as if it were designed.
3. **Capacity derivation from `resource_posture.breadth`** — same "don't hardcode, derive from Structure's signal" principle Pool followed for its own per-strategy widths.
4. **What legacy's bare `answer_shape` string hint actually does today** — verify its real callers/usage before deciding whether Slots subsumes it, extends it, or ignores it as dead weight.
5. **Relationship to FAN_OUT's `fanout_themes[]`** (from Reformat, does NOT currently pass through Structure — verify) — if FAN_OUT posture implies one slot per theme, Slots may need Reformat's `ReformatResult` directly, not just `StructureResult`, since theme detail may not have survived into Structure's narrower output. **Check what actually passes through before assuming.**

## 5. What's explicitly OUT of scope for Slots

- Gate/Reformat/Structure's locked logic (all three closed, don't touch)
- Pool's candidate-fetching (Step 2, closed, doesn't consume Slots' output)
- Fillers' actual chunk-to-slot assignment logic (Step 3, blocked on this module, but the assignment algorithm itself is Fillers' job, not Slots')
- Router/Synthesis/Contract/Timing (further downstream)

## 6. Process — same rigor as Gate/Reformat/Structure/Pool, don't skip steps

1. **First task before any code:** read legacy's `answer_shape` field usage directly (don't assume), and confirm with Ananth/UX whether posture (not something new) is the right primary driver for slot count/type — this is the equivalent of the H0019 Gate-vs-Reformat placement question, worth resolving explicitly before building.
2. Verify-before-trust discipline, same as every prior module: restart dev proxy before trusting latency, check actual code before assuming a field/behavior exists.
3. Test: unit tests on slot-derivation logic (pure — no DB expected here, same as Structure), plus an eval angle if there's real behavior to score (may need Eval's input on whether slot-shape correctness is measurable at all, or only downstream via Fillers/Synthesis quality).
4. Cross-agent sign-off: **UX especially** (already drafted a Fillers spec assuming a slot shape — needs to be the first to align once Slots' real design lands, since their draft's Input Contract will need revising), Chat, Eval, DB (if any), TECH.
5. Track in a live scoreboard (`shape-slots-simulation-tracker.md`), same pattern as every other module.
6. Commit incrementally, module-prefixed filenames in the shared `shape/` directory (e.g. `slots.py`) — ping before touching `shape/contracts.py` (the one shared file), same near-miss precedent as Gate/Reformat's `narrate.py` collision.
7. Report back to Retriever once signed off — this unblocks Fillers (Step 3), which unblocks Router (Step 4, already kicked off and waiting on this).

## 7. Lessons from every prior Shape/Pool build — apply here too

- **Don't guess at what fields "should" exist** — verify `StructureResult`/legacy `answer_shape` directly, same mistake already made once by UX's Fillers draft (assumed a slot model existed that didn't).
- **This module is genuinely new design, not refactor** — treat it with the same weight Pool got (new code = more scrutiny), not the lighter touch Gate/Reformat/Structure got when reusing legacy logic.
- **Keep the sign-off tracker current in real time** — went stale before, TECH caught it once already.
- **Module-prefixed filenames, ping before touching shared `shape/contracts.py`.**
- **PHI discipline: fail-closed** — if slot semantics ever echo raw query content for diagnostics, same never-persist-raw-content rule applies.

## 8. Open architecture questions to resolve FIRST (before kickoff proceeds)

1. **Is `posture` (from Reformat/Structure) the right primary driver for slot count/type**, or does Slots need a genuinely new classification pass of its own?
2. **Does FAN_OUT's per-theme structure (`fanout_themes[]`) actually survive from Reformat through Structure into what Slots receives**, or does Slots need `ReformatResult` directly? Verify, don't assume.
3. **What does legacy's `answer_shape` string hint actually do today** — dead weight, or something Chat/Synthesis genuinely reads downstream that Slots needs to preserve/extend?
