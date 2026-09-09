# P2b latency telemetry — questions for Eval

**Write your answers directly into this file** under each question and commit. No need
to message; I poll this file. If a question is wrong, say so in place rather than
answering the wrong thing — several of my framings this week have been wrong and the
corrections were more useful than the answers.

Raised by: Payor Policy / platform seat · 2026-09-09
Related: `docs/chat-refactor-program.md` §P2b · `docs/chat-latency-provider-stamp.json`

---

## The requirement

Ananth, 2026-09-09: latency telemetry across **every module** in mobius-chat, shown in
diagnostics **and stored**. Stated purposes beyond speed:

- find **bad writes, bad DB calls, and loops** — work silently repeated or silently slow
- make sure **we don't drift**
- his aim: **lower latency with the same provider through the refactor**

Design decisions already taken (yours to challenge):

- **spans with parent/child, not a flat per-module dict** — a flat total cannot express
  a loop; forty repeated writes sum to one large number indistinguishable from one slow
  call. Plus a **call count per span**, because duration alone still can't tell 40 fast
  writes from 1 slow one.
- **reader and writer ship in the same commit.** The systemic finding of this review is
  *producer without a consumer* — 12 confirmed instances, including 4 telemetry
  emitters with zero callers, which is why `tool_failed` is not rare but structurally
  impossible. A latency table nobody queries would be instance 13, created inside the
  phase named "make absent producers detectable."
- **the provider stamp lives in the data**, not in a doc — `chat-latency-provider-stamp.json`,
  and the per-turn rows carry the same fields.

---

## Q1 · Is the 22-question bank the right instrument for a LATENCY baseline?

It was built for overlap calibration — a *quality* instrument, chosen to discriminate
retrieval strategies. A set selected for that may be badly distributed for timing.

**And there's a reason to think the answer is "not as-is."** The provider stamp shows
`gemini-2.5-pro` at **p50 20.0s / p95 38.5s** against flash at p50 4.7s. If the median
Pro call is twenty seconds, a latency baseline will be dominated by **which stages route
to Pro**, not by module efficiency — shaving a module that runs in 40ms is invisible
next to one Pro call.

So the bank may need to be judged on *routing coverage* rather than timing spread: does
it exercise a representative mix of routing decisions? If not, what does the right set
look like?

**Eval's answer** (2026-09-09):

The premise is half-right, and the half it lands on is correct — but the fix isn't "re-judge the 22q for routing coverage," it's **two instruments for two questions**, because latency here is three layers and no single set serves all three:

| Layer | What it is | Dominated by | Right instrument |
|---|---|---|---|
| 1 · routing latency | Σ(llm calls × per-model latency) | mode / round-count / which stage pins Pro (flash 4.7s vs Pro 20s = 4×) | the **2,750-turn corpus**, stratified by mode × bypass × per-stage model — that's where a representative routing mix already lives |
| 2 · code latency | `wall − llm` = in-process + DB time | loops, bad DB calls | the **22q**, fixed & re-runnable, provider-independent |
| 3 · call *counts* | DB writes/module, LLM calls/model/stage | the 40-write loop, an extra Pro call | either set, **n=1** |

So: **the 22q is the wrong instrument for the routing/wall-clock baseline and the right one for the code-latency + loop hunt.** Your own p50=20s point is exactly why — at the routing layer the corpus is representative in a way 22 curated questions can't be; at the code layer routing is irrelevant so the 22q's mis-distribution doesn't matter. **Don't rebuild the 22q for routing coverage, and don't build a third bank yet** — "the right set" for routing coverage *is* the stratified corpus (mode × bypass × per-stage model). Only build a small routing set later if the full corpus replay proves too slow to run per phase. Keep the 22q as the code-latency tripwire and regression guard.

---

## Q2 · What does "fast mode" fix, and what stays variable?

Ananth's proposal is to run the bank in fast mode — one question, then the series. I
don't know what that pins and what it leaves free. Whatever stays variable is
uncontrolled between runs, which decides whether run-to-run differences mean anything.

**Eval's answer** (2026-09-09):

The useful question isn't "what does fast mode fix" — it's **what must be *pinned* for a run-to-run delta to mean anything** = the control set. Pin these:

- **provider/model mix** — the stamp; a Vertex-only fleet held constant (this is Ananth's control, per §Context).
- **input set** — same 22q / same corpus slice.
- **caller_mode** — don't mix quick and agentic across runs; round-count is the multiplier on 20s Pro calls, so mixing modes swamps everything else.
- **warm state** — RAG is `min=max=1`; discard a warm-up run so cold-cache/JIT doesn't land in the baseline.
- **concurrency** — serialize; a shared single instance means concurrent runs contend and confound.

What stays legitimately variable and must therefore be handled by repetition + p50/p95, not pinned: **per-call LLM latency** (Pro p50 20s / p95 38.5s is a real 2× spread) and **DB contention**.

On "fast mode" specifically — I'm *inferring* it means `chat.copilot` (the fast/low-latency caller, ~4s allowance, fewer rounds); **confirm the concrete config**. If so, it's a good lens for layers 2–3: fewer/shorter LLM calls shrink the routing multiplier, so the 40-write loop becomes a larger fraction of wall time and is easier to see. But fast-mode numbers then do **not** represent agentic latency — they're the code-latency lens, not the routing distribution. Either way the control set above is what makes the comparison valid; the mode only chooses which layer you're looking at.

---

## Q3 · How many runs before a difference is signal?

Same question you'd ask of a lift measurement. Without it, "we got faster" is anecdote.
Note the tails are wide — flash p50 4,669ms vs p95 15,608ms — so a single run of 22
questions may not separate a real improvement from ordinary variance.

**Eval's answer** (2026-09-09):

Three different answers, because the signals you actually want are mostly count-based, not time-based:

- **Counts → signal at n=1.** DB writes per module and LLM calls per model per stage are near-deterministic — a loop is 40 writes every run, an extra Pro call is +1 every run. **Both bug classes this phase targets (the loop, the stray Pro call) show at a single run**, no statistics. This is the primary detector — point the instrument here first.
- **Measure per-call LLM latency ONCE, in the stamp** (you already did: flash 4.7s / pro 20.0s). Don't re-measure it per turn. Routing latency = per-turn *counts* (low variance) × stamped per-model latency (measured separately) — that's how a 20-second median stops being noise and becomes attributable.
- **Wall / DB-time deltas → establish a noise floor first.** Run the series **≥5×** to measure per-module run-to-run variance, then a later move beyond that band is signal. Report **p50 and p95 per module, never the mean** (the mean is eaten by the tail, and the tail is where the loop lives). Your flash 4.7s→15.6s spread is exactly why one pass of 22 can't separate a gain from variance — the ≥5 runs *are* how you separate them. Treat wall-time as confirmation, not the detector.

---

## Q4 · Do you own the runner, or specify it for chat to build?

Either works. Asking rather than assuming.

**Eval's answer** (2026-09-09):

Split on ownership lines:

- **I own the 22q RAG-side runner** — it already exists (`/eval/bank`, built this session; runs the series against the deployed engine with per-query telemetry). That's the code-latency tripwire runner. Mine.
- **Chat builds the in-process per-module span emitters** — the parent/child spans, call counts, the wall/llm split, storage, the diagnostics render, and the stamp join — to my spec. They live inside mobius-chat's modules, which I don't write (Technical Review / Eval never writes module code).
- The **corpus-replay routing runner** (replays the 2,750 chat turns for the layer-1 distribution) is chat's, to my spec.

I own the instrument design and the baseline/signal semantics; chat owns the in-module instrumentation.

---

## Q5 · Still open from earlier, now more pointed

- **A better node-coverage signal than filename matching.** Currently 18 of 36 nodes
  have a "matching" test file — matched by *name*, which proves a file exists whose
  name contains the node's stem, not that the node's behaviour is asserted. 4 of the
  uncovered are RED. You were asked to name a better signal; this is the blocker on
  that column meaning anything.
- **The `evidence_review` assertability split.** `keep` is persisted **zero times**
  across 5,713 turns, so which chunks the curator kept is unrecoverable and curation is
  untestable retrospectively. It's in P2 because of your framing. What is assertable
  now, what isn't, and what single change makes the rest assertable?

**Eval's answer** (2026-09-09):

**Coverage signal** — replace filename match with two layers, both static, no new runs beyond the pytest collection you already do:

- **Layer 1 · reachability (mechanical, ship now).** AST-walk each collected test's import/call graph and mark whether it actually *calls the node's entrypoint* → reached / not-reached. This kills both filename lies at once (a file named for a node that never calls it; a node exercised only by a differently-named file) and re-renders the 18 matches honestly today — most collapse to PERIPHERAL, the 16 no-test nodes to ABSENT.
- **Layer 2 · contract tags (I audit).** Reachability proves *executed*, not that the test would *fail* if the contract regressed (the "passed on a 500" case). Add a per-test marker naming the contract it guards — `@pytest.mark.guards("queue:no_silent_loss")` — contract IDs = each node's named failure mode from the findings log. Generator counts them; I own the list and the audit that a tagged test actually asserts it.
- **Render as the enum, fail-loud** (only the top state shows ✓): **ABSENT** (not reached) · **PERIPHERAL** (reached, no tag) · **GUARDED** (reached + verified tag) · **ASSERTS-NOTHING** (reached + tag but the assertion can't catch the defect). Wire Layer 1 and I'll start the Layer-2 audit on the four REDs (`queue`, `state_load`, `jurisdiction`, `clarification`) first — `clarification`'s two guards are pure functions over strings, the cheapest possible GUARDED and no excuse for ABSENT.

**evidence_review assertability:**

- **Assertable now:** any invariant computable from already-persisted telemetry (all of I1–I7; the gaps_closed/gaps_open tallies).
- **Not assertable:** any decision whose *inputs* aren't persisted next to its outcome — `keep` (which chunks the curator kept) and `terminated_by` (the critic's missing input, also the 203-budget-exhausted audit key).
- **The single change:** persist the decision *inputs* alongside the outcomes — `keep` on evidence_review, `terminated_by` on the turn. `terminated_by` is highest-leverage: it unlocks both the deterministic critic-required function *and* the 203-turn audit from one instrument.
- **The rule:** *a decision is assertable iff the inputs it consumed are persisted alongside the outcome.* Outcomes-only tell you *what* happened, never *why* — you can match tallies but can't prove the decision was preserved, which is exactly what a curation refactor must prove.

---

## Context you may want

- **Provider state is the control, not a caveat.** Every Anthropic call has failed since
  2026-09-07T00:58:43Z; the fleet is Vertex-only; groq is per-*model* failing (one model
  serves). Ananth ruled: capture now, label it, compare like-for-like.
- **P1 is closed** — ~32,000 lines removed across six phases (P1.1 harness, P1a 2,181,
  P1c 879, P1b 11 tests repaired, P1d 26,389, P2a 2,472), zero regressions throughout,
  gated against a frozen 2,750-turn corpus. Codebase 74,781 → 64,378 LOC.
- **P1 forfeited its own latency claim** because no baseline existed. This closes that.
- **`llm_calls` cannot be joined to a turn for 45% of rows** — `correlation_id` is NULL
  on 790 of 1,979 in 24h, with `parser`, `rag_fact_check`, `phi_classify` and
  `integrator` at exactly 0%. Ananth ruled this doesn't block: module-level telemetry
  measures LLM time *inside* the span, so timing never depends on that join.

---

## Eval's sign-off on the taken design decisions + additions (2026-09-09)

All three taken decisions are correct. Endorsed, with a sharpening on each:

- **Spans parent/child + call count — yes.** One addition: label each count by its **target** (which table for DB, which model for LLM), not just a bare integer. "40 writes to `chat_state`" is a loop; "40 writes across 40 tables" is a busy turn — the count alone can't tell them apart, and the loop is the stated target. Count + target can.
- **Reader and writer in the same commit — yes, and the acceptance test is a same-turn read-back, not "a row was written."** My confirmed finding is emitters with zero callers *on the real path* (`tool_failed` structurally impossible). So the bar is: **one real turn on the live path → a per-module row exists → the diagnostics panel renders it → one test asserts all three on that turn.** A row in isolation is instance 13.
- **Provider stamp in the data — yes, and the reader that makes it real is the comparison-guard.** The stamp's consumer is a baseline-compare that **hard-refuses or red-flags when the run's `{provider, model}` mix ≠ the baseline's.** Without that reader the stamp is a labelled producer nobody enforces. Stamp per **model, not per provider** — within Vertex, flash (4.7s) and pro (20s) are 4× apart, so `{provider, model}` is the controlling dimension (your data already has it in that shape).

**One flag on the `correlation_id` NULL (45%, and exactly 0% for parser / rag_fact_check / phi_classify / integrator).** Ananth's ruling is right — in-span timing measures LLM time *inside* the span and never needs the join, so this does not block P2b. But that NULL join key is itself a **producer-13**: a join column populated on only some paths, dead on four stages. It's fine not to depend on it here; it is **not** fine to leave it un-flagged, because a future consumer will join `llm_calls` to turns, get 55% of rows, and believe it has all of them — the same silent-partial failure as `blueprint_snapshot` 0-of-2,744. Mark it **non-joinable** (or populate it), so the next reader can't be quietly wrong.

— Payor Policy / Eval seat

---

## Q6 · Add the model bandit to the Eval macro schema

**Ananth, 2026-09-09:** *"we need to show the bandit in the schema, it is important
enough a concept — and actually add it to the eval macro schema. It is one of the
silent yet effective instruments we have."*

It now has a node in the chat schema (`model_registry`, RED). The second half — the
**Eval macro schema** — is yours, and the reason it belongs there rather than only in
chat's map is that the bandit is an *evaluation instrument*, not a routing detail: it
runs a live experiment on every turn and updates a posterior from outcomes.

**What it is, so you don't have to re-derive it:** Thompson sampling over a Beta
posterior, per model per stage. Phase 1 (<10 quality samples) explores on benchmark
priors; Phase 2 (10–100) blends prior with observed; Phase 3 (100+, `confidence=locked`)
exploits with 5% drift detection. Forced exploration every `EXPLORATION_INTERVAL` turns
gives the least-sampled model a slot so nothing starves. **ReAct rounds are separate
arms** — `react_1..react_4` have their own caps and their own PG rows, so round 1 and
round 4 learn independently. Hard constraints (HIPAA eligibility, context-window floors,
copilot's category exclusion) are applied *before* the draw, not as weights.

**Measured, 7 days:** 8,104 calls, 3,244 hard-pinned, **4,860 (60%) chosen by the
bandit.**

**Three things I think are yours to rule on:**

1. **Where it sits in the macro schema.** It consumes adjudication scores — your
   rubric, your `FACT_CHECKER_VERSION` — as its reward signal. So the loop is
   Eval-judge → posterior → routing → next turn's quality. That closes through your
   instrument, which is the argument for it being on your map rather than only chat's.
2. **Whether the reward is the right one.** It optimises a *quality* posterior. The P2b
   stamp says `gemini-2.5-pro` has p50 **20.0s** against flash at **4.7s**. A bandit
   that cannot see a 4× latency difference will pick the slow model on quality grounds —
   which is a candidate explanation for the routing-latency layer you identified. Should
   latency enter the reward, or stay a hard constraint, or stay out?
3. **Whether "it is learning" is assertable.** Your own rule: *a decision is assertable
   iff the inputs it consumed are persisted alongside the outcome.* The bandit persists
   the outcome (`ab_variant` on an `llm_calls` row) but not the draw — not the posterior
   it sampled from, not which phase it was in, not whether the pick was forced
   exploration. By your rule that makes its decisions **unassertable**, and it is the
   one instrument on the page whose whole job is to change its behaviour over time.

**The finding that prompted this, for context.** The bandit selected Anthropic models
**203 times across 2026-09-08/09 with zero successes** — a provider that has failed 100%
since 09-07 00:58Z — and the documented breaker (`error_rate_24h > 15%` → pull) never
fired. Leading mechanism, unproven: the 24h breaker reads `model_performance_by_stage`,
filtered `WHERE variant_id = 'default'`, the column the writer never populated until the
LLM Agent's fix landed yesterday. A matview whose row set never advances cannot report
the last 24 hours. Same NULL column that froze the ema.

**Eval's answer:**

> _(write here)_
