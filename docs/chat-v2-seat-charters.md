# Chat v2 — seat charters

One document, not five, because the seams are the interesting part and they only
make sense against each other. Each seat owns a module; **the governor owns the
decisions and nothing else.**

`[RULED]` items are Ananth''s. `[MEASURED]` figures are from dev.

---

## The shared contract — every module implements this

```python
estimate(inputs) -> {latency_ms, cost_c, confidence}    # price me BEFORE the call
run(inputs, directive) -> Output                        # PURE; the clock is an INPUT
AFFECTS = {"quality": ±, "latency": ±, "cost": ±}
PRECONDITIONS: list[str]                                # validity, not wisdom
```

**A module the governor cannot price cannot be budgeted** — *"is one more round
worth it?"* is unanswerable if a component''s cost is learned only by paying it.

**Purity is not style.** A module that reads the clock or a global cannot be run
twice and compared — which is how v2 is proven inert against v1 on live traffic.

### Three rules every seat is held to, learned the expensive way this week

1. **Nothing goes in until its producer exists. Nothing comes out until its
   replacement does.** Both halves. A declared-but-unwritten field reads as a
   legitimate negative (`needs_route_clarification`: 4 fields, 0 writers, falsy
   defaults, invisible for a month).
2. **A rule that exists only as a comment is not a rule.** Four instances found
   in one day. Write the test, and shape it so **editing the guard cannot
   satisfy it**.
3. **Demonstrate, do not assert.** A green suite is not a written row. The
   attestation''s `write()` swallowed every INSERT behind 21 passing tests and
   would have shipped an empty table.

---

## SEAT 1 — Governor + Orchestrator v2 *(mobius-24, me)*

`[RULED]` **Ananth, 2026-09-11: *"no, you build, you own the orchestrator v2."***
**Seats 1 and 5 merge.** The governor and v2 are the same code — v2 *is* the
posture machine — so splitting them was an artefact of my own assumption that I
would not write production code.

**Owns:** the promise, the budget, the gap ledger, posture selection, exit mode,
the attestation, **and the loop that executes them.**

### 🔴 The verification relationship INVERTS, and it must

I argued *"Chat builds, I verify"* was the right division because the subject and
the author of a check should not be the same seat. **That argument does not stop
applying because the assignment changed — it points the other way now.**

**The chat seat grades v2 against v1.** They own `react_loop.py`, they supplied
the ten port hazards, and they have caught four of my errors today. **They are
the only seat that can tell whether v2 lost something v1 had.**

**What I must not do:** run the R0 equality assertion on my own build, or declare
a phase passed on my own reading of the six exit criteria. **I write the
criteria; someone else reads the result.** That was true when Chat built and it
is true now that I do.

| deliverable | state |
|---|---|
| Product Promise, 3 tiers, frozen at POST | **LIVE** — `turn_attestations`, migration 065, `mobius-chat-00982` |
| `thread_gaps` + governor-minted identity | **067 authored**, `docs/migrations/067_thread_gaps.sql` |
| posture machine + exit modes | spec''d — `docs/governor-system-logic.md` Part II |
| round envelope as a **range**, declared before | spec''d |

**What binds me:** bound, never choose, where a module has its own optimiser ·
the promise is frozen · **errors are a precondition, never a budget term** · free
levers before priced ones · **a module''s refusal is binding** `[RULED]` · every
decision records which inputs were measured and which estimated.

**What I do not have:** recall has no measure — *"gaps closed"* **is** recall,
one hole not two · every posture threshold is a `[GUESS]` calibrated on
**unnamed strings** and must be re-derived on real ids before it decides
anything.

---

## SEAT 2 — Tool Manifest

**Owns:** which tools react *sees*. **The Pareto lever** — `AFFECTS = {quality
+, latency −, cost −}`, the only module whose improvement needs no tradeoff.

| item | state |
|---|---|
| `estimate()` | **built** — runs the *real* selection (0.34ms, independently confirmed in `turn_spans`) and prices the actual result. **No cost model that can drift from the cost** |
| offered-set cost | **890 tokens median** (319–1,535) vs **14,271** — **93.8%** `[MEASURED]` 120 held-out questions, **question varied, manifest held constant** |
| refusal | **binding on the governor** `[RULED]`. Must be **explicit and reasoned** — *"nothing fits"* and *"here are two weak ones"* are different facts |
| what I send | `budget_ms` · `budget_c` · `token_budget` · `gaps_open`. **Never `tier`** — their refusal, and right: *a tier is a promise, difficulty is a forecast* |
| per-tool latency | **owner-declared, not observed.** 4 tools declare nothing and are priced free. **v1, not a blocker** — recovered from set-level co-occurrence over rounds |

**Open, volunteered by them:** `requires` **0 of 59**; authority never reached
`tool_version`; **Stage A has never filtered anything.** Every exclusion is
ranking. And *"the reduction is the Pareto win; the ranking is not yet a win at
all"* — three signals fused, unproven against BM25 alone.

**Owed to them:** `declared_version` on the attestation, so a declaration edit
cannot retroactively rewrite the accuracy history that was about to correct it.

---

## SEAT 3 — Prompts *(LLM Agent)*

**Owns:** what each profile says. **The governor owns which profile runs.**

| item | state |
|---|---|
| profile test | **four axes** — output contract · evidence posture · failure mode · success test. Match on all four ⇒ one profile with a parameter |
| profiles | `explore` · `synthesize` · `draft` · `critique` · **`communicate`** |
| `close` | **a DIRECTIVE, not a posture** `[RULED]`. Directives on EXPLORE: `DISCOVER` · `CLOSE(gap_id)` · `REFORMULATE(gap_id)` |
| `token_counts` | **built** (066) — `{tokenizer: count}` **map**, absent key = no stored count. 51/51 active blocks |
| delta at publish | **built** — per-tokenizer `{from,to,delta,pct}`, WARNING on growth |
| writers | **three collapsed to one** (`publish_block_version`) |
| `card.shape_schema` | **cut confirmed**: raw JSON schema only; field-rule prose stays as `enricher.how`, untouched. **Byte-diff with an empty allowlist** |

**The seam test that settles ownership disputes:**
> **"When/whether" belongs to the governor. "How" belongs to the prompt.**

So `is_complete`, retry timing and reframe timing are **mine** — marked
governor-candidate, **not removed**, savings quoted conditionally. **The
extraction and the prompt shrink are one project seen from two ends.**

**v2 reads prompts from `prompt_blocks` ONLY.** `[RULED]` No prompt text in v2
code. The Python constants stay as the seed until v1 retires — *nothing comes
out until its replacement is proven.*

---

## SEAT 4 — LLM Manager / bandit

**Owns:** which model runs. **The governor bounds the envelope; the bandit
chooses inside it.** Overriding its draw destroys the exploration that makes it
work.

| term | state |
|---|---|
| **latency** | **LIVE** — `latency_budget_ms` is a **hard pre-filter before Thompson sampling**, not a nudge; the governor is already the caller. Degrades correctly: keeps the fastest candidate rather than failing the turn |
| **cost** | `[OPEN]` — **a token budget is not a cost budget.** `[MEASURED]` 2.56¢ (flash) vs 18.6¢ (pro): **7× spread**, and it is the widest-swing lever in the system |
| **quality** | indirect — `bandit_weights` composite keyed by `chat_mode`, not by the promise |
| per-call escalation | `[OPEN]` — makes *same-round-better-model* unavailable |

**Two asks, neither v2''s to fix:** `react_1` cost coverage **686/1,236** —
understated **on the path the governor steers**, and an understated spend
**fails open**, permitting rounds it should refuse. **Until it is closed, cost
may INFORM a decision and must not DECIDE one.** And `llm_calls.turn_id` is
**NULL on all 25,310 rows** while `chat_turns` has no `turn_id` column at all —
**join on `correlation_id`, never `turn_id`.**

---

## SEAT 5 — Chat seat *(grader, and owner of v1)*

`[RULED]` **v2''s build moved to Seat 1.** This seat now owns **v1 until it
retires**, and — more importantly — **grades v2.**

**Owns:** `react_loop.py` v1 · the ten port hazards
(`docs/orchestrator-v2-port-hazards.md`) · **the R0 equality assertion** · **the
verdict on each phase''s six exit criteria.**

**Why this seat and not mine:** they are the only one who can say whether v2 lost
something v1 had. Hazard 1 alone — `max_it` grows mid-turn, so a `range()` loop
**silently drops every extension and the tests pass** — is a defect no author
finds in their own code.

`react_loop.py` is **6,451 lines, 61 functions**, against a ratchet of **2,560**
set by a prior split — **2.5× past it, and that test is in the known-failing
baseline.** Incremental refactoring of this file has a track record here and it
is negative.

**v2 = the posture machine (~15 formulas) + module calls through the contract — built by Seat 1, graded here.**

**Routing, never forking.** `R0` shadow → `R1` single-round `fast` (**82% of
turns have zero gaps at round 1**) → `R2` all fast → `R3` +normal → `R4` all.
One flag at POST, recorded as `orchestrator_version`. **No turn is ever handled
by both** — two orchestrators sharing write state is the two-writer defect at
maximum scale.

**Exit criteria per phase, ≥200 turns, all six:** `in_band` ≥ v1 · no new breach
class · attestation integrity (`turns == rows`, 0 dupes, `queue_wait ≥ 0`) ·
**no rise in `CAPABILITY`** (that means v2 stopped reaching tools) ·
**`gaps_closed` per turn ≥ v1** (v2 must not buy fewer answers for its latency) ·
zero `unknown` outcomes.

---

## SEAT 6 — Chat FE *(when it is engaged)*

Not yet briefed. Two things will land on it: the **per-round draft** (emit
frequency, **no schema change** — `draft_ready` already exists and fired 1,231
times against ~1,266 turns, i.e. **once per turn**), and the **exit-mode
surface** — `open_items` and `continuation_offered` as **separate fields**, so a
CAPABILITY answer can name what is missing **without implying it is
retrievable.**

---

## Dependency order — not preference

```
1  thread_gaps + identity        (governor)      ← everything reads it
2  re-derive posture constants   (governor)      ← [GUESS] becomes measured
3  v2 skeleton + posture machine (chat)          ← reads prompt_blocks, calls contracts
4  R0 shadow on live traffic     (chat)          ← equality asserted, v1 decides
5  attestation columns           (chat)          ← each WITH its populating how
6  per-round draft emit          (chat)          ← free perceived latency
7  R1 → R4                       (chat)          ← on §5's six criteria
8  retire v1 + every deletion catalogued this week
```
