# The round protocol — declare the envelope, then spend it

Ananth, 2026-09-10: *"you will tell this round is going to cost us between 10
and 20 seconds and x–y cost and we think we will get the quality to a–b… that's
your hope of the round, and you ask tool to give you tools that work within
those parameters (if they say no then you don't have a choice). Then you build
the prompt adjusting for tokens and direction, then we go to react."*

---

## 1. The round declares a RANGE, not a number

> **"This round will cost 10–20s and 3–6¢, and we expect quality to move from
> a to b."**

**Ranges, not points, and this is not hedging.** Today's own data says a point
estimate lies: the queue wait is **bimodal** — 13 turns at 0.023s and 3 at
3.762s, with nothing in between. A p50 would have reported it as negligible and
been wrong about one turn in five. **An interval carries the shape; a mean
erases it.**

A range is also **falsifiable in a way a point is not**: delivered inside the
range is a good forecast; delivered outside is a **finding**, and specifically a
finding about the estimator rather than the turn.

**The quality term is the honest one.** It is `a → b` on an ordinal, not a
number, because §8 still says recall has no measure. **Stating it as a range
makes the absence visible** instead of implying precision we do not have.

---

## 2. The round is a BUDGET CASCADE, and each module may refuse

```
   promise (frozen at POST)
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ 0 · GOVERNOR declares the round envelope                 │
│     latency 10–20s · cost 3–6¢ · quality a→b · gap G     │
└──────────────────────────────────────────────────────────┘
        │  budget_ms, budget_c, token_budget, gaps_open
        ▼
┌──────────────────────────────────────────────────────────┐
│ 1 · TOOL EXPOSURE  — estimate() → offer, or REFUSE       │
│     "here are the tools that fit"  /  "nothing fits"     │
└──────────────────────────────────────────────────────────┘
        │  offered set + measured token cost  ⇒ budget CONSUMED
        ▼
┌──────────────────────────────────────────────────────────┐
│ 2 · PROMPT BUILDER — build within the REMAINING tokens   │
│     + direction + gap_targeted                           │
└──────────────────────────────────────────────────────────┘
        │  remaining latency/cost envelope
        ▼
┌──────────────────────────────────────────────────────────┐
│ 3 · MODEL SELECTION — governor bounds, bandit chooses    │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ 4 · REACT executes                                        │
└──────────────────────────────────────────────────────────┘
        │  actuals + gaps_closed / gaps_open
        ▼
┌──────────────────────────────────────────────────────────┐
│ 5 · ROUND ATTESTATION  — declared vs delivered            │
└──────────────────────────────────────────────────────────┘
```

**The cascade is sequential because the budget is consumed as it flows.** Tool
exposure spends tokens; the prompt gets what remains. This is why tool exposure
goes first and why it is the Pareto lever — **every token it does not spend is a
token the prompt can use for direction.**

---

## 3. "If they say no, you don't have a choice"

Ananth's line, and it makes `estimate()` **an offer that can be refused**, not
just a price.

**A refusal is binding on me.** If no tool fits a 13-second envelope, I do not
get to overrule it — the tool genuinely cannot return in time. My options are
exactly three:

| option | when |
|---|---|
| **run the round without that capability** | the gap may still close another way |
| **widen the envelope** | only if the promise allows it — and it is the promise, not my preference, that decides |
| **do not buy the round** | if the gap cannot close without a tool that does not fit, the round is speculation |

**The third is the one a naive governor never takes**, and it is often correct.
A round that cannot close the gap it was bought for is spend with a reason
attached, which is worse than spend without one — it *looks* justified.

**A refusal is a first-class signal, not an error.** Recorded with its reason, it
is evidence about the promise: *"`fast` cannot answer this class of question
because the only tool that could takes 90s."* That is a finding about the tier,
surfaced by the tier being enforced.

---

## 4. Round attestation — the turn pattern, one level down

Same shape as the turn attestation shipped today:

| field | source |
|---|---|
| `round_n`, `gap_targeted`, `because` | the directive |
| `declared_latency_lo/hi`, `declared_cost_lo/hi`, `declared_quality_a/b` | **the envelope, recorded BEFORE the round** |
| `delivered_latency_ms`, `delivered_cost_c` | actuals |
| `in_range` | derived |
| `gap_closed` | **did the named gap actually close?** |
| `refusals` | which modules refused, and why |

**Two questions fall out, and they are different:**

- **Was the forecast right?** delivered vs declared → **the estimator's accuracy**
- **Was the spend right?** `gap_closed` vs `gap_targeted` → **the governor's judgement**

A governor can forecast perfectly and still buy the wrong round. **Separating
these is the only way to improve either while quality stays unmeasured** — and
`gap_closed` is a *measurable governor error*, which is the closest thing to a
training signal this design has.

---

## 5. What blocks this

| need | status |
|---|---|
| tool `estimate()` returning an offer or refusal | **Tool Manifest: built.** Selection is 0.34ms, so it prices the *real* result rather than modelling it |
| **observed** per-tool latency | `[OPEN]` **I cannot supply this today** — see below |
| prompt builder taking `token_budget` + `direction` + `gap_targeted` | `[OPEN]` next seat |
| **cost** envelope into model selection | `[OPEN]` — a token budget is not a cost budget; ~7× price spread |
| gap **identity** | `[OPEN]` **unowned, and it is what `gap_closed` depends on** |

### The per-tool latency gap — an honest no

Tool Manifest's `latency_ms` is built from **owner-declared** latencies, with
four tools declaring none and priced as free. They asked me to replace
declarations with observations from the attestation. **I checked, and I cannot:**

- `turn_spans` has module granularity only — `tool_manifest` (0–1ms, which
  independently confirms their 0.34ms) and `react_loop` (avg 4,991ms, p90
  10,147ms, max 45,110ms). **No per-tool span.**
- `chat_tool_results` has `thread_id, turn_id, tool_hint, payload, created_at`
  — **no duration column at all.**

So the budget''s tool-latency term rests on **declarations nobody has checked**,
and is wrong in a knowable direction for the four tools declaring nothing.
`[OPEN]` **Per-tool timing needs a producer before this can be measured.**
Neither seat can fix it alone.
