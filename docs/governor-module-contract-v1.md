# Governor ↔ module contract, v1

The uniform interface every module in the turn implements. **Uniformity is the
point**: the governor must be able to budget without module-specific knowledge.

---

## The four declarations

```python
estimate(inputs) -> Estimate          # what will this cost me, BEFORE I call it
run(inputs, directive) -> Output      # do the thing, under my parameters
AFFECTS: dict                         # which promise terms it moves, and which way
PRECONDITIONS: list[str]              # what must hold for a call to be valid
```

### `estimate` — the one that does not exist anywhere today

```python
Estimate = {
  "latency_ms": float,
  "cost_c":     float,
  "confidence": "high" | "medium" | "low",   # in THIS estimate, not in the output
}
```

**A module the governor cannot price cannot be budgeted.** Without `estimate`,
*"is one more round worth it?"* is unanswerable in principle — you cannot weigh a
cost you only learn by paying it.

It is an **estimate, not a guarantee.** Its accuracy is measured over time by
comparing it to the attestation''s delivered numbers. **A module whose estimates
are consistently wrong is a finding, not a failure** — and it is only detectable
because the estimate was recorded before the call.

### `run` — pure, and the clock is an input

```python
run(inputs, directive) -> Output
```

**No module reads the clock, the mode, or a global.** Everything it needs
arrives in `inputs` or `directive`. This is what makes a module (a) unit
testable, (b) **runnable twice and compared** — which is how any extraction is
proven inert, and how a change is proven safe on live traffic without applying
it.

### `AFFECTS` — signed, per term

```python
AFFECTS = {"quality": "+", "latency": "-", "cost": "-"}
```

Lets the governor reason about a module it has never seen. A module that
improves all three (`+`,`-`,`-`) is a **Pareto lever** and should be exhausted
before anything with a tradeoff is bought.

### `PRECONDITIONS`

What must be true for the call to be valid — not what makes it *wise*. Wisdom is
the governor''s job; validity is the module''s.

---

## What the governor sends

```python
Directive = {
  "decision":       str,        # what to do
  "because":        str,        # WHY — makes it auditable after the fact
  "gap_targeted":   str | None, # which named gap this spend is meant to close
  "budget":         {"latency_ms": float, "cost_c": float},   # what you may spend
  "params":         dict,       # module-specific
  "promise_version": str,
}
```

**`because` and `gap_targeted` are not documentation.** They are what make a
decision reviewable: **a round bought for a named gap that then stays open is a
measurable governor error.** That is how the policy improves while quality
remains unmeasured.

## What a module returns

```python
Output = {
  "result":    Any,
  "actual":    {"latency_ms": float, "cost_c": float},   # vs the estimate
  "gaps_closed": list[str],   # if it can speak to gaps
  "gaps_open":   list[str],
  "notes":     str | None,
}
```

`actual` beside `estimate` is what makes estimates improvable. **Never omit it
because it "should" match.**

---

## Rules that bind the governor, not the modules

1. **The governor bounds; it does not choose.** Where a module has its own
   optimiser — the bandit — the governor sets the envelope and the module picks
   inside it. Overriding a learner''s draw destroys the exploration that makes it
   work.
2. **The promise is frozen at POST.** No directive may move it. The
   attestation''s denominator depends on it.
3. **Errors are a precondition, never a budget term.** You can spend cost to buy
   quality. You cannot spend errors to buy anything.
4. **Free levers before priced ones.** Gap prioritisation and prompt direction
   cost nothing. A governor that buys a round without having aimed a prompt is
   skipping its cheapest improvement.
5. **Every decision records which inputs were measured and which estimated.**
   Today: latency measured, cost measured-but-undercounted, quality estimated.
