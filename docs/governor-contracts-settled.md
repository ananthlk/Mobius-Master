# Governor ↔ module contracts — what is settled, 2026-09-11

Written at Ananth's instruction: *"write all changes first… we have the
instructions for tool. Did we land on prompts contract set? Then the llm manager
— which is more what we do today, nothing new. Then we can include others and go
to chat."*

Every figure `[MEASURED]` against dev. Provenance: read-time and what varied are
stated where a table could be mistaken for an experiment.

---

## The uniform contract — all modules

```python
estimate(inputs) -> {latency_ms, cost_c, confidence}   # price me BEFORE the call
run(inputs, directive) -> Output                       # pure; clock is an INPUT
AFFECTS = {"quality": ±, "latency": ±, "cost": ±}      # signed, per term
PRECONDITIONS: list[str]                               # validity, not wisdom
```

**A module the governor cannot price cannot be budgeted.** Estimates are
compared to delivered and the drift is a finding, not a failure.

### Rules binding the governor, not the modules

1. **Bound, never choose** where a module has its own optimiser.
2. **The promise is frozen at POST.** No directive may move it.
3. **Errors are a precondition, never a budget term.** You can spend cost to buy
   quality; you cannot spend errors to buy anything.
4. **Free levers before priced ones.**
5. **Every decision records which inputs were measured and which estimated.**

---

## 1 · TOOL EXPOSURE — SETTLED, and built on their side

**Owner:** Tool Manifest seat.

| item | state |
|---|---|
| `estimate()` | **built** — runs the *real* selection (0.34ms) and prices the actual result; no cost model that can drift. Independently confirmed: `turn_spans.tool_manifest` = 0–1ms over 260 spans |
| offered-set cost | **890 tokens median** (319–1,535), against **14,271** before — **93.8% reduction** `[MEASURED]` 120 held-out questions, **question varied, manifest/threshold/cap held constant** |
| shortlist size | cap is **3 specific tools**; 5 is an *outcome* (`refuse` + specific + `rag`) |
| what I send | `budget_ms` · `budget_c` · `token_budget` · `gaps_open` |
| what I do NOT send | **`tier`** — their refusal, and correct: *a tier is a promise, expected difficulty is a forecast.* **Send the budget the tier resolves to.** Keeps promise→number translation in one place |
| refusal | **binding on me.** *"If they say no you don''t have a choice"* — Ananth. Must be **explicit and reasoned**, never a thin set: *"nothing fits"* and *"here are two weak ones"* are different facts |
| latency input | **owner-DECLARED, not observed.** 4 tools declare nothing and are priced free — wrong in a knowable direction. **v1, not a blocker** |
| per-tool observed timing | `[OPEN]` — `turn_spans` is module-granularity; `chat_tool_results` has **no duration column**. Recovered instead from **set-level co-occurrence** over rounds, the way the bandit learns per-model quality it never attributes directly |

**Open on their side, volunteered:** `requires` **0 of 59** populated; authority
never reached `tool_version`; **Stage A has never filtered anything.** So every
exclusion is *ranking*, all of it mine to budget against — except `refuse`,
offered first always, Ananth''s ruling, not mine to touch. And: *"the reduction
is the Pareto win; the ranking is not yet a win at all"* — three signals fused,
unproven against BM25 alone.

**What I owe them:** `declared_version` on the round attestation, so an owner
updating a declared latency cannot retroactively rewrite the accuracy history
that was about to correct it. Same defect class as the promise version pointing
at an editable file.

---

## 2 · PROMPTS / PROFILES — SET, minus two names

**Owner:** LLM Agent (prompt seat).

### Landed

| item | state |
|---|---|
| **profile-required test** | **four axes** — output contract · evidence posture · failure mode · success test. Match on all four ⇒ one profile with a parameter, not two |
| **profiles agreed** | `explore` · `synthesize` · `draft` · `critique` — all four pass the test |
| `token_counts` | **built** (migration 066). `{tokenizer: count}` **map, not integer**; absent key = no stored count. 51 active blocks, all 51 populated, 3 derived correctly `{}` |
| computed | Vertex `countTokens` at publish, in `publish_block_version()` |
| **my consuming rule** | **MAX across candidate tokenizers** — I bound *before* the bandit chooses, so only the pool is known; and an under-counted prompt **fails open**. MAX **fails closed** |
| fallback | chars//4 permitted **only if the estimate records it was a fallback** |
| delta at publish | **built** — per-tokenizer `{from,to,delta,pct}`, WARNING on growth, never fabricated from a missing count |
| writers | **three collapsed to one** — `publish_block_version()`; verified one `INSERT INTO prompt_blocks` remains |

### The measured prompt inventory `[MEASURED]`

`react_draft` / `react_explore` / `react_synthesize` are **the identical seven
blocks in the identical order** — separate keys, one prompt. **The seams are cut
and empty.**

| block | tokens | share |
|---|---|---|
| `react.critical_rules` | **3,093** (now 3,233 @v8) | **78.5%** |
| `react.response_shape` | 482 | 11.2% |
| `react.format_rules` | 344 | 8.9% |
| `react.tool_manifest` | template — ~14,271 → **890** injected | — |
| identity / mode_quality_bar / user_profile | 186 | 1.1% |

`critical_rules` splits three ways by the four-axis test: **tool-decision
(~half, explore-only)** · **evidence/citation discipline (shared)** ·
**round-completion heuristics (governor-owned, see §5)**.

### The seam test that settled the arguments

> **"When/whether" belongs to the governor. "How" belongs to the prompt.**

`is_complete` rules, retry timing, reframe timing → **mine.** Tool-choice
guidance, citation shapes → **prompt.** So **the extraction and the prompt
shrink are one project seen from two ends.**

**Sequencing rule, absolute:** mark governor-candidate content, **do not remove
it**, quote its saving as conditional. **Removing the current decider before its
replacement exists is the trap.**

### `[OPEN]` — blocking their split

**What do `close` and `communicate` mean?** Both seats stopped rather than guess.
Their hypothesis and mine agree — `close` may be a directive-level decision, not
a profile; `communicate` may be delivery rather than a distinct LLM call — **but
committing block boundaries to a guess means redoing the split.**

---

## 3 · LLM MANAGER / BANDIT — mostly already what we do

**Owner:** llm_manager. **Ananth: *"nothing new."* Correct — two-thirds exists.**

| term | control into model selection | state |
|---|---|---|
| **latency** | `latency_budget_ms` **hard pre-filter before Thompson sampling** — `model_registry.py:1899-1915`; governor already the caller at `react_loop.py:4813` | **LIVE.** Their docstring names us: *"a caller with a real deadline (e.g. ReAct''s Product Promise governor nearing its hard ceiling) gets a guarantee, not just a probabilistic lean"* |
| **cost** | **none** | `[OPEN]` — there is a *token* budget, which is **not a cost budget**: per-turn cost ran **2.56¢ (flash)** vs **18.6¢ (pro)**, a **7× spread** |
| **quality** | `bandit_weights` composite per `chat_mode` | indirect — mode-derived, not promise-derived |
| per-call escalation | **none** | `[OPEN]` — I can bound latency; I cannot say *"this call, spend more."* Which makes **same-round-better-model** unavailable as a lever |

**Degradation is already correct:** if the latency filter empties the pool it
keeps the single fastest candidate rather than failing the turn.

**Cost discipline until coverage is fixed:** `react_1` reports cost on **686 of
1,236** calls — understated **on precisely the path I steer**, and an
understated spend **fails open**, permitting rounds it should refuse. **So cost
may INFORM a decision and must not DECIDE one.** Time can decide; the promise
clock is complete. The coverage figure travels with the number.

---

## 4 · What I own, and what I built the case for tonight

**Gap ledger — mine, per Ananth.** Governor-minted ids, **injected into the
prompt**, answered by reference (`closed: [G3]`, `new: [...]`). React does zero
bookkeeping. Fields: `id · text · opened_round · importance · attempted_by ·
closed_round · reopened_count`.

### Posture — my output, the prompt''s input

```
FRAME/EXPLORE ──► CLOSE ◄──► REFORMULATE ──► NARROW ──► VALIDATE ──► COMMUNICATE
```

**Steps are skippable, and skipping is what the tier IS** — not a round count
but *which postures are affordable*.

### What the data says `[MEASURED]` 60 days

| finding | number |
|---|---|
| P(all gaps close next round) | **flat 20–24%** for any non-zero count. **The level carries no signal** |
| why | **the gap list GROWS**: round 1 avg 0.46 → round 3 1.32. The denominator moves, so "% closed" is not a percentage |
| trend | decreasing 41.5% · flat 41.0% · **increasing 25.4%** — only *increasing* is informative |
| **REFORMULATE trigger** | consecutive `rag` queries within a turn: **24.5% near-duplicate or identical**, 52.5% ≥0.50 overlap. **Still the H0036 pattern**, a month after the protocol written to stop it |
| **stuck-gap rule** | fires on **182 of 837** multi-round turns (21.7%), avg round 4.5, and **66.7% of the turn happens after it says stop** — 88.6s average |

`[OPEN]` **All of the above counts UNNAMED strings.** Two "gaps" may be one gap
rephrased. **These numbers argue the ledger is worth building; they are NOT the
calibration.** Re-derive on identified gaps before setting any threshold.

### Step costs `[MEASURED]`

```
react round     quick 7.7s p50 / 13.4 p90    copilot 7.5 / 18.2    agentic 10.3 / 30.1
enricher                       5.2s / 10.3
critic                         9.6s / 16.9   ← fire-and-forget, OUTSIDE the promise
tool selection                 0.0003s       ← free, never skip
```

**Do not sum p90s** — that is not the p90 of the sum. Use measured turn-level
tails: fast p90 **33.9s**, normal **56.1s**, thinking **218.5s**.

**Bands, per Ananth''s ± relaxation:** fast 13±5 · normal 31±8 · thinking 95±25.
The attestation becomes `in_band` with three outcomes, not a boolean. **Widening
a band is a product decision and needs a new `promise_version`** — otherwise a
missed promise gets fixed by moving the tolerance.

---

## 5 · Withdrawn tonight, retained as corrections

| claim | why withdrawn |
|---|---|
| "chars//4 under-counts ~5%, systematic" | **content-dependent.** Both my samples were manifest-like text on the same tokenizer; prose ran **3% OVER** |
| "multiple active `prompt_blocks` rows are a hygiene bug — add a uniqueness constraint" | **it is the designed rollback chain.** A constraint would have **broken rollback** |
| "critical_rules grew unwatched, like the manifest to 57 tools" | **2 of 5 jumps are replacements with cited incidents.** Growth real; the cause was mine, not measured |
| "validate is structurally impossible on fast (9.6s of 13s)" | **the critic is already fire-and-forget** (`schedule_post_run_adjudication`) — never in the latency budget |
| "move the promise to first delivery" | first delivery is not the answer — see below |
| ~~"kill the enricher, fold its schema into a draft profile"~~ | **WITHDRAWAL ITSELF WITHDRAWN — see below.** The 9.6× measures instruction, not capability |

### The enricher question — REOPENED, and the 837 explains itself

Ananth: *"react did the 837 chars because we have been asking it to summarise —
we never asked it to produce a final answer."* `[READ]` **Confirmed in the
prompt itself.** `react.format_rules`:

> *"Start with ONE bold sentence… Follow with **2–4 short bullet points (each
> 10–25 words)**… **Do NOT write paragraphs.**"*

**2–4 bullets at 10–25 words IS 837 characters.** react is not falling short of
8,000 — **it is hitting its instructed target exactly.** So the 9.6× measures
the gap between *what we ask react for* and *what we ask the enricher for*. It
says nothing about capability, and **"a fold is a transplant" is unsupported.**

`[DESIGN]` **Fourth instance today of one error: reading an artifact of
instruction as a property of the system.** The others — a tier comparison that
fanned one question across three tiers, a chars//4 bias measured only on
manifest-like text, and a growth curve whose cause I supplied rather than
measured. **Every one was caught by asking what varied.**

### The decision rule — Ananth''s, and it is budgetable at admission

> **The enricher earns its place when there is a lot to consolidate. It does not
> when there is not.**

| turn shape | path |
|---|---|
| 1 round, 1 tool, evidence fits in one pass | **react writes the final answer. Skip the enricher.** |
| N rounds, many tools, evidence spread wide | **enricher consolidates.** Keep it |

**Round count and tool count are already what the posture forecast produces** —
this is the same forecast used for a second decision, not a new signal.

**Saving on the simple path: 5.2s p50 / 10.3s p90 plus ~4,028 prompt tokens** —
40% of a 13s promise, on the turns that are **82% of all turns** (1,239 of 1,514
have zero gaps open at round 1).

**Cost: react needs a second OUTPUT MODE, not a bigger prompt.** Today
`format_rules` is one instruction set. It needs two — *summarise for downstream
consolidation* (~837 chars, today) and *write the final answer*
(enricher-quality, ~7,300 chars).

**Which collapses two open questions into one.** `COMMUNICATE` **is react''s
final-answer output mode**, and the enricher is the fallback when there is too
much to consolidate in one pass. They differ on **output contract** and
**success test** — two of the prompt seat''s four axes — so they are genuinely
different profiles, not one with a parameter.

**Provenance note on that last one:** an intermediate version compared the
ledger''s `running_answer` (497) to `chat_turns.final_message` (8,171) and
attributed the whole gap to the enricher. `integrate.py:988` **reassigns**
`final_message`, so that comparison mixed two different objects. The 9.6×
above compares `card.react_draft` to the final card — the right pair.

---

## 6 · The per-round draft — a regression with a dated cause

**Ananth: the draft only reaches the user at the end; it should arrive every
round.** Confirmed, and it was deliberate:

`react_loop.py` **Task #33, 2026-08-05** — the per-round live `draft_ready`
event was removed because it streamed **raw tool-result text** (document chunks,
`"[1] file.pdf (p.18)…"`) *"as if it were the draft answer (and could clobber a
real draft already set)."* Replaced with `append_evidence_checkpoint()` — **no
live event.**

**The removal was correct; it fixed the symptom, not the cause.** There was no
per-round *synthesised* draft to stream. Today `append_draft_answer` fires once,
at `orchestrator.py:873`, with `ctx.final_message` — **at the end of react.**

**All three pieces for the fix already exist and are not connected live:**

| piece | state |
|---|---|
| producer — `evidence_review.running_answer`, every round | ✓ exists |
| renderer — `card.reasoning_trace` progression (rd-1 → rd-last) | ✓ exists |
| channel — live per-round event | ✗ removed, Task #33 |

**This buys perceived speed with no step skipped and no budget spent** — the
only latency win that costs nothing. `[OPEN]` Work order for Chat Master, with
the Task #33 history attached so nobody reverts to streaming raw evidence.

---

## 7 · Open, in dependency order

| # | item | owner | blocks |
|---|---|---|---|
| 1 | **`close` / `communicate` meaning** | **Ananth** | the prompt split |
| 2 | **gap ledger: turn-scoped or thread-scoped?** | **Ananth** | the identity scheme |
| 3 | gap identity + lifecycle | **me** | posture, `gap_closed`, everything |
| 4 | re-derive §4 numbers on identified gaps | me | posture thresholds |
| 5 | per-round draft emit | Chat Master | perceived latency |
| 6 | phase-1 extraction, shadow-proven | Chat Master | prompt deletions |
| 7 | cost envelope into model selection | llm_manager | the widest lever |
| 8 | `react_1` cost coverage 686/1,236 | llm_manager | cost deciding anything |
| 9 | `integrator_critic` 9.6s p50 — unexamined | ? | nearly 2× the enricher |
