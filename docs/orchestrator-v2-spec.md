# Orchestrator v2 — spec, routing, and exit criteria

`[RULED]` Ananth, 2026-09-11: *"it may be easier to create a chat 2.0 version so
we don''t mess around with the existing version… this is just the orchestrator
redo, and anyway we wanted to do this because it is not modular — the current
react is 6k+ lines and is a mess."* Plus: *"move the prompt blocks to prompts and
we can build it and take it away from the card."*

---

## 1. Why replace rather than refactor — the evidence, not the instinct

```
react_loop.py                    6,451 lines · 61 functions
tests/test_react_split_phase_1i  "Phase 1i — lock in the react_loop.py split.
                                  Ratchets react_loop.py LOC"     cap: 2,560
```

**A prior split set a ratchet and the file is now 2.5× past it.** That test is
one of the two currently failing and is carried in the known-failing baseline.
**Incremental refactoring of this file has a track record here and it is
negative.**

Symptoms catalogued in one evening: 8 publish call sites across 2 reachable
terminals, **1 terminal unreachable with 3 green tests on it**, **16 context
fields with no writers**, **2 extension granters with different deadlines**
(120/+25 vs 90/5.0), `refined_query` inert across 17 reads while costing a
`chat_state` write per turn.

---

## 2. It is NOT chat 2.0 — everything but the loop is already outside it

| concern | already lives | v2 action |
|---|---|---|
| tool selection | Tool Manifest, own repo, `estimate()` built | **call it** |
| prompts | `prompt_blocks` / `prompt_compositions` | **read from DB only** — §4 |
| model selection | `model_registry` Thompson + `latency_budget_ms` pre-filter | **bound it, never choose** |
| attestation | `turn_attestations`, migration 065, **live** | **write it** |
| gaps | `thread_gaps`, migration 067, spec''d | **read at state_load, write at turn end** |
| the answer card | `integrate.py` / `format_response*` | **untouched in v2** |

**What is left is the decision loop — and it is ~15 formulas** (`docs/governor-system-logic.md` Part II), not 6,451 lines.

---

## 3. What makes this safe now and was not safe this morning

**The attestation measures v1 and v2 on the same metric, on live traffic.**
`promised` vs `delivered`, `kept`, `in_band`, `exit_mode`, per turn. So v2 is
**routable and comparable**, not a leap of faith. That capability did not exist
twelve hours ago.

### 🔴 The one trap — two orchestrators must never both be writers

**Route a turn to exactly one. Never fork and reconcile.** Today we deleted two
extension granters that agreed until they didn''t, and collapsed three
`INSERT INTO prompt_blocks` paths into one. **A second orchestrator sharing
write state with the first is that defect at maximum scale.**

Routing is a single decision at POST, recorded on the attestation as
`orchestrator_version`. **No turn is ever handled by both.**

---

## 4. Prompts — invert the source of truth `[RULED]`

**Confirmed: there are two sources today.** `react/prompts.py` holds
`REACT_CRITICAL_RULES_TEXT`, `REACT_RESPONSE_SHAPE_TEXT`,
`REACT_FORMAT_RULES_TEXT`; `react_block_seed.py` seeds `prompt_blocks` from
them; `test_prompt_block_seed_drift.py` exists **specifically to catch the two
diverging.** That drift test is the tell: **a test whose job is to keep two
sources of truth in agreement is evidence there should be one.**

It has already bitten — the prompt seat published `critical_rules` v7 through
the admin path and it drifted from the Python constant **by a trailing
newline**, caught only because that test existed.

**v2 reads prompts from `prompt_blocks` ONLY.** No prompt text in v2''s code.

**But do not delete the Python constants in the same change.** They are today''s
seed and today''s fallback. **Same sequencing rule as everything this week:
nothing comes out until its replacement is demonstrably in place.** They are
removed when v2 is the only orchestrator, not when v2 first runs.

**And "take it away from the card":** v2 composes the answer from
`card.shape_schema` + a `how` block, both in `prompt_blocks` — **not from card
logic in `integrate.py`.** The card layer renders; it does not instruct.

---

## 5. Routing — start where the evidence is strongest

`[MEASURED]` **1,239 of 1,514 turns have zero gaps open at round 1 — 82%.** Those
need `FRAME → EXPLORE → COMMUNICATE` and nothing else.

| phase | v2 handles | v1 handles |
|---|---|---|
| **R0** shadow | nothing live — v2 computes, v1 decides, both emit, equality asserted | everything |
| **R1** | single-round `fast` | everything else |
| **R2** | all `fast` | `normal`, `thinking` |
| **R3** | `fast` + `normal` | `thinking` |
| **R4** | all | — |

**R0 is not optional.** Shadow on live traffic, not replay — replay proves
equality only on the traffic you replayed, and **six of seven moved decisions
read mode, elapsed, or round number**, which is exactly where untested
combinations live. Purity requirement: **the clock is an input, never read
inside**, or two runs cannot be compared.

---

## 6. Exit criteria per phase — measured, not judged

Advance only when **all** hold over ≥ 200 turns in the phase:

| criterion | threshold |
|---|---|
| **conformance** `in_band` rate | **≥ v1''s**, same tier, same window |
| **no new breach class** | every v2 breach has a v1 counterpart shape |
| **attestation integrity** | `turns == rows`, 0 duplicates, `queue_wait ≥ 0` on every row |
| **exit_mode distribution** | no rise in `CAPABILITY` vs v1 — a rise means v2 stopped reaching tools |
| **gap closure** | `gaps_closed` per turn **≥ v1** — v2 must not buy fewer answers for its latency |
| **zero `unknown` outcomes** | an unrouted exit is a defect, not a tolerance |

**Roll back on any single failure.** Routing is one flag; rollback is the same
flag. **That is the reason to route rather than fork.**

---

## 7. What v2 does NOT do — scope fence

- **Does not rewrite prompts.** The incident knowledge lives in the blocks —
  H0036 via commit `4268736`, the 2026-08-17 clarification finding, the
  Aspire/MMA fabrication postmortem. **The loop is the safe thing to replace
  precisely because the knowledge is not in it.**
- **Does not touch the enricher or the card renderer.**
- **Does not change the promise or its bands.**
- **Does not pick models** — bounds the bandit, never overrides its draw.
- **Does not delete anything from v1** until v1 is retired.

---

## 8. Build order

```
1  thread_gaps + identity            ← everything reads it
2  re-derive posture constants       ← today's [GUESS] values become numbers
3  v2 skeleton + posture machine     ← reads prompt_blocks, calls modules by contract
4  R0 shadow on live traffic         ← equality asserted, v1 still decides
5  R1 single-round fast              ← 82% of turns are this shape
6  R2 → R4 on the §6 criteria
7  per-module A/B arms (7a) — one variable each, same question set
8  wholesale v1-vs-v2 — LAST, when a bad result has a short suspect list
9  retire v1; delete the Python prompt constants, the dead terminal,
   the 16 writerless fields, the second extension granter
```

**Step 7 is where every deletion catalogued this week lands — after its
replacement is proven, never before.**
