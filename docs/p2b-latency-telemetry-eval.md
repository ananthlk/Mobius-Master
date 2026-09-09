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

**Eval's answer:**

> _(write here)_

---

## Q2 · What does "fast mode" fix, and what stays variable?

Ananth's proposal is to run the bank in fast mode — one question, then the series. I
don't know what that pins and what it leaves free. Whatever stays variable is
uncontrolled between runs, which decides whether run-to-run differences mean anything.

**Eval's answer:**

> _(write here)_

---

## Q3 · How many runs before a difference is signal?

Same question you'd ask of a lift measurement. Without it, "we got faster" is anecdote.
Note the tails are wide — flash p50 4,669ms vs p95 15,608ms — so a single run of 22
questions may not separate a real improvement from ordinary variance.

**Eval's answer:**

> _(write here)_

---

## Q4 · Do you own the runner, or specify it for chat to build?

Either works. Asking rather than assuming.

**Eval's answer:**

> _(write here)_

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

**Eval's answer:**

> _(write here)_

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
