# The modular target — seams, contracts, and who owns each

Ananth, 2026-09-10: *"almost all of this exists but is not modular. I want to
get to a clean modular place."*

Also settled in that message, and it changes the tool seam:
**tools execute AFTER react; tool selection decides which tools are EXPOSED to
react, not which one is called.** Pre-react execution is a later option, not the
target now.

---

## 1. The organising principle

> **The governor is the only module that holds state and makes decisions.
> Every other module is a function of `(inputs, directive) → output`.**

This is what makes the whole thing modular, testable and shadowable at once —
and it is the same property that lets phase 1 be proven inert: **a pure module
can be run twice and compared.** A module that reads the clock, the mode, or a
global cannot.

### The seam rule that does not exist yet, and matters most

> **A module the governor cannot price cannot be budgeted.**

Today no module declares what it costs. The governor is asked to spend a budget
on components whose price it learns only after paying. **Every module contract
below therefore carries an `estimate(inputs) → {latency_ms, cost_c}`** — not a
guarantee, an estimate, with its own measured accuracy over time.

Without it, "is one more round worth it?" is unanswerable in principle: you
cannot compare a cost you will not know until afterwards.

---

## 2. The seam map

| # | module | today | seam target | owner |
|---|---|---|---|---|
| **0** | **Governor** | `react/governor.py` — advisory, computes some directives, two writers for extensions | **sole decision authority**; holds promise, budget, gaps | this seat |
| **1** | **Tool exposure** | all tools shipped every round — **57 tools / 14,271 tokens** | shortlist: which tools react *sees* | **Tool Manifest agent** (new) |
| **2** | **Prompt builder** | already modular | takes `role · depth · direction · gap_targeted` | **Prompt agent** |
| **3** | **Model selection** | bandit; `latency_budget_ms` pre-filter **LIVE**, governor already the caller | governor sets envelope, bandit chooses inside | **llm_manager** |
| **4** | **React executor** | `react_loop.py` — decisions embedded in the loop | pure executor: prompt + tools + model → answer, evidence, gaps | chat seat |
| **5** | **Gap assessment** | exists post-react; **output is discarded** | named gaps with identity, importance, age | `[OPEN]` unowned |
| **6** | **Critic / QA** | gated on `agentic AND rounds AND ledger` | governor-gated on value-of-information | chat seat |
| **7** | **Integrator / enricher** | always runs | governor-budgeted; direct-from-react viable if prompts produce structure | chat seat |

---

## 3. The contracts

Each module declares the same four things. **Uniformity is the point** — the
governor should not need module-specific knowledge to budget.

```
estimate(inputs)            -> {latency_ms, cost_c, confidence}
run(inputs, directive)      -> output
declares.affects            -> which promise terms it moves, and which way
declares.preconditions      -> what must be true to call it
```

### 1 · Tool exposure — the biggest single win available
**Input:** query, user authority, gaps open, tier.
**Output:** ranked tool shortlist + why each was included.
**Why it is first:** 14,271 tokens of manifest ship **every round**. On a
multi-round turn that is the largest fixed cost in the system, and it is paid
whether or not any tool is used. **Cutting it improves all three promise terms
at once** — the Pareto lever, and the only module whose improvement needs no
tradeoff.
**Ananth''s framing:** selection will get better as modules improve; the seam
should be built now so it *can* improve.

### 2 · Prompt builder — already modular, and underused
**Input:** role, reasoning depth, **direction**, `gap_targeted`.
**Output:** the prompt.
**The governor''s cheapest lever, and the only one that gives direction rather
than volume.** Today the governor computes role and depth (`react_loop.py:4760`,
`:4792`) but passes **no gap and no direction** — so a round bought to close a
specific named gap does not tell the model which gap. `[OPEN]` **That is a
prompt change, not an architecture change, and it is nearly free.**

### 3 · Model selection — already the right shape, two-thirds unwired
Governor bounds, bandit chooses. `latency_budget_ms` is a **hard pre-filter
before Thompson sampling** and the governor is already the caller.
`[OPEN]` **No cost envelope** — the token budget is not a cost budget; price per
token varies ~7× across the roster. `[OPEN]` **No per-call escalation** — the
governor cannot say *"this call, spend more"*, which is what makes
*same-round-better-model* unavailable as a lever.

### 4 · React executor — the extraction
Phase 1 of step 2: seven decisions move out, react calls the governor and
applies the answer. **Proven inert by shadow mode**, not replay. **Purity
requirement: the clock is an input, never read inside.**

### 5 · Gap assessment — the load-bearing hole
The producer is good: react emits named `gaps_open` / `gaps_closed` per round.
**The consumer is a boolean** (`react_loop.py:1139` — `if gaps_open: return
False`), and the prompt tells the model *"a gap tracker downstream reads these
directly"* when **no gap tracker exists**.
Gaps are the framework''s currency: without **identity**, "closed" cannot be
verified; without **importance**, priority cannot be set; without **age**, a
stuck gap looks like a fresh one. `[OPEN]` **Unowned, and it blocks the budget
framework more than anything else on this page.**

### 6 · Critic — a decision, not a mode test
`run_critic ⇔ actionable_budget(time, cost) AND quality_is_uncertain`.

### 7 · Enricher — one lever, two moments
Budgeted at admission, decided at the react→integrate boundary.

---

## 4. Sequencing — what unblocks what

```
Gap identity (5)  ──►  the budget framework can name what it is buying
Tool exposure (1) ──►  the Pareto win; frees budget for everything else
Prompt direction (2) ─► a bought round can be aimed
Cost envelope (3) ──►  the widest-swing lever steerable on more than latency
Extraction (4)    ──►  decisions leave the loop; shadow-proven inert
```

**Gap identity first.** Everything else is a lever, and a lever with nothing to
aim at is volume. `[OPEN]` It is also the only item with **no owner**.

---

## 5. What is deliberately NOT changing

- **Tools still execute after react.** Pre-react execution is a later option.
- **The bandit still chooses the model.** The governor bounds; it must not pick,
  or exploration dies.
- **The promise stays frozen at POST.** Modularity does not get to move it —
  the attestation''s denominator depends on it.
