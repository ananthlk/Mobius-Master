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

### The per-tool latency term — DECLARED is v1, and it becomes measured by being used

Ananth, 2026-09-10: *"if we don''t start we don''t get. Now we know what to
measure."* He is working the declarations into Tool Manifest directly.

**Correction to an earlier version of this section**, which called this the
weakest input and left it `[OPEN]` pending a producer neither seat owns. **That
framed a starting point as a blocker.** Declared latencies are exactly the
exploration-bound argument one level down: **a term you refuse to state because
it is imperfect never accumulates the evidence that would improve it.**

**What I could not find, stated so nobody re-searches for it:**
- `turn_spans` is **module** granularity — `tool_manifest` 0–1ms (which
  independently confirms Tool Manifest''s 0.34ms), `react_loop` avg 4,991ms /
  p90 10,147ms / max 45,110ms. **No per-tool span.**
- `chat_tool_results` carries `thread_id, turn_id, tool_hint, payload,
  created_at` — **no duration column.**

**But per-tool spans are not required to start correcting declarations.** What
is required is that the round attestation records, every round:

| field | why |
|---|---|
| `tools_offered` | which tools were in the set |
| `declared_latency_ms` | **the sum the offer was priced at** |
| `declared_version` | **which declaration was in force** — an owner updating a number must not retroactively rewrite past rounds. Same rule as `promise_version` |
| `delivered_latency_ms` | what the round actually took |

**Over enough rounds, per-tool truth falls out of set-level observations.** A
tool that keeps appearing in rounds slower than their declarations predicted is
visible in the co-occurrence long before any per-tool timer exists — the same
way the bandit learns per-model quality from turn-level outcomes it never
attributes directly.

**So the sequence is: declare now → record declared-vs-delivered from the first
round → let attribution emerge → replace declarations with measurements where
the data disagrees with them.** Per-tool spans would make that faster, not
possible. They are an accelerant, not a precondition.

`[OPEN]` The four tools declaring nothing are priced as free, which is wrong in
a **knowable** direction — they can only be underestimated. Worth a placeholder
declaration rather than a zero, because **a zero is indistinguishable from a
genuinely instant tool** and a placeholder is not.
