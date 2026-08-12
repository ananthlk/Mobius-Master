# SHAPE / Structure Module Spec (Step 1c) — v1

**Status:** DRAFT — kickoff artifact only. No code written yet. Prepared by Retriever (Shape's manager) for handoff, following the exact process Shape:Gate and Shape:Reformat used.
**Owner:** to be assigned (a new sub-agent under Retriever — "Shape:Structure Agent," third sibling to Shape:Gate and Shape:Reformat).
**Scope of this spec:** Structure only — the final Shape sub-phase, takes `ReformatResult` and assembles the actual contract Pool consumes. Does not touch Gate's locked classification, does not touch Reformat's locked posture/fan-out logic, does not do Pool's actual search.

---

## 1. Where Structure sits in the chain

```
Query → SHAPE [ Gate (DONE) → Reformat (TECH-review pending) → Structure (THIS MODULE) ] → POOL → ROUTER → FILLERS → SYNTHESIS → CONTRACT → TIMING
```

Gate classifies (6 contours). Reformat translates contour → posture + `rewritten_queries[]`/clarify-questions/external-reason/decline-reason. **Structure's job, per the original design doc:** "set up for downstream — emits the single contract the rest of the chain reads." It's the thinnest of the three Shape sub-phases by original design intent, but it's the one that actually produces what Pool is contractually allowed to consume — everything before it is Shape-internal.

## 2. Input — what Structure receives

The full `ReformatResult`: `posture`, `rewritten_queries[]`, `fanout_themes[]`, `clarify_questions[]`, `external_reason`, `decline_reason`, `reason`, `reformat_ms`, `segment_ms`. Confirmed live: `ReformatResult`'s own docstring currently says *"Do not wire into Structure/Pool until signed"* — Structure is exactly the thing that ends that hold.

## 3. Output — the real Shape→Pool contract (per original design, §1c)

- **`rewritten_queries[]`** — already produced by Reformat, passes through (or gets finalized/validated here)
- **`answer_shape` + `slots`** — per the legacy field (`corpus_search_agent.py:2939`, string hint: "essay"/"structured"/"binary"/"any") plus whatever real slot structure Structure introduces — this is explicitly flagged in the current-state doc as the piece with **no real design today** ("shape has NO slot model yet — just the escalation-budget loop"). Undesigned, first real task.
- **Scope/auth context** — which of the 4 federated pool sources (public NOW, org/instant-rag/cache reflected per the `SourceAdapter` seam design) this specific user/request may see. **Undesigned, second real task** — ties directly to the scope-guard P0 principle from the original Pool design ("federate, never leak").
- **Flags** — PHI, freshness, scope overlays (mentioned in Gate's original contour-taxonomy overlays section but never actually threaded through as output fields — check if Gate's `GateResult` carries anything usable here, likely not, would need passing through)
- **Posture** — carries forward from Reformat, exact→lean per original design

## 4. What's genuinely undesigned (Structure's real work, not just plumbing)

1. **`answer_shape` + `slots`** — no real design exists anywhere in this fleet yet. Legacy is a bare string hint from the request. What should the actual slot structure be? Ties to what Synthesis (much further downstream) will eventually need to compose an answer.
2. **Scope/auth context assembly** — how does Structure know which of the 4 pool sources (public/org/instant-rag/cache) a given user/org is allowed to see? This likely needs input from outside Shape entirely (org context, auth claims) — Structure may need a NEW input beyond just `ReformatResult`, e.g. an org/auth context object passed in from whatever calls the chain (chat, likely). **Check with whoever owns request-level auth/org context before assuming this is Shape-internal.**
3. **PHI/freshness/scope flags** — need to confirm what's already available from Gate (the PHI overlay was part of the original contour-taxonomy design — did Gate ever actually implement it as an output field, or was it deferred? Check `GateResult` directly before assuming a PHI flag exists anywhere to pass through).

## 5. What's explicitly OUT of scope for Structure

- Gate's classification logic (`gate.py`'s `_classify` — locked)
- Reformat's posture-decision/fan-out/clustering logic (`reformat.py`'s `_dispatch`/`_fan_out` — locked once TECH signs off)
- Pool's actual corpus search (Step 2, separate module)
- Router/Fillers/Synthesis/Contract/Timing (all separate, downstream modules)

## 6. Process — same as Gate and Reformat, don't skip steps

1. **First task before any code:** confirm with Ananth whether `answer_shape`/slots and scope/auth context are genuinely Shape's job, or whether Structure is thinner than the original design implied (e.g., if scope/auth context actually belongs to whatever orchestrates the whole chain — see `orchestrator.py`, Retriever's own top-level entry point — rather than Shape itself). **This is a real architecture question worth resolving before building, same class of question as the H0019 Gate-vs-Reformat placement call.**
2. Build with real DB/system verification at every step — same discipline as Gate and Reformat (verify-before-trust, restart the dev proxy before trusting latency numbers, etc. — see lessons list below).
3. Test: unit tests on pure structure-assembly logic + DB-integration tests + an eval bank if there's real behavior to test (may be thinner than Gate/Reformat's banks if Structure turns out to be mostly plumbing).
4. Cross-agent sign-off, same process: UX (emit schema — new key, avoid collisions with `shape_gate`/`shape_reformat`), Chat (does the final contract need anything Chat-specific), Eval (if there's real logic to score), DB (any new query patterns), TECH (final structural sign-off, same 2-round rigor).
5. Track in a live scoreboard (`shape-structure-simulation-tracker.md`), keep it current in real time.
6. Commit to git incrementally, following the module-prefixed filename convention (e.g. `structure.py`, `structure_narrate.py` if narration is relevant here at all — may not be, since Structure may not need user-facing narrative the way Gate/Reformat do).
7. Report back to Retriever once TECH signs off — next stop is Pool (Step 2), the first module outside Shape entirely.

## 7. Lessons from Gate + Reformat's builds — apply here too

- **Verify-before-trust, every number** — dev cloud-sql-proxy degrades after long uptime, produces misleading latency; restart + re-measure with EXPLAIN ANALYZE before trusting anything that looks slow.
- **Don't guess at what fields "should" exist** — check `GateResult`/`ReformatResult` directly for what's actually available before assuming a flag/field exists to pass through.
- **Land test-suite additions immediately** — don't build a bank and forget the unit tests (TECH caught this exact gap during Gate's review).
- **Keep the sign-off tracker current in real time** — went stale once already, TECH caught it.
- **PHI discipline: fail-closed, not "redact before persisting"** — anything echoing raw query/user data must never be persisted, not rely on a future caller remembering to scrub it.
- **Module-prefixed filenames, ping before creating new files in the shared `shape/` directory** — a real near-miss already happened (Reformat's `narrate.py` briefly overwrote Gate's).
- **Don't silently assume cross-module wiring** — the `thinking_trace` ownership question (does Reformat's narrate() belong there) is still unresolved between Gate, Reformat, and UX; Structure should get an explicit answer before building anything narrative-shaped, not repeat the same assumption-without-confirmation mistake.

## 8. Open architecture question to resolve FIRST (before kickoff proceeds)

**Is `answer_shape`/slots and scope/auth context genuinely Shape's responsibility, or does some of this belong to the orchestrator (`orchestrator.py`, Retriever's own top-level entry point) instead?** Structure was designed, in the original doc, as part of Shape — but Shape is specifically the "reason, cheap, no DB-heavy work" phase per its own definition, and scope/auth context assembly might need request-level context (org, auth claims) that doesn't naturally flow through Gate→Reformat→Structure's internal chain at all. Worth resolving this explicitly with Ananth before assuming the original design's module boundary is still right — same instinct as questioning the H0019 placement rather than building on an assumption.
