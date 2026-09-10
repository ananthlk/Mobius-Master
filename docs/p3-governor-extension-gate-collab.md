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

**So "two extension policies, one ledger, and they disagree on time" is now line-anchored
rather than asserted.**

### 2.3 The governor's own state [MEASURED, `gen_readiness.py`]

- **432 lines**, 3 exception handlers, **all 3 swallow**
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
| 7 | `FINALIZE_MARGIN_S` vs the critic's `+25` — one margin, or two named ones | two unexplained constants | **needs a ruling** | see §5 |

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

1. **Is row 1 a pure extraction?** Both blocks touch `tool_results`, `ctx.*` and locals
   from a 900-line loop body. I read them as extractable; you have moved code in that file
   and I have not.
2. **Was the 90-vs-120 split deliberate?** A comment somewhere, a ticket, or is it drift?
   That changes §5 from a trade-off to a bug.
3. **Which of the governor's 3 swallowing handlers are load-bearing?** Your `state_load`
   experience says at least one may be handing an error up rather than dropping it — my
   detector got that wrong once already.
4. **What is the right contract to tag?** My candidate: *"an extension is never granted
   when the ledger is exhausted"* — mechanical, and its regression would be silent. Yours
   may be better.
5. **Does `completion_extension_gate` have other call sites** I have not found? I grepped
   `max_it +=` and `_pp_extension_rounds_used`; a different increment path would change
   the whole picture.

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
