# Governor contract — step 2

Answers to the chat seat's four questions, 2026-09-10. Verified claims marked.

---

## 1. The contract shape — right, but it is FIVE things of THREE kinds

Ananth's line: *gaps closed · within time · within cost · at the desired quality
· without errors.*

Listing those as five peers invites a governor that trades them against each
other. **They are not the same kind of thing:**

| | term | kind | tradeable? |
|---|---|---|---|
| **gaps closed** | the **objective** — what we maximise | goal | it is the thing being bought |
| **time · cost · quality** | the **promise** — the envelope | constraint | **yes, against each other** |
| **without errors** | an **invariant** | precondition | **NO** |

**The distinction is load-bearing.** You can spend cost to buy quality; that is
the entire point of the tiers. **You cannot spend errors to buy anything.** If
"without errors" sits in the same list as cost, some future directive will trade
it — a governor that accepts a 2% error rate to hit a latency target is
obviously wrong, and nothing in a flat five-term list says so.

**So: errors are a precondition on every directive, not a term in the budget.**
A directive that risks an error is invalid regardless of what it buys.

### And "gaps closed" is the same hole as recall
It is the only term with **no measure** — §8 says exactly that about recall, and
**operationally they are the same quantity**: a gap that stays open is a recall
failure. This means the governor's load-bearing input and the promise's missing
leg are **one problem, not two.** Worth knowing before either is scoped
separately.

---

## 2. Critic discretion — run it only when its verdict can change what happens next

Today: `_pp_enabled AND agentic AND rn < max_it AND ledger > 0`. `[READ]`

**Drop `agentic`.** Mode is a *tier*, and it is standing in for *expected
difficulty*. **A hard question on `normal` needs the critic more than an easy
one on `agentic`.** Difficulty is a **forecast**, which is exactly what step 2
introduces — so replace the mode test with the forecast, not another proxy.

> **CORRECTION, same day.** An earlier version of this paragraph cited the
> deployed rows — *"thinking delivered a worst case of 8.3s against a 95s
> promise, so those turns were trivial."* **That citation is withdrawn.** Joined
> to `chat_turns` at 20:21:49Z, **11 of the 16 rows are the same question —
> "what is a CARC code?" — sent across all three tiers**, out of four distinct
> questions in the whole sample. The comparison **holds the question constant
> and varies only the tier**, so it measures nothing about difficulty.
>
> It also fully explains the shape that looked like inversion, and the
> explanation is arithmetic: same question ⇒ similar delivered time ⇒
> *worst-as-%-of-promise* is dominated by the **denominator**. Thinking shows
> 8.7% because 95 is the largest number in the column.
>
> **The argument above never needed that data and stands without it.** Recorded
> rather than deleted, because a good conclusion resting on a bad citation is
> the same failure as a wrong one — it just survives longer.
>
> Nor is the `fast` breach a difficulty result: both `28.6s` and `7.8s` rows are
> `deploy smoke probe`, and the 28.6s one has `queue_wait = 0.028s` — **warm
> dispatch, 28.6s of real worker time on an identical probe eight minutes
> later.** That is a genuine open question, and a different one.
>
> `[OPEN]` **What would settle the difficulty question:** one tier across
> *different* questions, or real traffic. Sixteen rows of one question settles
> nothing.

**Keep `rn < max_it`, and understand why it is the sound part.** It is a crude
proxy for the real gate:

> **A critic whose verdict cannot be acted on is pure cost.**

Running a critic at the last round buys a verdict with nowhere to go — time and
money spent to be told something we can no longer fix. So the first condition is
**actionable budget**: enough time *and* cost left to act on a bad verdict, not
merely a round remaining.

**Second condition: uncertainty.** The critic is worth its price only when the
answer is neither clearly good nor clearly unsalvageable. In both extremes the
verdict changes nothing.

**The gate, stated as a decision rather than a mode test:**

```
run_critic  ⇔  actionable_budget(time, cost)  AND  quality_is_uncertain
```

Which is a **value-of-information** test: spend on knowing only when the knowing
can change the doing. `ledger > 0` survives as one input to the second term.

---

## 3. Enrichers — one lever, two moments. Not per-round.

**Per-round is the wrong shape** — enrichers do not run per round; they run once,
after react.

- **At admission**: budget the *intent*. Can this promise afford enrichment at
  all? On `fast` (13s / 1c measured) the answer is usually no, and that should be
  decided while the tier is being resolved, not discovered at the boundary.
- **At the react → integrate boundary**: make the *call*, against actual
  remaining budget. This is the moment with the most information in the whole
  turn — react has finished, real spend is known, and the promise clock has
  a real remainder.

**Budgeted at admission, decided at the boundary.** Admission can rule it out;
only the boundary can rule it in.

---

## 4. Proving phase 1 inert — replay is necessary and NOT sufficient

Replay proves equality **on the traffic you replayed**. The risk in this
extraction is precisely the input nobody thought to replay — and six of the
seven moved decisions read `mode`, elapsed time, or round number, which is where
untested combinations live.

**The bar: shadow mode on live traffic.**

1. React computes its directive **exactly as today**, and also calls the
   governor.
2. **Both are emitted** on the same envelope, with the inputs.
3. **React uses its own.** The governor's answer is observed, never applied.
4. Equality is asserted per turn. **Switch only after N consecutive turns agree
   across all four tiers and both regimes** — including the cold-start regime,
   which is ~1 turn in 5 and has different elapsed-time behaviour.
5. **Every divergence is a finding**, not a bug to paper over. A disagreement
   means one of the two is wrong about a case neither of us enumerated.

This is the demonstration requirement applied to a refactor: **inert is a claim
that gets measured, not asserted.** It costs one extra emit per turn and runs on
real traffic rather than the traffic we imagined.

**Purity requirement that makes it possible:** the extracted functions must take
the clock as an **input**, not read it. Two calls in the same turn that read
`monotonic()` independently cannot be compared for equality.

---

## 5. On phase 2 — agreed, and the reason is stronger than "separate commit"

`[READ]` verified: `react_loop.py:5418` reads `MOBIUS_TURN_DEADLINE_S` inline
with a **120** default and a **+25** margin; `governor.py` uses **90** and
`FINALIZE_MARGIN_S = 5.0`. Two writers, two deadlines, one budget.

**Retiring the critic's grant rather than reconciling it is the right call.**
Reconciling would leave two writers that agree today — and *agreeing today* is
not a property anything enforces. **A rule that exists only as agreement between
two code paths is not a rule** — same shape as the four comment-only rules found
today. One granter cannot disagree with itself.

---

## 6. Cost-so-far — accepted, with the caveat carried

`[READ]` verified: `ctx.usages.append` at `react/prompts.py:766` and
`react_loop.py:842`; `compute_cost` at `services/cost_model.py:76`. **So
`sum(compute_cost(u) for u in ctx.usages)` is readable at round top today.**
Two of four inputs are live, not one.

**The caveat is not cosmetic and must travel with the number.** `react_1`
reports cost on **686 of 1,236** calls — so cost-so-far is understated **on
precisely the path the governor steers.** A budget check against an understated
spend fails open: it permits rounds it should refuse.

**Therefore: until that is fixed, the governor's cost input carries a coverage
figure, and a cost-based refusal must not be built on it.** Cost may inform;
it may not yet *decide*. Time can decide — the promise clock is complete.

`[OPEN]` The `react_1` gap is an ask on llm_manager, not work for either seat.
