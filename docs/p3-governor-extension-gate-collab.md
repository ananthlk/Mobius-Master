# P3 — `governor` + `completion_extension_gate`: current state → future state

**A COLLABORATION DOCUMENT.** Platform seat (mobius-c2) and Chat Master, working on the
same file. Not a work order — a shared understanding to be argued with before anything is
built.

**🔴 NO CODE UNTIL ANANTH SIGNS OFF.** His instruction, 2026-09-10: *"create a document
for you and chat to collaborate on what things need changing, the current state and the
future state.. do not code until i sign off."* Every row in §4 is a proposal.

**Provenance tags, as in the other documents:** `[READ]` = I read that line ·
`[MEASURED]` = computed, method stated · `[UNVERIFIED]` = believed, not established ·
`[CHAT]` = for Chat Master to fill in or correct.

---

## 1. Why these two nodes, and why together

They are **one problem**. P3's ratified gate metric is literally *"modules that can grant
an extension round: 2 → 1"*, and the rubric agrees:

| node | rating | the shape of it |
|---|---|---|
| `governor` | **amber** — 6 open · **3 of 3 handlers swallow** · 1 telemetry site | 432 lines, decides the round directive |
| `completion_extension_gate` | **red** — **0 lines**, no logs, no telemetry | **has no file.** It is inline code inside `react_loop.py` |

`completion_extension_gate` reading **0 lines** is not a measurement error. **The node has
no module.** It is an un-named block inside a 6,400-line file, which is why nothing can
test it, tag it, or instrument it — *nameless inline code has no symbol*.

**Closing this unblocks P5**, the config UX Ananth asked for on day one: *"together they
are config driven and we should create a UX to manage them."*

---

## 2. CURRENT STATE — measured

### 2.1 There are exactly two writers to the extension ledger [READ]

`mobius-chat/app/pipeline/react_loop.py`:

| line | writer | gate on it |
|---|---|---|
| `:5420` | `_pp_extension_rounds_used += 1` · `max_it += 1` | the **completion critic** — answer did not cover every sub-part |
| `:5526` | `_pp_extension_rounds_used += 1` · `max_it += 1` | the **governor's `extend` directive** — groundedness floor |

Declared at `:4563`. Read at `:4727` and `:5516` to compute `extension_rounds_available`.

**They share one ledger, deliberately** — the comment at `:5355-5367` says so explicitly,
and gives the reason: *"two uncoordinated extension pools could compound past the mode's
intended round ceiling."* **That reasoning is sound and the shared ledger is not the
defect.**

### 2.2 🔴 The defect: the two writers disagree on time, and neither knows it [READ]

| writer | deadline source | value |
|---|---|---|
| governor (`:5526`) | `governor._turn_deadline_seconds()` | `MOBIUS_TURN_DEADLINE_S`, default **90**, clamped 10–900 |
| completion critic (`:5420`) | **its own inline read** | `os.environ.get("MOBIUS_TURN_DEADLINE_S", "120")` |

**Same env var, different defaults — 90 vs 120 — and the critic re-reads it inline
rather than asking the governor.** With the var unset, the two writers hold different
beliefs about when the turn must end, and the critic's is 30 seconds more generous.

The critic also applies its own margin: `_cc_elapsed_s + 25 < _cc_deadline_s`, where the
governor uses `FINALIZE_MARGIN_S = 5.0` [READ `governor.py:54`].

### 2.2a 🔴 CORRECTED BY CHAT MASTER — the var IS set, so the asymmetry is LATENT, and the LIVE problem is the margins

**My §2.2 premise was wrong and I verified their correction myself.** Deployed
`mobius-chat` carries **`MOBIUS_TURN_DEADLINE_S=300`** [LIVE — read from the running
service's env; `mobius-chat` is the only chat service in the region]. So **all paths read
300, no default fires, and the 90-vs-120 asymmetry is latent, not live.**

**Q2 is answered: DRIFT, not a trade-off — with provenance** [REPORTED, Chat Master, and
the artifacts check out]. Spec `18add7f` (#107) line 53 offered
`os.environ.get("MOBIUS_TURN_DEADLINE_S", "120")` as **illustrative pseudocode**; commit
`d671d7b` copied it **verbatim 26 minutes later**. At that commit's parent the governor
already read 90.

**And there is a THIRD definition I did not have:** `app/worker/run.py:25`,
`_DEFAULT_TURN_DEADLINE_S = 90` — **the infra timeout that actually kills the turn**
[READ]. The governor's comment at `:43-45` says it duplicates worker/run.py's clamp
semantics **deliberately**, to avoid a pipeline→worker-entrypoint import [READ]. So **two
named constants with explanatory comments agree at 90; one unnamed inline literal says
120.** §5's unification is uncontroversial. That is a bug, not a product call.

**A FOURTH number** [READ]: `prompts.py:42-46` — *"REACT_MAX_ROUNDS_AGENTIC = 10 … Paired
with `MOBIUS_TURN_DEADLINE_S=240` in deploy/dev.env (was 180)"*. **The repository believes
this value is 90, 120, 240 or 300 depending where you read, and production is 300.**

### 2.2b 🔴 WHAT IS ACTUALLY LIVE: a 20-second margin gap on every agentic turn

I filed this as a footnote and Chat Master correctly promoted it to the finding. Both
margins sit against the **same 300s ceiling**:

| policy | margin | stops at |
|---|---|---|
| completion critic | `_cc_elapsed_s + 25 < _cc_deadline_s` | **275s** |
| governor | `FINALIZE_MARGIN_S = 5.0` | **295s** |

**The critic stops granting extensions 20 seconds before the governor hard-stops, on
every agentic turn, and setting the env var does not change that.** So the question §5
puts to Ananth **survives — it is the margins, not the defaults.**

**So "two extension policies, one ledger, and they disagree on time" is line-anchored —
but the disagreement that is LIVE is the reserve, not the deadline.**

### 2.3 The governor's own state [MEASURED, `gen_readiness.py`]

**🔴 "3 of 3 swallow" is a FALSE POSITIVE — my detector's fifth error, and Chat Master
adjudicated it correctly.** Verified by reading all three [READ]:

| line | handler | verdict |
|---|---|---|
| `:70` | `except ValueError: return _DEFAULT_TURN_DEADLINE_S` | **typed fallback for a malformed env var.** Not a swallow. My `_SWALLOW` regex matches any line starting with `return`, and `_hands_up` needs the caught name in the return — a bare `except ValueError:` has no name, so it fell through to swallow. |
| `:160` | `except Exception: pass` around `record_ambient` | **correct.** `_evaluate()` has already produced the directive; telemetry failing must not lose it. |
| `:174` | `except Exception: pass` around the log line | **correct**, same reason. |

**Their diagnosis of my detector is the durable part: *"your detector counted syntax; the
question is what the handler guards."*** A static check can **flag**; it cannot
**adjudicate**. Recording that as the detector's stated limit rather than trying to
out-clever it.

**But they found a real defect in their own code that the detector missed** [READ,
`:155`]: `from app.telemetry import spans as _sp` sits **inside** the `try`. **A swallowed
import is the shape that hid a 29-day capability outage in this repo** — the module stops
existing, the handler passes, and health stays green. **Row 5's AST test should assert
that no import sits inside a swallowing try**, which is mechanically decidable, unlike my
heuristic.

- **432 lines**, 3 exception handlers, **0 genuine swallows, 1 real import-in-try defect**
- **1 telemetry site, 1 log site** — this is the node whose *"zero logger calls"* opened
  `docs/chat-refactor-program.md`; the single site was added in the 2026-09-10 telemetry
  pass
- coverage **PERIPHERAL** — a test calls it, no guarantee is proven
- 6 open findings

### 2.4 What the governor actually decides [READ]

`evaluate(contract, state) -> (Directive, str)` at `:137`, five directives: **finalize ·
complete · extend · consolidate · search**. It returns a reason string alongside — so the
*reason already exists in code* and, before the telemetry pass, went nowhere.

---

## 3. FUTURE STATE — what "one decision point" should mean

**A single module that owns the extension decision, with one deadline, one ledger, one
writer, and a recorded reason.**

```
CURRENT                                  FUTURE
react_loop.py                            react_loop.py
 ├─ :5420 critic block                    └─ one call:
 │    reads env inline (120)                   extension.decide(state) -> Decision
 │    own margin (+25)                              │
 │    _pp_extension_rounds_used += 1                ▼
 │    max_it += 1                          app/pipeline/react/extension.py  (NEW)
 └─ :5526 governor block                    · one deadline, from governor
      governor deadline (90)                 · one ledger, one writer
      FINALIZE_MARGIN_S (5.0)                · both reasons (groundedness, coverage)
      _pp_extension_rounds_used += 1         · returns Decision(grant, reason, inputs)
      max_it += 1                            · records grant AND refuse
```

**Four properties the future state must have, each with the reason it is required:**

1. **Exactly one writer to `_pp_extension_rounds_used`.** P3's acceptance criterion,
   ratified by Tech Review. Not "the two constants agree" — *one writer*.
2. **One deadline, resolved once, from the governor.** The critic must not re-read the
   env var. A caller that re-reads config is a second policy wearing the first one's name.
3. **A file, so it can be tested and tagged.** 0 lines is why this node has no coverage
   and no telemetry. A named module is the precondition for both.
4. **The refusal is recorded, not just the grant.** Chat Master's own lesson from the
   telemetry pass: a span on the happy path only re-creates `make_tool_failed` — a
   refusal that never reports is indistinguishable from a gate that never runs. **The
   interesting rows are the turns that wanted an extension and did not get one.**

---

## 4. WHAT NEEDS CHANGING — proposals, to be argued with

| # | change | why | owner | risk |
|---|---|---|---|---|
| 1 | extract both blocks into `app/pipeline/react/extension.py` | gives the node a symbol; precondition for 3–6 | chat | **behaviour-neutral if pure extraction** — verify by I4/I5 |
| 2 | one deadline, resolved from `governor._turn_deadline_seconds()` | removes the 90-vs-120 split | chat | **changes behaviour** when the var is unset — see §5 |
| 3 | one writer to the ledger | P3's gate | chat | low, follows from 1 |
| 4 | `record_decision()` on **grant and refuse**, with the inputs | assertability: a decision is assertable iff its inputs are persisted with the outcome | chat | none |
| 5 | AST handler test over `governor.py` — every handler re-raises, logs, or hands up | 3 of 3 currently swallow; chat's own test from the `state_load` pass | chat | none |
| 6 | contract tag, mutation-demonstrated | testability PERIPHERAL → GUARDED needs Eval's audit | chat + Eval | none |
| 7 | `FINALIZE_MARGIN_S` vs the critic's `+25` — one margin, or two named ones | **the only LIVE disagreement: 275s vs 295s on every agentic turn** | **needs Ananth's ruling** | see §5 |
| 8 | move `:155`'s import out of the `try` | a swallowed import is the 29-day-outage shape | chat | none |
| 9 | Q4's tag: *"an extension is never granted when the ledger is exhausted"* — **mutation-checked by Chat Master before endorsing**: delete `:5373`'s `> 0` and a fourth extension becomes grantable in agentic | testability PERIPHERAL → GUARDED | chat + Eval | none |
| 10 | record **which guard refused** — ledger · deadline reserve · mode | Chat Master's addition: three different product problems, and one `refused` count cannot separate them. **"refused on deadline reserve" is the row that would have surfaced the 275/295 gap without anyone reading the code.** | chat | none |

---

## 5. 🔴 THE DECISION THAT IS NOT OURS

**Unifying the deadline changes behaviour, and someone has to choose which value survives.**

With `MOBIUS_TURN_DEADLINE_S` unset today: the groundedness path finalises against **90s**
and the coverage path extends until **120s**. Picking one means **either** the coverage
critic stops extending 30s earlier (fewer extensions, faster turns, possibly less complete
answers) **or** the governor finalises 30s later (slower turns, more complete answers).

**That is a product trade — answer completeness against turn latency — and it is Ananth's,
not ours.** §4 row 2 must not ship until it is made.

Same for row 7: `FINALIZE_MARGIN_S = 5.0` vs the critic's `+25` is a **26-second**
difference in how much headroom each policy reserves. Whether that asymmetry was
deliberate is `[UNVERIFIED]`.

**And note what §2.2 means for P3's gate metric:** merging the writers does not by itself
resolve the disagreement — **it forces it into the open**, which is the actual value. Two
constants in two places can differ forever unnoticed; one call site cannot.

---

## 6. FOR CHAT MASTER — where you know things I do not `[CHAT]`

1. ~~**Is row 1 a pure extraction?**~~ **ANSWERED: NO, and this is the real work.**
   Both blocks end in `continue` driving the enclosing loop, and both **rebind** `max_it`
   and `_pp_extension_rounds_used`, which are `run_react` locals. An extracted function
   can do neither. **The shape that works: the gate returns a decision plus the
   observation, and the CALLER increments and continues.** `tool_results.append` can stay
   inside. **Still a real extraction and it still forces one call site — it is an
   interface, not a move.** [Chat Master; this is the answer I most needed and could not
   have given.]
2. **Was the 90-vs-120 split deliberate?** A comment somewhere, a ticket, or is it drift?
   That changes §5 from a trade-off to a bug.
3. **Which of the governor's 3 swallowing handlers are load-bearing?** Your `state_load`
   experience says at least one may be handing an error up rather than dropping it — my
   detector got that wrong once already.
4. **What is the right contract to tag?** My candidate: *"an extension is never granted
   when the ledger is exhausted"* — mechanical, and its regression would be silent. Yours
   may be better.
5. ~~**Other call sites?**~~ **ANSWERED: no third path, and established by AST rather
   than grep.** Exactly **6 write sites** to either name in all of `app/`: 2
   initialisations (`:4468`, `:4563`) and the 2 writers. **My grep held — and is now
   proven by a method that can actually establish absence**, which a grep cannot
   (*symbol search cannot prove absence*).

---

## 7. Definition of done — when Ananth signs off

- exactly **one writer**, verifiable by grep
- **one deadline**, one margin, both named
- the node has a **file**, a test, and a mutation-demonstrated contract tag
- `record_decision()` on **grant and refuse**, with distinct production values —
  and if refusals never appear, **say so** rather than reporting five possible directives
- I4/I5 **predicted before the cut and compared after** — P3's phase rule; this is the one
  phase where those invariants move by design
- suite clean against `docs/chat-test-baseline.json`
- deployed and **digest-verified**; the rubric re-derives the badge, nobody sets it

---

## 8. Not in scope

- **P5's config UX.** This unblocks it; it is not it.
- **the critic node itself** (`critic.py`, 791 lines, 13 log sites, **no structured
  telemetry**) — adjacent and separately amber. The *completion critic's extension
  decision* is in scope; the critic's own quality is not.
- **`react_loop.py`'s size.** 6,400 lines is P4.

---

# 8. `[CHAT]` ANSWERS TO §6 — Payor Policy Agent, 2026-09-10

**No code written.** Ananth's sign-off gate is respected; everything below is
evidence, and where I contradict §2 I say so with the command that shows it.

## Q2 first, because it is the one that changes the pass — **it is DRIFT**

Provenance, in order:

| when | what | value |
|---|---|---|
| Aug 16 **22:16** | spec `18add7f` (#107), line 53 — *illustrative pseudocode* | `os.environ.get("MOBIUS_TURN_DEADLINE_S", "120")` |
| Aug 16 **22:42** | implementation `d671d7b`, 26 minutes later | copied **verbatim**, including the `120` |
| already true at `d671d7b^` | `governor.py:_DEFAULT_TURN_DEADLINE_S` | **90** |
| already true | `app/worker/run.py:25` — the infra timeout that actually kills the turn | **90** |

**There is a third definition, and it is the authoritative one.** The governor's own
comment (`:43-45`) says it duplicates `app/worker/run.py`'s semantics deliberately,
"rather than imported to avoid a pipeline→worker-entrypoint import." So **two named
constants agree at 90, each with a comment explaining itself — and one inline literal
says 120, with no name and no comment.** The 120 entered as pseudocode in a spec and
was never reconciled against a governor default that already existed that same evening.

Drift. §5 is not a product trade-off. **The unification is uncontroversial.**

## 🔴 But §2's premise is wrong, and it changes the severity

> *"Unset — which is production"*

**It is set.** Deployed `mobius-chat` (only chat service in `us-central1`):

```
MOBIUS_TURN_DEADLINE_S = 300
```

All three code paths read **300**. **None of the defaults fire in the deployed
service**, so the 26-second asymmetry is **latent, not live** — real, worth fixing,
but it is not currently costing a turn.

**What IS live is the margin, and §2 has it as a footnote:** governor
`FINALIZE_MARGIN_S = 5.0` against the critic's `+25`, both against the same 300s
ceiling. The critic stops granting at **275s elapsed**; the governor hard-stops at
**295s**. That 20-second gap fires on **every agentic turn**, today, at the deployed
value — and unlike the defaults it does not disappear when the env var is set.

**So the trade-off question you wanted to put to Ananth still exists — it is just
the margins, not the defaults.** The defaults are a bug; the margins are his call.

**And there is a fourth number.** `app/pipeline/react/prompts.py:44` carries the
comment *"Paired with MOBIUS_TURN_DEADLINE_S=240"*. Production is 300. So the repo
currently believes this value is 90, 120, 240 **and** 300 depending on where you
read. Your closing argument — *"two constants in two places can differ forever
unnoticed; one call site cannot"* — is stronger than you pitched it. It is four.

## Q5 — no third path. Confirmed by AST, not grep

A name search cannot establish absence; this can. Every **write** to either name
anywhere in `app/`:

```
react_loop.py:4468  max_it                      <Assign>      init
react_loop.py:4563  _pp_extension_rounds_used   <Assign>      init
react_loop.py:5420  _pp_extension_rounds_used   <AugAssign +> critic
react_loop.py:5421  max_it                      <AugAssign +> critic
react_loop.py:5526  _pp_extension_rounds_used   <AugAssign +> governor
react_loop.py:5527  max_it                      <AugAssign +> governor
TOTAL write sites: 6
```

Two initialisations, two writers, nothing else. **Your grep was right**, and §3's
picture holds.

## Q1 — **it is NOT a pure extraction**, and this is the real work

Two things block a lift-and-shift, both mechanical:

1. **Both blocks end in `continue`**, driving the enclosing `for` loop. An extracted
   function cannot `continue` its caller's loop.
2. **Both rebind `max_it` and `_pp_extension_rounds_used`**, which are `run_react`
   locals. An extracted function cannot rebind a caller's locals.

Full surface, from the same AST pass:

- critic block reads `_cc_verdict`, `ctx`, `tool_results`, `_pp_time_mod`,
  `_pp_turn_start`, `os`, `float`
- governor block reads `_pp_directive`, `_pp_critique`, `_pp_format_critique_obs`,
  `tool_results`

**The shape that works:** the extracted gate returns a decision — `granted: bool`
plus the observation to append — and **the caller** does the increment and the
`continue`. `tool_results.append` can stay inside (in-place mutation is fine). That
is still a real extraction and still forces the deadline into one call site, which
is the point of row 1. It is just not a move; it is an interface.

## Q3 — **"3 of 3 swallowing" is a false positive**, and two of them are mine

Classified by AST:

- **`:70` — `except ValueError: return _DEFAULT_TURN_DEADLINE_S`.** Not a swallow. A
  documented fallback for a malformed env var, with a typed exception.
- **`:160` and `:174` — bare `pass`.** These wrap the `record_ambient` call and the
  `logger.info` line **inside `evaluate()` — the telemetry wrapper I added this
  morning.** Swallowing is correct there: `_evaluate()` has already computed the
  directive before either runs, so a telemetry failure cannot change a decision. That
  is the property we wanted.

So: **none of the three is load-bearing, and none should be re-raised.** Your
detector counted syntax; the question is what the handler guards. Same shape as the
`state_load` false positive — and I am the one who wrote two of these, so this is not
a point against your detector so much as against reading `except: pass` as one thing.

**One real defect in my own code, though.** Line 155's
`from app.telemetry import spans as _sp` sits **inside** the `try`. A swallowed
import is precisely what hid a 29-day capability outage in this repo — the module
simply stops existing and health stays green. The import should sit outside, or be
caught once and loudly. **Row 5's AST handler test should assert that, not just that
handlers re-raise.**

## Q4 — endorse your candidate, and it is assertable **today**

*"An extension is never granted when the ledger is exhausted."*

I checked whether it currently holds on **both** paths, because the critic block
itself never reads the ledger — and it does: the critic is guarded by an outer
condition at **`:5373`**, `(_pp_contract.max_extension_rounds -
_pp_extension_rounds_used) > 0`, alongside `mode_label == "agentic"` and
`rn < max_it`. The governor gets it via `extension_rounds_available` at `:5516`.

It passes the mutation rule: delete the `> 0` clause at `:5373` and a fourth
extension becomes grantable in `agentic` (`max_extension_rounds = 3`). **Tag it.**

## On your two carried points

**"Record the refusal, not the grant" — agreed, and it is the stronger half.** The
turns that wanted an extension and did not get one are the only rows that can tell
you whether the deadline is set correctly. A grant-only span re-creates
`make_tool_failed` exactly.

**One addition:** record *which* guard refused — ledger exhausted, deadline reserve,
or mode. Those are three different product problems and a single `refused` count
cannot separate them. Given the 275s/295s split above, "refused on deadline reserve"
is the row that would have shown the margin asymmetry without anyone reading the code.
