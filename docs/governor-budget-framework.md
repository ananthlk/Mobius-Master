# The governor's budget framework

Ananth, 2026-09-10: *"you have a question and a promise… set targets for each…
you have so many variables, this is a complex optimization problem, but you need
to set up the right framework for budgeting and make a call about is one more
round worth it and at what parameters so that you can direct others."*

All `[READ]` claims verified against source today.

---

## 1. State the problem honestly before framing it

**Two of the three promise terms are measurable and one is not.** Time is exact
(the promise clock, live since today). Cost is computable at round top
(`sum(compute_cost(u) for u in ctx.usages)`) with a known coverage hole.
**Quality has no measure at all.**

So this is **not** a three-way optimisation. It is:

> **Maximise an unmeasured objective, subject to two hard budgets, using
> estimators of unknown accuracy.**

Any framework that pretends otherwise will produce confident arithmetic on a
number nobody has. The framework's honesty requirement: **every decision records
which of its inputs were measured and which were estimated.**

---

## 2. Targets — and quality's target is a STOPPING CONDITION, not a threshold

| term | target | kind |
|---|---|---|
| **latency** | the tier's promised seconds (§7) | hard, measured |
| **cost** | the tier's exploration bound (§7) | soft today — cost may inform, must not decide, until `react_1`'s 686/1,236 coverage is closed |
| **quality** | **no threshold exists** | see below |

**You cannot set a quality target you cannot measure.** So quality's target is
expressed as the condition under which we stop spending on it:

> **Stop when the next unit of spend has no named gap to close.**

That is checkable without a quality metric, and it fails safe: if we cannot name
what another round would fix, another round is speculation.

---

## 3. The levers — and the split that governs everything

The critical distinction, which the flat lever list hides:

| | levers that change **the answer** | levers that change **what we know about it** |
|---|---|---|
| | new react round · tool selection · prompt · enricher | **the critic** |
| worth it when | a named gap can close | **the verdict could change the next decision** |
| failure mode | spend with no gain | **spend that buys a verdict with nowhere to go** |

**The critic buys information, not quality.** Running it when nothing can be
done with the answer is pure cost — which is why the gate is
*actionable-budget AND uncertainty*, not a mode test.

### The lever table

| lever | quality | latency | cost | notes |
|---|---|---|---|---|
| **new react round** | ↑ | ↑↑ | ↑↑ | **the only lever that can close a gap.** Most expensive, most direct |
| **tool selection** | ↑ | ↓ | ↓ | **the only Pareto lever** — a better tool improves all three. Should be exhausted before buying a round |
| **prompt / direction** | ↑ | ~ | ~ | near-free, and the *only* lever that gives direction rather than volume. **Underused** |
| **critic** | — | ↑ | ↑ | buys information. Changes no answer by itself |
| **model choice** | ↑↑ | ↕ | **↕↕** | Ananth''s addition. **The widest-swing lever of all** — and the only one with a control plane already built. See §3a |
| **enricher vs direct** | ↑ presentation | ↑ | ↑ | a formatting decision, not a correctness one. Direct-from-react is viable **if the react prompt is changed to produce structure** |
| **gap prioritisation** | ↑ | — | — | **free.** Choosing which gap to spend on is the highest-leverage decision available |

**Ordering that falls out of the table:** exhaust the free levers (gap
prioritisation, prompt) before the Pareto lever (tools), and the Pareto lever
before the expensive one (a round). **A governor that reaches for a round first
is skipping the two cheapest improvements it has.**

### 3a. Model choice — the governor BOUNDS, the bandit CHOOSES (and this already works)

Ananth added model choice to the answer-changing levers. It belongs there, and
it is the **widest-swing lever in the table**: measured over 30 days, per-turn
cost ran **2.56¢ p50 on gemini-2.5-flash** against **18.6¢ on gemini-2.5-pro** —
a **7× spread**, larger than any other lever moves any term.

**But the governor must not pick the model.** The bandit is a learner: it needs
to keep exploring, and a governor overriding its draw per turn destroys the
exploration that makes it work. The right division:

> **The governor sets the envelope. The bandit chooses inside it.**

`[READ]` **This is already built, and the governor is already the caller.**
`model_registry.py:1899-1915` applies `latency_budget_ms` as a **hard pre-filter
before Thompson sampling** — not a nudge to the draw — and
`react_loop.py:4813-4814` imports `latency_budget_ms` from
`react/governor.py` and passes it in. The registry''s own docstring names us:
*"a caller with a real deadline (e.g. ReAct''s Product Promise governor nearing
its hard ceiling) gets a guarantee, not just a probabilistic lean."*

It also degrades correctly: if the filter would empty the pool it keeps the
single fastest candidate rather than failing the turn. **Degraded beats none.**

**So one of the three terms already has a working control plane. The other two
do not:**

| term | control into model selection | status |
|---|---|---|
| **latency** | `latency_budget_ms` hard pre-filter | **LIVE**, governor is the caller |
| **cost** | **none** | `[OPEN]` — there is a *token* budget, which is **not a cost budget**: price per token varies across the roster, so a token cap does not bound spend. With a 7× price spread this is the gap that matters |
| **quality** | `bandit_weights` composite, per `chat_mode` | indirect — mode-derived, not promise-derived |

### 3b. "Same round, better model" — a lever the flat list hides

Escalating the model **within** the current round is **distinct from buying
another round**, and is usually cheaper:

- **another round** = another full turn of tool calls, tokens and latency
- **model escalation** = the same work, done better, at a higher unit price

**When a gap stays open after a round, the first question is not "another
round?" — it is "was this the right model for that gap?"** A synthesis failure
on good evidence (high tool scores, low confidence — §6''s prompt-lever quadrant)
is often a model-capability problem, and buying a second round with the same
model repeats the failure at full price.

`[OPEN]` This requires per-call escalation authority the governor does not have
today: it can bound latency, it cannot say *"this call, spend more."*

---

## 4. The currency is GAPS — and the producer exists while the consumer does not

Ananth: *"open gaps (to be created… can be closed based on importance)."*

**The producer is already good.** `[READ]` `react/prompts.py:382, 398, 443` —
react emits `gaps_closed` and `gaps_open` per round as **named lists**, with the
instruction: *"name specific missing pieces, not 'need more info'… gaps_closed
is what THIS round's tool result actually resolved."*

**🔴 The consumer does not exist.** `[READ]` The only reader in the pipeline is
`react_loop.py:1139-1140`:

```python
gaps_open = (enr or {}).get("gaps_open") or []
if gaps_open:
    return False
```

**Last round only, any-vs-none, and the content is discarded entirely.** The
named gaps — the thing the prompt works hard to elicit — are collapsed to a
boolean.

And `prompts.py:443` tells the model: *"a gap tracker downstream reads these
directly."* **There is no gap tracker.** That is the worst variant of the
comment-only rule: **an instruction the model follows whose output nothing
reads** — and it is the exact input the budget framework needs.

### What a gap must carry to be spendable

| field | why |
|---|---|
| **id / identity** | so *closed* is verifiable, not asserted. Today gaps have no identity across rounds |
| **importance** | Ananth's word. Not all gaps are worth a round |
| **age (rounds open)** | a gap open for three rounds is evidence the lever isn't working, not that more of it is needed |
| **attempted-by** | which lever has already been spent on it. **Prevents buying the same round twice** |

**Without identity, "gaps closed" cannot be measured** — and gaps-closed is the
objective. This is the same hole as recall (§8), and it is the load-bearing one.

---

## 5. The decision — "is one more round worth it?"

**Not** *"is confidence low?"* — that is a feeling, and a self-report. The rule:

> **Buy a round iff: a NAMED gap is open, it is important enough to matter to
> the answer, no cheaper lever addresses it, the round has a PLAN for it, and
> the budget can afford both the round and acting on what it finds.**

Five conditions, all checkable **before** spending, and all reviewable
**afterwards** — did the named gap actually close?

**The last condition is the one usually forgotten.** Buying the final round of
budget to *discover* a problem leaves nothing to fix it with. **Reserve the cost
of acting, not just the cost of looking** — the same principle as the critic
gate, applied to rounds.

### The parameters that travel with the directive

A directive is not `continue`/`stop`. It is:

```
{ decision, because, gap_targeted, expected_close, budget_remaining,
  lever, depth, role, tools_hint, inputs_measured, inputs_estimated }
```

`because` and `gap_targeted` are what make it **auditable**. A round bought for
a named gap that then stays open is a **measurable governor error** — which is
how the policy improves without a quality metric.

---

## 6. Quality: three estimators, none trusted alone

| signal | cost | independence | failure mode |
|---|---|---|---|
| **react self-reported confidence** | free | **none — it grades itself** | confidently wrong asks for nothing; anxious asks for everything |
| **tool raw scores** `[READ]` `react_loop.py:3869` (`rerank_score`/`original_score`) | free | high | measures **retrieval**, not the answer. Good sources, bad synthesis scores well |
| **critic / QA** | expensive | **high** | end-of-turn artifact; costs the thing it is judging |

**Rule: no single signal authorises spend.** Specifically, **self-reported
confidence must never authorise spend on its own** — it is the only signal
produced by the thing being judged, and it is free precisely because it is
cheap talk.

**The useful combination is disagreement.** High tool scores + low self-reported
confidence = good evidence, poor synthesis → **a prompt lever, not a round**.
Low tool scores + high confidence = **the dangerous quadrant**, and the one case
where buying the critic is clearly worth it.

---

## 7. Bootstrapping — there is no training signal, so v1's job is to create one

We cannot learn a policy today: no reward, no counterfactual, no labels.
So v1 is **a rule-based policy that logs the data to replace itself.**

Every decision emits: the directive, its `because`, **the alternatives
considered and why they were rejected**, and — after the fact — **whether the
named gap closed.**

> **The framework's first job is to generate the data that will eventually
> replace the framework.**

Without that, in six months we will have the same rules and the same absence of
evidence — which is exactly the position the promise was in this morning, before
anything measured it.

---

## 8. What this needs that does not exist

| need | status |
|---|---|
| gap **identity + lifecycle** | `[OPEN]` **the blocker.** Producer good, consumer is a boolean |
| gap **importance** | `[OPEN]` not emitted; needs a prompt change |
| **cost coverage** on `react_1` | `[OPEN]` 686/1,236 — spend understated, **fails open** |
| **cost budget into model selection** | `[OPEN]` — token budget exists, cost budget does not; 7× price spread makes them different things |
| **per-call model escalation** | `[OPEN]` — governor can bound latency, cannot authorise spend |
| directive **counterfactual log** | `[OPEN]` new |
| quality **estimator combination** | `[OPEN]` design above, unbuilt |
| time budget | **LIVE** — shipped today |
