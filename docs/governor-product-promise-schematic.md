# The Governor as Product Promise — schematic

**Ananth's concept, 2026-09-10:** *"this is my product promise concept.. we start with an
SLA (who is calling, user, mode etc).. and the role of this agent is to get the best
possible answer to meet the SLA.. we will figure out how to do it."*

**Schematic only. No code. Ananth's sign-off gate holds.**
Companion to `docs/p3-governor-extension-gate-collab.md` (the current-state evidence).
Provenance tags as elsewhere: `[READ]` · `[MEASURED]` · `[LIVE]` · `[UNVERIFIED]`.

---

## 1. The concept in one line

> **An SLA comes in. The governor's job is to spend the budget it implies to get the best
> answer it can, and then tell the integrator what it actually got.**

Everything else — rounds, extensions, depth, consolidation, finalisation — is *how* it
spends. The promise is the thing that is owned.

**The object already exists.** `ProductPromiseContract` [READ, `governor.py:75`] is the
SLA: `max_rounds`, `max_extension_rounds`, `confidence_bar`, `soft_target_s`,
`hard_ceiling_s`, `tone`, `reasoning_visibility`. **What is missing is that it is derived
from the MODE alone** — not from who is calling.

---

## 2. The schematic

```
  ┌── SLA ─────────────────────────────────────────────────────────────────────┐
  │  caller identity   user / API key / service        ← NOT AN INPUT TODAY    │
  │  mode              quick · copilot · agentic · task                       │
  │  query intent      extract_query_intent_floor(message)                    │
  │  infra ceiling     MOBIUS_TURN_DEADLINE_S = 300s          [LIVE]          │
  └───────────────────────────┬───────────────────────────────────────────────┘
                              ▼
  ╔══ PHASE A — SCOPE (once, before round 1) ═════════════════════════════════╗
  ║  build the contract:  rounds · extensions · confidence bar                ║
  ║                       soft_target_s · hard_ceiling_s                      ║
  ║  resolve depth:       intent floor → reasoning depth → latency budget     ║
  ║  scope the planner:   what it may call, how deep, how long it has         ║
  ║  ── EXISTS TODAY, scattered across 5 functions and unnamed ──             ║
  ╚═══════════════════════════┬═══════════════════════════════════════════════╝
                              ▼
  ╔══ PHASE B — SPEND (every round) ══════════════════════════════════════════╗
  ║                                                                           ║
  ║   round result ──► RoundState ──► evaluate() ──► directive + reason        ║
  ║                                                                           ║
  ║        finalize     budget exhausted — ship what we have                  ║
  ║        complete     bar met — ship                                        ║
  ║        extend       quality gap + budget left — buy a round               ║
  ║        consolidate  time low — synthesize, no more tool calls             ║
  ║        search       keep gathering                                        ║
  ║                                                                           ║
  ║   quality signals ASK; they do not take:                                  ║
  ║        groundedness floor ─┐                                              ║
  ║        completion critic  ─┼──► request_extension(reason) ──► granted?    ║
  ║        (future signals)   ─┘                     └─► refused(WHICH guard) ║
  ║                                                                           ║
  ║  ── EXISTS as evaluate(); the ASK interface does NOT — today two callers  ║
  ║     increment the ledger directly and contradict each other ──            ║
  ╚═══════════════════════════┬═══════════════════════════════════════════════╝
                              ▼
  ╔══ PHASE C — HAND OFF (once, at the end) ══════════════════════════════════╗
  ║  the promise, kept or not, as an INSTRUCTION to the integrator:           ║
  ║     · did we meet the bar, or ship short — and why                        ║
  ║     · what is unverified, and must be said out loud                       ║
  ║     · what was cut for time                                               ║
  ║     · tone + reasoning_visibility from the SLA                            ║
  ║  ── DOES NOT EXIST. The directive is written to ctx, read ONCE, and       ║
  ║     lands in a human-readable trace. The integrator never sees it. ──     ║
  ╚═══════════════════════════┬═══════════════════════════════════════════════╝
                              ▼
                        integrate → answer
```

---

## 3. What is already in the governor, what moves in, what is missing

| | today | under the promise |
|---|---|---|
| **the SLA object** | `ProductPromiseContract`, built from **mode only** [READ] | + caller identity |
| **budget** | `_MODE_DEFAULTS` — quick 2/0, copilot 3/1, agentic 10/3, task 3/0 [READ] | unchanged, per-caller override possible |
| **depth** | `extract_query_intent_floor` · `resolve_reasoning_depth` · `agent_role_to_reasoning_depth` · `latency_budget_ms` — **already here, called from `react_loop` and `prompts`** [READ] | **named as Phase A** |
| **the round decision** | `evaluate()` — pure, 5 directives, first-match [READ] | unchanged; this is the good part |
| **extension grants** | **2 writers, inline in `react_loop.py`** at `:5420` and `:5526` [READ] | **move in** as `request_extension()` — one writer |
| **the final hand-off** | `ctx.product_promise_directive` → `make_react_trace(final_directive=…)` → a diagnostics string [READ] | **new**: a contract the integrator consumes |

---

## 4. 🔴 Three parts of the promise are already inert

Found while tracing the SLA object. All three are declared and unread — the shape this
program keeps finding, this time inside the contract that is supposed to be the promise.

**1 · `tone` and `reasoning_visibility` have no readers outside `governor.py`** [MEASURED
— grep across `app/`, zero hits]. They are fields of the SLA that nothing consumes. **They
are exactly Phase C material** — how the answer should read is a promise term — and they
are sitting in the object already, unused, because there is no Phase C to consume them.

**2 · `scale_ceiling_for_intent()` has no effect today, and says so.** Its own docstring
[READ, `:413-427`]: *"Because `default_contract_for_mode()` already sets `hard_ceiling_s`
to exactly `_turn_deadline_seconds()` for every mode (no per-mode headroom below the infra
deadline today), this scaling has NO visible effect until `MOBIUS_TURN_DEADLINE_S` itself
is raised."* **A deep-intent query cannot buy more wall-clock, because the contract already
promises the entire infra deadline to every mode.**

**That is the SLA's central weakness in one line: every mode promises the same 300
seconds.** `soft_target_s` differs (6 / 12 / 120 / 15) but `hard_ceiling_s` is 300 for all
four. So the *only* per-mode budget that actually binds is rounds and the soft target —
the ceiling is common, which is why a `quick` turn and an `agentic` turn have the same
hard stop.

**3 · The caller is not in the SLA at all.** No user, no API key, no service identity
reaches `default_contract_for_mode()`. So *"who is calling"* — the first term in Ananth's
formulation — is the one input the current contract cannot see.

---

## 5. What the promise makes possible that today's design cannot

**a · Per-caller SLAs.** An API caller with a 5-second budget and a UI user with 300 are
the same contract today. Adding caller identity to Phase A is the smallest change with the
largest reach — and it is the same shape as the `tool_manifest` seat's Stage A authority
filter, which starts from the caller too.

**b · Quality signals that ask.** Today the completion critic **takes** budget the
governor would have refused: between **120s** (governor stops extending, `elapsed_s <
soft_target_s`) and **275s** (critic's `+25` reserve against 300) the governor says
`consolidate` while the critic funds more gathering. **155 seconds of direct contradiction
on every agentic turn** [READ, `governor.py:196,206` + `react_loop.py:5420`]. Under
`request_extension()` that becomes one recorded decision — and *"refused: already
consolidated"* is a row somebody can count.

**c · An integrator that knows what it was handed.** The CARC 197 answer stated *90 days*
confidently while its own disclaimer said the timeframe was unsupported. **The integrator
had no directive telling it the turn ended short.** Phase C is the fix, and it is a
hand-off contract, not a prompt tweak.

**d · A promise that can be reported.** *"Agentic promises a high confidence bar within
120s and met it on N% of turns"* is currently unanswerable — the directive exists per turn
and aggregates nowhere.

---

## 6. What I would decide before building, and who decides it

| # | question | owner |
|---|---|---|
| 1 | **should a quality signal be able to buy rounds after the budget authority has consolidated?** (§5b — the 120s/275s contradiction) | **Ananth** |
| 2 | is `hard_ceiling_s` per-mode, or does every mode keep promising the whole infra deadline? | **Ananth** — it is what makes `scale_ceiling_for_intent` inert |
| 3 | what does the caller term of the SLA contain — identity, a named tier, or a budget? | **Ananth** |
| 4 | is Phase C a structured object or prose in the integrator's prompt? | design; mine to propose |
| 5 | does Phase A also scope the *planner's* opening plan, or only its budget? | Ananth's framing says planner is in scope — needs a line |

**Question 1 is the one that unblocks the P3 pass.** Everything else can be phased.

---

## 7. What this is not

- **not a rewrite of `evaluate()`** — the round decision is the part that works
- **not P5's config UX** — this is what makes that UX have something coherent to edit
- **not the tool selector** — that seat owns *which tools*; the governor owns *how much
  budget and to what standard*. They meet at Phase A, and both start from the caller.

---

# 8. Deriving the extension budget from real data, instead of 0 / 1 / 3

**Ananth, 2026-09-10:** *"we should use real data to make determinations for part b — on
how many extensions, as against this made up 2 or 3 etc. lets get into the logic of doing
that too."*

**The current numbers have no derivation.** `_MODE_DEFAULTS` [READ, `governor.py:89-94`]
declares `quick 0 · copilot 1 · agentic 3` with a comment citing a spec section, not a
measurement. **They are a starting guess that has never been checked against outcomes.**

## 8.1 The question the data has to answer

Not *"how many extensions feel right"* but:

> **Does the Nth extension change the outcome often enough to be worth a round?**

An extension costs one round — LLM calls, tool calls, wall-clock. It earns its keep only
if it **closes the gap that triggered it**. So the budget is where the **marginal value of
the next extension** falls below its cost. Same shape as RAG's recall@k curve: you buy
depth until the curve flattens.

**Both triggers state their own success condition, which is what makes this measurable:**

| trigger | granted because | **closed** if, next round |
|---|---|---|
| groundedness floor | `groundedness_passed is False` | groundedness passes |
| completion critic | `_cc_verdict.satisfied is False`, with `uncovered` gaps | those gaps no longer uncovered |

**Neither is a judgement call.** The turn already computes both verdicts.

## 8.2 What is already queryable — more than I expected

`react_trace` persists **as JSON inside `chat_turns.thinking_log`** [READ,
`emit_envelope.py:11,41,164`], and its `rounds` array carries **one dict per round**:

```json
{"round": 2, "directive": "consolidate", "reason": "...",
 "agent_role": "synthesize", "composition_id": 26, "elapsed_s": 70.9}
```

So **available today, no new instrumentation:**
- the **extension ordinal** — count `directive == "extend"` in order within a turn
- **`elapsed_s` at the moment of each extension**
- `rounds_used` / `max_rounds`, `final_directive`, `groundedness_passed` (turn-level)

**Two questions can therefore be answered this week, from data already on disk.**

## 8.3 🔴 But half the extensions are invisible, and it is the two-writer problem again

**The critic's extension at `react_loop.py:5420` is not a `governor.evaluate()` call**, so
**it produces no per-round `directive`** [READ]. Only the governor's extensions appear as
`directive == "extend"` in the trace.

**So `rounds[].directive == "extend"` undercounts extensions by exactly the critic's
share, and there is no way to tell from the trace how large that share is.** The
architectural defect and the measurement gap are the same defect: **two writers, one of
which does not report.**

**Which means the ordering is forced, and that is useful rather than annoying:** unify the
writers first (§3's `request_extension()`), and the data needed to set the budget starts
existing as a side effect. **The refactor is the instrumentation.**

## 8.4 What must be recorded, per extension request

Small, specific, and it is the same list §4 row 10 already proposed:

| field | why |
|---|---|
| `ordinal` | 1st / 2nd / 3rd — the whole curve is conditioned on this |
| `trigger` | `groundedness` · `coverage` · future | different curves; do not pool them |
| `granted` / `refused` | and **which guard refused**: ledger · deadline reserve · consolidated · mode |
| `elapsed_s` at request | answers §8.6 — whether count or time is the real constraint |
| `outcome_next_round` | did the triggering condition clear? **the numerator** |
| `mode` | the budget is per-mode, so the curve must be too |

**`refused` is not optional.** A curve built only on granted extensions is conditioned on
the budget it is trying to set — the classic circularity. **The refusals are what tell you
whether a bigger budget would have helped.**

## 8.5 The decision rule

For each mode, for each ordinal N, over turns that **reached** N:

```
close_rate(N) = closed_after_extension_N / granted_extension_N
```

**Set the budget at the largest N where `close_rate(N)` clears a stated bar.** The bar is
a product choice, not a statistical one — *"an extension must close the gap at least X% of
the time to be worth ~R seconds"* — and it is Ananth's to set, once the curve exists.

**Three traps, named because each would produce a confident wrong number:**

**1 · Survivorship.** Turns reaching extension 3 are the hard ones. **`close_rate(3)`
must be computed over turns that reached 3, never over all turns**, or the denominator
flatters the tail.

**2 · The curve is not monotonic and should not be assumed to be.** A second extension may
help *more* than the first if the first bought the evidence the second needed. **Report
the raw rates; do not fit a decay.**

**3 · Refused-but-would-have-closed is unobservable**, so the curve can only tell you
where to *stop*, never where to *start*. **Widening the budget requires an experiment**
(temporarily raise it in one arm), which is exactly the A/B machinery the tool-selection
spec already describes.

## 8.6 The question I would answer first, because it may make the budget moot

**Is the count even the binding constraint?**

Today the governor will not extend once `elapsed_s >= soft_target_s` — **120s for
agentic** [READ, `governor.py:196,206`]. So if most extension requests arrive after 120s,
**a budget of 3 is fiction: time binds first and the count never runs out.**

**This is answerable right now from `rounds[].elapsed_s` in `thinking_log`** — the
distribution of elapsed at each `extend`, against the 120s line. **No new instrumentation,
no ruling needed.**

**If time binds first, the honest fix is `soft_target_s`, not `max_extension_rounds`** —
and every conversation about "2 or 3" was about the wrong number.

## 8.7 Sequencing

1. **measure the elapsed distribution at extension time** — existing data, answers §8.6
2. **unify the writers** (§3) — makes extensions countable at all
3. **record the six fields** (§8.4) — small, and follows from 2
4. **build the curves per mode and ordinal** — a week of traffic, and dev traffic is thin
   (217 `state_load` turns / 11h), so this is days not hours
5. **Ananth sets the bar**; the budget follows from the curve
6. **widen only by experiment**, never by argument (§8.5 trap 3)

**Steps 1 and 2 are worth doing regardless of the budget question**, which is the argument
for doing them first.
