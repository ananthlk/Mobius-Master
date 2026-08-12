# Filler e (Fast Exit) — Tracker

**Owner:** Filler e Agent (under Retriever)
**Status:** CLOSED 2026-07-23 — no `filler_e.py` exists or is needed. Confirmed by Retriever: this is an orchestrator-level terminal path, not a Fillers-package module. Converged with Filler q's identical independent finding.

## Resolution

`posture ∈ {DECLINE, CLARIFY, CLARIFY_REPHRASE}` → Slots already emits 0 slots, Pool/Router/Fillers/Observer are all already skipped (verified live in `orchestrator.py:122-137`). Retriever is building a new orchestrator branch that produces a terminal result **directly from `ReformatResult`** (`decline_reason`/`clarify_questions`/`reason`) — bypassing the whole chain, since none of those modules have anything to do for these postures. Synthesis will read either a real `FilledShape` (normal path) or a new terminal-result type (decline/clarify path) — two input shapes, not one contract forced to fit both.

Session scope closed. Optional follow-on offered by Retriever: review the terminal-result shape once drafted.

**Separate, real, still-open gap (not this session's scope, flagged to Ananth via Retriever):** legacy's `fail_fast_gate` covered 4 reasons — `phi_detected`/`jailbreak`/`self_referential`/`no_domain_match`. New Gate's contour taxonomy only covers `no_domain_match` (→ `OUT_OF_SCOPE`). Per-query PHI-in-text, jailbreak, and self-referential-question detection do not exist anywhere in the new pipeline today (verified: zero grep hits in `app/services/retriever/`). This is real and unrelated to Filler e's (non-existent) scope.

---

---

## Deliverable 1: What triggers strategy "e" in the new pipeline? — ANSWERED, verified in code/docs

**Short answer: currently, nothing does.** The new pipeline has no code path that routes a *slot* to strategy "e", because the two things that would need to produce one — a real per-query fail-fast signal, and slots that survive to reach Router — don't line up the way legacy did.

### 1. Legacy "e" was a whole-query short-circuit, not a per-strategy choice

`corpus_search_agent.py:398-451` (`fail_fast_gate`) runs a **pre-flight check** before any pool build, on 4 reasons:
- `phi_detected` (regex over query text — member IDs/SSN/DOB/names)
- `jailbreak` (prompt-injection patterns)
- `self_referential` (meta-questions about the system itself)
- `no_domain_match` (well-formed query, zero d-tag match)

`corpus_search_agent.py:4341-4357`: `if strategy_id == "e" and verdict and verdict.fail: return CorpusSearchAgentResponse(chunks=[], ...)`. Legacy has no slot concept at all (`StrategyId = Literal["a","b","c","d","e"]` — 5 strategies total, verified at the top of `corpus_search_router.py`). "e" firing means the *entire query* short-circuits, once, globally — not "this slot gets strategy e while other slots get a/b/c."

### 2. New Gate's contour taxonomy only covers 1 of legacy's 4 fail reasons

Verified via `grep -rn "phi_detected\|jailbreak\|self_referential\|fail_fast_gate" app/services/retriever/` → **zero hits**. Gate's 6-way contour (`shape-gate-module-spec.md` §3) is purely D/J/P tag-match + corpus-probe based. Only `OUT_OF_SCOPE` ("zero tags matched, query IS well-formed") lines up with legacy's `no_domain_match`. There is currently no per-query PHI-in-query, jailbreak, or self-referential check anywhere in the new Shape pipeline — a real gap, separate from Filler e's scope, flagging below.

### 3. OUT_OF_SCOPE → DECLINE → **zero slots**, one step before Router would ever see it

- `shape-reformat-module-spec.md` §3: Gate `OUT_OF_SCOPE` → Reformat posture `DECLINE` ("hard boundary, no external fallback attempted").
- `shape-slots-module-spec-v1.md` §4: Reformat `DECLINE` → Slots emits **slot count: 0** ("No answer slots; Chat declines gracefully"). Same for `CLARIFY` (missing_domain/missing_jurisdiction) → 0 slots.
- `app/services/retriever/orchestrator.py:122-137` (code, not spec): confirms this live — for DECLINE/CLARIFY/CLARIFY_REPHRASE, `resource_posture.breadth == 0`, so `pool_results` stays `[]` and **Pool never runs**. Comment at line 104-108 confirms Router/Fillers don't exist in code yet ("Router onward doesn't exist yet").

So a DECLINE query never produces a slot for Router to route in the first place — the short-circuit already happens a full step earlier (at Slots) than legacy's did (at strategy dispatch). There's no "slot routed to e" case reaching Fillers under the current spec chain.

### 4. Router's own build spec doesn't include "e" in its allocation loop either

`router-module-spec.md` §1 casually lists the full alphabet "a>b>c>d>e>f>s" in prose, but the actual greedy algorithm in `router-build-spec.md` §3 (`for strategy in [a, b, c, d, f, s]`) **omits "e" entirely** from the loop that assigns strategies to slots. Router's own spec doesn't define what routing a slot to "e" would even mean.

## Consequence — two real options, not a guess, flagging to Retriever/Ananth

1. **Filler e is currently unreachable / not needed as "a filler."** If DECLINE/CLARIFY queries never reach Fillers (0 slots, Pool skipped), there's nothing for a filler to fill. The "fast exit" formalization the handoff described may belong entirely to the orchestrator's existing 0-slots handling (already built) plus Chat's decline rendering — not a new module in the fillers/ package at all.
2. **OR** legacy's 3 missing fail reasons (phi_detected/jailbreak/self_referential) are a real gap that needs rebuilding somewhere upstream (most likely a Gate-adjacent pre-flight check, not Fillers) — and if/when that lands, its "fail" verdict is the thing that should short-circuit the whole query, same shape as legacy, still never reaching Fillers as a per-slot strategy.

Either way: **strategy "e" is not a per-slot Fillers concern under the current spec.** Recommend confirming with Retriever whether Filler e should be scoped down to "port the 3 missing pre-flight checks (PHI/jailbreak/self-referential) as a Gate-adjacent module" (real, needed work) rather than "a Fillers sibling that never gets invoked" (the original framing).

## Process notes
- Verify-before-trust applied throughout — every claim above is grepped/read directly, not assumed.
- No calibration bank started (per handoff's flag-don't-assume note) — moot until scope is confirmed, since there's no code path yet to calibrate.
- Next: awaiting Retriever's call on the two options above before writing any code.
