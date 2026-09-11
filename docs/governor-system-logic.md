# The governor — full schema and decision logic

Ananth, 2026-09-11: *"tell me the schema with the actual logic and formula for
the entire system, and we can start producing contracts including yours."*

**Every constant below is tagged.** `[MEASURED]` from dev · `[RULED]` by Ananth ·
`[GUESS]` calibrated on nothing. **Do not read a `[GUESS]` as a finding** — four
claims were withdrawn tonight for exactly that, and every one was caught by
asking what varied.

---

## PART I — THE DATA

### 1 · `promise` — git, versioned, frozen at POST

```python
PROMISE_VERSION = "v1"
_TIER_BY_MODE = {"quick": "fast", "copilot": "normal", "agentic": "thinking"}

PROMISE = {                      # [MEASURED] n=1,119 turns, 2026-08-11 → 09-10
  #          latency_s  band  cost_c   quality
  "fast":     (13,       5,    16,     "none"),   # [RULED] 15× cost headroom
  "normal":   (31,       8,    45,     "some"),
  "thinking": (95,      25,    81,     "best"),
}
```

**Rules.** Frozen at POST, immutable for the turn. Cost is an **exploration
bound, not a budget** — measurement produces the promise, never the reverse.
Quality is **ordinal**; recall has no measure. **Widening a band is a new
`promise_version`**, not a config change.

### 2 · `turn_attestations` — LIVE (migration 065, deployed `mobius-chat-00982`)

```
correlation_id PK · promise_version · tier
posted_at · published_at                      ← the promise clock, POST → PUBLISH
outcome        completed|failed|empty_payload|unknown     ← MECHANICAL
exit_mode      complete|budget|capability|error           ← SEMANTIC   [TO ADD]
promised_latency_s · promised_cost_c · promised_quality   ← INLINE, not by reference
delivered_latency_s · worker_latency_s · delivered_cost_c · delivered_quality
notes · created_at
```

`queue_wait_s = delivered_latency_s − worker_latency_s` — **derived, never
stored.** `[MEASURED]` bimodal: **13 warm @ 0.023s, 3 cold @ 3.762s.** A p50
reports it as negligible and is wrong about **1 turn in 5**.

### 3 · `thread_gaps` — SPEC, migration 067 `[RULED]` thread-scoped

```
gap_id PK (governor-minted) · thread_id · text (react's words, never rewritten)
status open|closed|abandoned · importance
opened_turn · opened_round · opened_at · opened_promise_version
attempted_by JSONB                     ← separates BUDGET from CAPABILITY at exit
closed_turn · closed_round · closed_at · exit_mode_at_close
reopened_count · last_seen_turn
INDEX (thread_id, status) · (status, exit_mode_at_close)   ← the build queue
```

Read at `state_load` (currently **412.7ms p50**, measure after). **Written once
at turn end**, in the attestation''s `finally`.

### 4 · Measured costs `[MEASURED]` 30–60 days

```
react round      quick 7.7s p50 / 13.4 p90   copilot 7.5 / 18.2   agentic 10.3 / 30.1
enricher                        5.2 / 10.3
critic                          9.6 / 16.9    ← fire-and-forget, OUTSIDE the promise
tool selection                  0.0003        ← free, never skip
tool manifest tokens            890 median (was 14,271)   93.8% cut
static prompt                   3,950 tok  (critical_rules 3,093 = 78.5%)
enricher prompt                 4,028 tok
turn-level tails                fast p90 33.9 · normal 56.1 · thinking 218.5
```

**Never sum p90s** — that is not the p90 of a sum. Use measured turn-level tails.

---

## PART II — THE LOGIC

### 5 · ADMISSION — at POST, once

```python
promise   = PROMISE[tier_of(chat_mode)]          # frozen
affordable(P) = Σ p50(p) for p in P  ≤  promise.latency_s
                AND measured_p90(config P)  ≤  promise.latency_s + promise.band

postures = largest P ⊆ SEQUENCE satisfying affordable(P)
```

**Skipping is what the tier IS** — not a round count, but which postures fit.

```
fast      FRAME → EXPLORE ─────────────────────────────► COMMUNICATE
normal    FRAME → EXPLORE ⇄ REFORMULATE → NARROW ──────► COMMUNICATE
thinking  FRAME → EXPLORE ⇄ REFORMULATE → NARROW → VALIDATE → COMMUNICATE
```

### 6 · THE ROUND ENVELOPE — declared before, compared after

```python
declare = { latency: [p25(posture), p90(posture)],     # a RANGE, never a point
            cost:    [lo, hi],
            quality: (a → b),                          # ordinal; recall unmeasured
            gap_targeted: gap_id | None,
            because: str }
```

A point estimate lies when the underlying is bimodal — **the queue wait proved
that.** Delivered outside the range is a finding **about the estimator**,
separable from a finding about the turn.

### 7 · POSTURE SELECTION — the state machine

```python
if not gap_list:                                    return FRAME
if trend(gaps_open) == INCREASING:                  return EXPLORE/DISCOVER
if g := best_worth_spending(open_gaps):
    return EXPLORE/REFORMULATE(g) if repeating(g) else EXPLORE/CLOSE(g)
if open_gaps and budget_nearly_spent:               return NARROW
if validate_worth_it():                             return VALIDATE
                                                    return COMMUNICATE
```

**`trend` is the only gap signal with evidence** `[MEASURED]`:

```
decreasing 41.5% | flat 41.0% | INCREASING 25.4%     ← only "increasing" informs
level: 1 gap 24.6% · 2 20.5% · 3 21.7% · 4 23.9%     ← FLAT. the level says nothing
```

**Because the list GROWS** — round 1 avg 0.46 → round 3 1.32. The denominator
moves, so *"% of gaps closed"* is not a percentage.

### 8 · CLOSE vs REFORMULATE — the free signal

```python
repeating(g) ⟺ jaccard(query_n, query_{n-1}) ≥ 0.70        # [GUESS] threshold
```

`[MEASURED]` consecutive `rag` queries **within** a turn: **24.5% ≥0.70,
52.5% ≥0.50.** Still the H0036 pattern — *"the model''s only real lever was
cosmetic query rewording"* — a month after the protocol written to stop it.

**This costs nothing to compute and separates two diagnoses that look identical
in gap counts:** the lever failed (change model/tool) vs **the question is
wrong** (change the question). No model and no tool fixes the second.

### 9 · IS A GAP WORTH A ROUND

```python
worth(g) ⟺ importance(g) ≥ MIN_IMPORTANCE                      # [GUESS]
       AND NOT stuck(g)
       AND remaining ≥ cost(round) + cost(acting_on_result)     # reserve BOTH

stuck(g) ⟺ age(g) ≥ 3 AND len(attempted_by(g)) ≥ 2 AND closed_last_round == 0   # [GUESS]
```

**Reserving the cost of acting is the condition usually forgotten.** Buying the
last round to *discover* a problem leaves nothing to fix it with.

**`stuck` → change the lever, not another round of the same.** `[MEASURED]` fires
on **182 of 837** multi-round turns (21.7%), avg round 4.5, and **66.7% of the
turn happens after it says stop** — 88.6s average. Worked example: one turn ran
the identical gap for **seven consecutive rounds**, 193.7s against a 95s promise.

### 10 · VALIDATE — value of information

```python
run_validate ⟺ remaining ≥ cost(validate) + cost(one_fix_round)
           AND quality_uncertain()
```

**Never a mode test.** `agentic` was a proxy for *expected difficulty*, which is
a forecast — replace it with the forecast, not another proxy.

```
tool_scores HIGH + confidence LOW   → a PROMPT lever. Good evidence, poor synthesis
tool_scores LOW  + confidence HIGH  → the dangerous quadrant. BUY THE VALIDATE
both high / both low                → the verdict changes nothing. Skip
```

**No single signal authorises spend** — least of all self-reported confidence,
the only signal produced by the thing being judged.

### 11 · ENRICHER vs DIRECT `[RULED]`

```python
use_enricher ⟺ rounds_used > 1 OR tools_used > 1
```

**The enricher earns its place when there is a lot to consolidate.** Skipping it
on the simple path saves **5.2s p50 / 10.3s p90 + ~4,028 tokens** — 40% of a 13s
promise, on turns that are **82% of all turns** (1,239 of 1,514 have zero gaps at
round 1).

**react''s 837 chars is its instructed target, not its ceiling** —
`react.format_rules` says *"2–4 short bullet points (each 10–25 words)"*. It
needs a **second output mode**, not a bigger prompt.

### 12 · EXIT MODE

```python
if exception:                                        ERROR
elif no open gap with importance ≥ MIN:              COMPLETE
elif all(attempts_ran_and_returned_nothing(g)):      CAPABILITY
else:                                                BUDGET
```

| exit | user is told | continuation |
|---|---|---|
| COMPLETE | the answer, **nothing about the promise** | no |
| BUDGET | *"a, b, c established; x, y, z open — I ran out of time"* | **yes, and cheap** — thread scope means it opens at CLOSE(x) |
| CAPABILITY | *"I have no source for x"* | **NO.** Retrying fails identically |
| ERROR | *"something failed on our side"* | yes, **gap list not authoritative** |

**Separating BUDGET from CAPABILITY requires `attempted_by`.** Without it the
system defaults to the flattering one — *"I ran out of time"* over *"we cannot
answer this."* **CAPABILITY exits aggregated across threads are a build queue**,
not a failure.

### 13 · CONFORMANCE

```python
kept    ⟺ delivered ≤ promised
in_band ⟺ delivered ≤ promised + band                 # three outcomes, not two
```

`[MEASURED]` first live breach: `fast` promised 13s, delivered 28.6s — **warm
dispatch, queue_wait 0.028s.** 28.58s of real worker time on a smoke probe
identical to one that took 7.8s eight minutes earlier. **Cause unknown, and not
to be guessed** — two explanations were offered today and both were wrong.

---

## PART III — MY CONTRACT

### 14 · What the governor promises every module

```python
estimate(inputs) -> {latency_ms, cost_c, confidence}    # you price yourself
run(inputs, directive) -> Output                        # pure; clock is an INPUT
AFFECTS = {"quality": ±, "latency": ±, "cost": ±}
PRECONDITIONS: list[str]                                # validity, not wisdom
```

**What I send:**
```python
Directive = { decision, because, gap_targeted, posture,
              budget: {latency_ms, cost_c, token_budget},
              promise_version, inputs_measured, inputs_estimated }
```

**What binds me:**

1. **Bound, never choose** where a module has its own optimiser. Overriding the
   bandit''s draw destroys the exploration that makes it work.
2. **The promise is frozen at POST.** No directive moves it.
3. **Errors are a precondition, never a budget term.** You can spend cost to buy
   quality; **you cannot spend errors to buy anything.**
4. **Free levers before priced ones** — gap prioritisation and prompt direction
   cost nothing.
5. **A refusal is binding.** `[RULED]` *"If they say no, you don''t have a
   choice."* My options are three: run without, widen only if the promise
   allows, or **not buy the round** — the one a naive governor never takes.
6. **Every decision records which inputs were measured and which estimated.**
7. **Nothing goes in until its producer exists; nothing comes out until its
   replacement does.** Both halves.

### 15 · What I do not have

| gap | consequence |
|---|---|
| **recall has no measure** | quality is ordinal. *"Gaps closed"* **is** recall — one hole, not two |
| `react_1` cost coverage **686/1,236** | spend understated **on the path I steer** → **fails open.** **Cost may INFORM a decision, it must not DECIDE one** |
| no **cost** envelope into model selection | latency bounds the bandit; cost does not. **7× price spread** |
| no per-call escalation | *same-round-better-model* is unavailable as a lever |
| per-tool latency is **declared, not observed** | 4 tools declare nothing, priced free. Recoverable from set-level co-occurrence |
| every posture threshold | **`[GUESS]`.** §7–9 count **unnamed strings** — re-derive on identified gaps before calibrating |

### 16 · Build order — dependencies, not preferences

```
1  thread_gaps + identity          ← everything else reads it
2  re-derive §7–9 on real ids      ← the [GUESS] constants become numbers
3  posture emit + shadow mode      ← inert proven on live traffic, not replay
4  exit_mode on the attestation    ← with the how that populates it
5  per-round draft emit            ← free perceived latency, Task #33 history attached
6  phase-1 extraction              ← then the prompt deletions it unlocks
```

**Step 2 is not optional.** Shipping §7–9''s constants as calibration would be
reading a division as a discovery — which this seat did twice today.
