# The A/B harness — contract

`[RULED]` Ananth, 2026-09-11: *"give a contract to them so that it does not
disrupt what we have but builds… we will be doing lots of A/B so this setup is
not bad."*

**Built as reusable infrastructure, not a one-off for v2.**

---

## 1 · The rule that keeps it from disrupting production

> **Production routes. The harness forks. They are different surfaces and the
> distinction is load-bearing.**

| | production | the harness |
|---|---|---|
| a turn goes to | **exactly one** orchestrator | **both**, deliberately |
| why | a user is served once; two writers sharing state is the defect this program removed three times | nobody is being served — **running both on identical input IS the point** |
| routed by | `assign(correlation_id, v2_pct)`, recorded as `orchestrator_version` | the harness, explicitly, per question |

**Nothing here is a precedent for forking a live turn.** If a future reader
finds this and concludes production may fork, the harness has done damage.

---

## 2 · What the harness may NOT do

| rule | why |
|---|---|
| **never write to `thread_gaps`** | the ledger is thread-scoped and outlives the turn. Harness runs would seed a real thread with gaps no user opened |
| **mark every turn it creates** | so conformance queries can exclude them — the `VERIFY-ROW%` lesson, one level up |
| **never count toward the ≥200** | `[RULED]` chat seat: *v2 must not pass on traffic v2 generated* |
| **never change the promise** | the harness observes the contract; it does not get to relax it |
| **hold everything constant but the arm** | same question, same mode, same window. **The only thing that varies is the orchestrator** |

**The third rule is the one that will be tempting to break** — 20 clean
comparisons look like 20 data points. They are **zero** data points for the exit
criteria and **20** for human judgement. Different currencies; do not mix them.

---

## 3 · What it produces

```
per question, per arm:
  the rendered answer        ← what the human judges
  the decision trace         ← postures / directives, round by round
  promised vs delivered      ← latency, cost, exit_mode
  gaps opened / closed       ← by id once the ledger is live
  divergences                ← where the two machines disagreed, and why
```

**The human is the judge.** Quality has no measure — `AFFECTS` for tool exposure
was corrected to `quality: UNMEASURED` for exactly this reason, and there are
**zero golden fixtures** anywhere in the fleet. **A person reading two renderings
side by side is the only quality signal that exists**, and it is a better one
than a number nobody can compute.

---

## 4 · The question set — `eval/ab_question_set_v1.json`

**20 real production questions**, 90-day window, deduped.

`[DESIGN]` **Machine-generated follow-ups were excluded** — anything containing
*"A previous search left this unresolved"*, *"Earlier searches surfaced"*, or
*"Quote the sentence that states"*. Those were written **by the system**, and a
sample you generated yourself passes every provenance check perfectly. That trap
has caught two seats in this program already.

Shapes: 5 lookup · 2 hard lookup · 2 comparison · 4 multi-round · 3 procedural ·
1 multi-part · 1 tool-shaped · 1 typo-tolerance · 1 underspecified.

**It is NOT a golden set.** Real inputs, no known-correct outputs. **It fixes
what both arms are asked; it does not grade the answers.**

**All 20 run in `copilot` (default)** — `[RULED]` — which holds the tier constant
so the only variable is the orchestrator.

---

## 5 · Staging — the second box fills in later

| stage | box 1 | box 2 |
|---|---|---|
| **now (R0)** | v1''s real answer, rendered | v2''s **decision trace** and where it diverged |
| **at R1** | v1''s answer | **v2''s answer**, rendered identically |

**v2 cannot produce an answer yet** — it is a posture machine in shadow: it
decides what a round is *for*, and executes nothing. Saying so now is cheaper
than an empty box later.

**The R0 stage is not filler.** Seeing *"v1 called complete at round 9; v2 said
gaps were still increasing"* against a real question is when changing the machine
is cheapest.

---

## 5a · What this actually is — the fleet''s only quality instrument

`[RULED]` Ananth, 2026-09-11: *"I don''t imagine this as a one-time thing but as
a setup that we can capitalize on."*

**Worth stating plainly, because it changes the priority:**

| | state |
|---|---|
| golden fixtures, fleet-wide | **zero** — Tool Manifest, verbatim |
| recall | **no measure** (§8 of the promise) |
| tool-exposure `AFFECTS.quality` | **UNMEASURED** — corrected today |
| the groundedness floor on `agentic` | **never runs** |

> **A person reading two renderings side by side is the only quality signal this
> system has.** Not a fallback for when the metric is unavailable — there is no
> metric, anywhere, for the term the promise calls quality.

So this is not a page for comparing v2. **It is the apparatus.**

### And it produces the thing nobody can currently buy

Every comparison where a human says *"this one is right, and here is why"*
yields a **(question, better answer, reason)** triple. **That is a golden
fixture** — the artifact Tool Manifest has none of, Eval cannot grade without,
and recall cannot be measured against.

**The harness pays for itself by generating its own missing input.** Nothing else
in the fleet does.

`[DESIGN]` **Accumulate them as labelled examples. Never as a score.** The moment
*"v2 better: 13/20"* exists it will be quoted as an exit criterion, and the
distinction between *zero data points for the criteria* and *twenty for
judgement* stops being observed. **A fixture is evidence; a tally is a claim.**

### The smallest thing that makes it a capability rather than a page

| piece | why |
|---|---|
| `ab_runs` — `run_id · arm_a · arm_b · held_constant[] · varied[] · question_set · created_by` | **a run is a record, not a one-off.** Without it, every comparison is unreproducible the day after |
| versioned question sets — `ab-v1`, `ab-v2`, … | sets **accumulate**; a set is what makes two runs comparable to each other |
| verdicts as annotations keyed `(run, question, arm)` | judgement **persists** and is re-readable — and is never summed |
| the `experiment` block **mandatory** on every run | the *what varied / what was held constant* line, enforced by the schema rather than by discipline |

**Four small things. None of them is about v2.**

### Self-serve, which is the actual capitalization

Arm-agnostic means **any seat declares an experiment without me**:

| seat | the arm they cannot currently settle |
|---|---|
| Tool Manifest | **manifest 57 vs 5** — they have the reduction measured and *"the ranking is not yet a win at all"* |
| prompt seat | **profile A vs B** — the `critical_rules` split, once it exists |
| llm_manager | **model X vs Y** on real questions, not on bandit reward |
| governor | **v1 vs v2**, and later **enricher vs direct** |
| Eval | any prompt or policy change, before it ships |

**Every one of those seats is currently blocked on the same absence.** The
harness is the shared unblock, and it is why it should be built once, properly,
rather than four times badly.

---

## 6 · Reusable beyond v2

The same surface takes any two arms: **prompt profile A vs B · manifest 57 vs 5 ·
model X vs Y · enricher vs direct.** What makes it reusable is that the contract
is about **isolation and provenance**, not about v2:

1. both arms get identical input
2. only the named variable differs
3. harness traffic is marked and excluded from every production number
4. the human judges the rendering; the machine reports the terms
5. **state what varied and what was held constant, inside the artifact**

`[DESIGN]` **Rule 5 is the one this program keeps re-learning.** A tier table was
withdrawn for holding the question constant and varying only the tier; a
tokenizer claim was withdrawn for holding content type constant across two
samples. **A comparison without that line stated is a shape with no experiment
behind it.**
