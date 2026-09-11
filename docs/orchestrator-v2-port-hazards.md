# Orchestrator v2 — port hazards

**The undocumented load-bearing half of `react_loop.py`.** Supplied by the chat
seat, 2026-09-11, in answer to *"what in the 6,451 lines do you know is
load-bearing and undocumented?"*

**None of these is in a docstring, and several actively contradict one.** This is
the register a rewrite loses if nobody writes it down — so it is written down.

---

## The ten

### 1 · 🔴 `max_it` grows mid-turn — a `range()` loop silently drops every extension

The loop is `itertools.count()` plus an explicit bound check, **not
`range(max_it)`** — deliberately, so an extension can raise the bound *between*
iterations.

**The in-file comment says a `range()` version is "byte-for-byte equivalent."**
It is equivalent **only while extensions never fire.** A v2 written as
`for i in range(rounds)` drops every extension, **and the tests pass.**

### 2 · 🔴 The appeals REST path is unreachable, and the code asserts the opposite

`react_loop.py:3070` states the five appeals tools *"bypass MCP and call the
appeals REST API directly."* **They do not.** The registry fallback at `:2759`
ends in an unconditional `Return` at `:2873` — **200 lines before** the appeals
branch at `:3073`.

**A v2 that reproduces the documented behaviour would CHANGE production
behaviour** — and would be right to. **Decide it deliberately; do not inherit
it.**

### 3 · The completion-extension gate has no name

~60 lines inline in the loop body — no module, no class, no function. **A
symbol-based inventory of what to port will not find it.** It is the second
extension writer.

### 4 · `_pp_pre_directive` already shapes two things

`agent_role` (`:4761`) and `reasoning_depth` (`:4803-4810`). **v2 must reproduce
both or round behaviour changes for reasons unrelated to the governor** — and
the change would look like a governor regression.

### 5 · `is_guidance_round` fires at six interacting sites

`:4694, 4967, 4975, 5009, 5056, 5061`. One guards a prose-looks-like-answer
branch, another the round label. **Porting the function without all six call
sites changes when guidance mode engages.**

### 6 · `ctx.thinking_chunks` is mutated in place, never assigned

Three `append` sites in `orchestrator.py` alone. **A v2 that builds a fresh list
and assigns it breaks the envelope stream** — which is now how the promise
reaches the trace.

`[DESIGN]` Same shape as the prompt seat''s detector false positive: an
assignment sweep reports every in-place-mutated container as dead. **Mutation is
invisible to the tools we have been using to find dead code.**

### 7 · ContextVars do not cross the thread boundary

react spawns daemon threads; the worker runs the turn off the main thread when
`signal.alarm` is unavailable. **The chat seat paid for this twice today** on the
logging correlation id.

**v2''s clock-as-input purity requirement has a twin: any ContextVar the loop
depends on must be PASSED, not read.**

### 8 · `_skill_success` guards on a foreign string

`text.startswith("Unknown skill")` — chat''s own literal from `registry.py:313`.
**A remote server says `"Unknown tool"`.** And `registry.py:312` never sets
`success=False`, so **that string comparison is the sole mechanism** turning an
unknown skill into a failure — not the backstop its comment claims.

### 9 · 🔴 `ReactRetryGuard._is_zero_result` cannot fire for MCP tools

It requires `no_sources` **and** an empty sources list. **The MCP adapter
attaches a self-citing `SourceRef` on success, so the escape hatch is always
satisfied.** Tool exhaustion is **structurally unreachable for ~34 tools.**

**This lands directly on the governor''s exit-mode design.** `CAPABILITY`
requires knowing that *every attempt ran and returned nothing* — and for those
34 tools **the zero-result detector cannot say so.** So a genuinely unanswerable
question routed to an MCP tool would exit as **BUDGET** and **offer a
continuation that can only fail again**, which §3 of `governor-exit-modes.md`
calls the worst available outcome.

`[OPEN]` **`attempted_by` must record the payload check, not the tool''s own
success flag.** The adapter''s self-citing `SourceRef` — text that is a prefix of
the answer — must count as **zero sources**, the same rule already written for
the quality leg.

### 10 · The two extension writers disagree on the deadline, latently

Critic: inline `os.environ.get("MOBIUS_TURN_DEADLINE_S", "120")`, `+25` margin.
Governor: `90` with `FINALIZE_MARGIN_S = 5.0`. **Both currently read `300` from
the deployed env**, so the disagreement is invisible **and would surface only if
the var were unset** — exactly the kind of thing a rewrite "simplifies" into
production.

---

## Round records — `turn_rounds`, and the reason is sharper than sampling

`[READ]` verified asymmetry:

```
turn_spans          sampled BOOLEAN NOT NULL, sample_rate NUMERIC   ← a row CAN be absent
turn_attestations   no sampling columns at all                      ← a row CANNOT be absent
```

`sample_rate()` reads `MOBIUS_SPAN_SAMPLE_RATE` and defaults to `1.0` — **so it
is 1.0 by configuration, not by construction.**

> **Do not take the sampling exemption. An exemption is a rule that exists as
> agreement between a table and whoever remembers to keep an env var at 1.0.**

Same shape as the two extension writers, and the four comment-only rules found
this week. **A column that can make a row absent must not exist on a table that
backs a conformance number** — *remove the ability, do not set it to 1.*

**And "don''t invent something new" does not apply here.** That instruction is
against inventing a new *surface*. **Spans are diagnostics that may be dropped;
attestations are accounts that may not.** Putting a conformance number in a
droppable table is not reuse, it is a **category error** — and
`turn_attestations` already established that this fleet keeps the two apart.

**Decision: `turn_rounds`, keyed `(correlation_id, round_index)`, no sampling
column. Its absence is the guarantee.**

---

## Why the two exit criteria are the real gate — stated at full strength

**Every other metric improves when v2 does less.** Latency, cost and conformance
all move the right way if v2 quietly stops reaching tools.

**Only two move the wrong way:**

- **no rise in `CAPABILITY` exits** — a rise means v2 stopped reaching tools
- **`gaps_closed` per turn ≥ v1** — v2 must not buy fewer answers for its latency

**That asymmetry is what makes them the gate and everything else the dashboard.**
