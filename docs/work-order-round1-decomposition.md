# Work order — ask for `gaps_open` on round 1

**From:** Governor seat (orchestrator v2)
**To:** Prompt / LLM seat — owner of `react.response_shape`
**Raised by:** Ananth, 2026-09-11 — *"why did R1 not get us 3 sub-questions,
could have skipped a step"*, and *"work with prompt to change the frame prompt
to include decomposition when the question is obvious."*

---

## The ask, in one line

On **round 1 only**, ask for `gaps_open` — and nothing else from
`evidence_review`.

## Why it is not already happening

`react.response_shape` says, verbatim:

> include `"evidence_review"` whenever this is **NOT your first round** (i.e.
> earlier tool results are present in context above)

**That clause is right about three of its four fields and wrong about the
fourth.** On round 1 there is no evidence, so `keep`, `running_answer` and
`gaps_closed` are genuinely meaningless — asking for them would invite the
model to invent a review of nothing, which is a worse failure than the one
below.

`gaps_open` is different. *"Compare the timely filing deadlines for Sunshine
Health, Humana and Aetna"* names three lookups **on its face**. No tool call is
required to know that. The prompt is currently withholding a field the model
could fill from the question alone.

## What it costs today — measured, 20 production questions, 2026-09-11

Run `ab-82c6105465`, copilot, v2 arm:

```
EVERY R1 in the run had exactly ONE gap. All twenty.
(that one gap is G0 — the governor's seeded root, i.e. the whole question)

6 of 20 turns later split into 2–4 sub-questions:

  q      R1 gaps   peak gaps   R1 cost
  q08        1         2         5.7s
  q09        1         3         7.4s
  q10        1         4         9.3s
  q12        1         2        10.4s
  q14        1         3         8.6s
  q17        1         2         3.1s
```

**The cost is not the round. It is that every budget decision on those six
turns was made against a gap count that was wrong.** The governor's
`spendable()` reserves the cost of buying one more round plus acting on it. On
q10 the real remaining work was four lookups. The arithmetic was correct and
answering the wrong question.

Consequence, traced end to end on q09: round 3 had to draw an **overrun**
because it was **2.84s short**, with two gaps it only learned about at round 2.
Had the three been open at round 1, the affordability maths would have been
different from the start — it might have refused the second rag round, targeted
all three in one call, or said up front that it could not afford all three.

## The precise change

In `react.response_shape`, add a **round-1 shape** that asks for `gaps_open`
alone:

```
First round — you have no evidence yet, so there is nothing to review.
Include "evidence_review" with ONLY gaps_open:
{
  "thought": "...",
  "evidence_review": {
    "gaps_open": [<the distinct things this question asks for, if it asks for
                  more than one — e.g. one entry per payer, per code, per
                  timeframe. EMPTY ARRAY if the question asks for one thing.>]
  },
  "tool": "...", "inputs": {...}, "is_complete": false
}
```

**The empty-array case is load-bearing and must be stated as prominently as the
populated one.** Fourteen of the twenty questions in the run are single-part. A
prompt that rewards decomposition will decompose "what are Sunshine's timely
filing deadlines?" into three imaginary sub-questions, and the governor will
then budget for work that does not exist — the same defect as today, in the
opposite direction and harder to see, because a wrong gap count that is too
HIGH refuses rounds the turn could afford.

This is the `feedback_example_undermines_the_rule` shape: whatever example you
write will be copied. If the example shows a three-way split, expect three-way
splits. Consider making the *single-part* case the example.

## What I will do on my side, and what I will not

**Will:** the governor already seeds `G0` when the ledger is empty and will keep
doing so — a round-1 `gaps_open` REPLACES the seed rather than adding to it, so
there is no double-count. `decision_inputs` records the gap list per round, so
the effect of this change is measurable the day it ships: R1 gap counts stop
being uniformly 1.

**Will not:** build a second decomposer. If react already has a
decomposition/shape step I should be reading instead of asking the prompt to
duplicate, tell me and I will read that instead. **A decomposition only the
governor can see is a producer with no consumer** — the defect this program has
now found thirteen times.

## Two risks, stated

1. **This changes what the model emits on EVERY turn, not just multi-part
   ones.** It needs to ship behind whatever gate you normally use and be
   measured against the single-part majority, not the six.
2. **The gap text is the governor's identity key.** Gap ids are content-
   addressed (sha1 of the normalised text), so a wording change reworded by a
   prompt edit mints new ids and resets gap age and lever counts — which are
   what make the `stuck` rule reachable at all. I now record `reworded_from`
   and `reworded_similarity` on every gap, so drift is countable rather than
   silent; **tell me when this lands and I will watch that rate**, because a
   spike is the signal that the ids are being held together by a 0.70
   similarity threshold rather than by the model saying the same thing twice.

## Not asked for

A `frame` prompt profile. There is no FRAME posture in the running machine —
I declared it unreachable on 2026-09-11 because its only trigger was
positional (`round_index <= 1`, which means "this is round one", not "we are
answering the wrong question"). **Ananth's observation is the first real signal
for it**: a question whose surface structure names more than one thing to look
up. That is a property of the question, testable at round 1, and correctly
false on the fourteen single-part questions here. If this change lands and the
counts come back honest, FRAME becomes buildable on evidence rather than on
position — but that is a later conversation and it is not what this order asks
for.
