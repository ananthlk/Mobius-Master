# The emit contract — every module shows its thinking

Ananth, 2026-09-11: *"make sure each of the agents has good persistence,
telemetry and emits so that I can follow the logic. I really want their thinking,
using the existing emit/sharing interface. The worst thing is when there is
silence — emits are a way to know the system is working, and working hard."*

---

## 1 · The channel is not silent. It is uninformative. `[MEASURED]`

```
80.6 events per turn                            ← the channel is saturated
30,435 'thinking' events / 7d, 8,094 distinct   ← real variety exists

most frequent lines:
  940  "◌ Thinking…"                             ← a spinner
  855  "Using rag…"                              ← status, not reason
  854  "Composing answer…"                       ← spinner
  783  "Found 15 relevant passages."             ← informative
  773  "Evidence review: no chunks marked relevant…"  ← informative
```

**The problem is not volume and it is not silence.** It is that the loudest
lines carry no decision. *"Using rag…"* says what happened; it does not say
**why rag, what else was considered, what was refused, and at what cost.**

`[DESIGN]` **So the fix is not a new channel and not more events.** It is:
**emit the decision, not the status.**

---

## 2 · We do not need to design this — the directive IS the thinking

The module contract already carries everything a reader needs:

```python
Directive = { decision, because, gap_targeted, posture,
              budget: {latency_ms, cost_c, token_budget},
              promise_version, inputs_measured, inputs_estimated }
```

**`because` was specified to make a decision auditable after the fact. Emitting
it makes the decision legible during the fact.** Same field, two readers.

### Before and after, same turn

```
today    Using rag…

v2       round 3 · CLOSE(G3) — "no FL Medicaid timely-filing figure", open 2 rounds
         offered: rag, appeals_lookup_rules  (3 of 5 refused)
           · appeals_assemble_letter  UNAFFORDABLE  90s ceiling vs 31s envelope
           · payor_fact_get           IRRELEVANT
           · appeals_get_playbook     EXHAUSTED     tried round 2, returned nothing
         budget 10–20s · 3–6¢ · spent so far 12.4s / 2.1¢
```

**Every field in that block already exists as a decision the governor or a module
made.** Nothing is computed for display.

---

## 3 · Four surfaces, and the stream is the one that was missing

| surface | reader | carries | authority |
|---|---|---|---|
| **the stream** `chat_progress_events` | **the user, live** | the decision and its reason, as it happens | **none — it is a view** |
| **the row** `turn_attestations` · `turn_rounds` · `thread_gaps` | the system, and us | promised vs delivered, declared vs actual | **source of truth** |
| **the line** structured log | whoever debugs one turn | the same fields, flat, by `correlation_id` | debug only |
| **the signal** counter / histogram | alerting | rates and distributions | derived |

**Use the existing `event_type` values.** `thinking` · `tool_progress` ·
`draft_ready`. **Do not invent a new surface** — the instruction that produced
the envelope decision applies here: *"if you write to the emit envelope table it
should pick it up, don''t invent something new."*

---

## 4 · Silence is a failure mode, and it is now specified as one

> **A module that takes longer than 2s and says nothing is indistinguishable
> from a hung one.**

**Every module must emit on entry and on exit**, not only on success:

| moment | emit | why |
|---|---|---|
| **entry** | *"tool selection: 5 candidates, 31s envelope"* | proves it started |
| **progress** if > 2s | *"rag: 8s elapsed of a 20s ceiling"* | **working hard is a thing the user should be able to see** |
| **exit — success** | the decision and its reason | the point |
| **exit — refusal** | the refusal **and which of the three kinds** | a refusal is a finding, not an error |
| **exit — error** | the failure, plainly | `[DESIGN]` **an error that emits nothing is the worst case: it reads as silence, and silence reads as hung** |

---

## 5 · What each module emits

| module | on entry | on exit |
|---|---|---|
| **Governor** | posture chosen · `because` · `gap_targeted` · the declared range | delivered vs declared · `in_band` |
| **Tool exposure** | candidates considered · the envelope | offered set **and every rejection with its kind** — `irrelevant` / `unaffordable` (+`needed_budget_ms`) / `exhausted`. **47 rejections on a typical round; a table of winners cannot answer "why was X not offered"** |
| **Prompt** | profile · token budget · what the manifest left | composed size vs `estimate()` |
| **Model** | the envelope sent to the bandit | model chosen · candidates trimmed by the latency filter |
| **React** | the directive it received | `closed:[…]` · `new:[…]` **by reference** |
| **Enricher** | why it ran at all (`rounds>1 OR tools>1`) | expansion vs the draft |

---

## 6 · Persistence — the stream is not a record

`[DESIGN]` **`chat_progress_events` is a view, never a source of truth.** It is
high-volume (80.6/turn), ephemeral in practice, and **nothing should compute a
conformance number from it** — the same rule already written for logs.

**Every decision worth reading later has a durable home:**

| decision | durable in |
|---|---|
| the promise, and whether it was kept | `turn_attestations` |
| per-round declared vs delivered, per-posture | `turn_rounds` — **no sampling column** |
| gaps, their attempts, their exits | `thread_gaps` |
| module estimates vs actuals | `turn_rounds` |

**If a decision only ever appears in the stream, it did not happen as far as any
report is concerned.** The stream is how you watch; the rows are how you know.

---

## 7 · The rule this all reduces to

> **Emit what you decided and why you decided it — not what you are doing.**

*"Composing answer…"* is a spinner. *"COMMUNICATE: direct from react, 1 round /
1 tool, enricher skipped — saves ~5.2s of a 13s promise"* is the same event
carrying the reason. **Both cost one emit. Only one of them lets anyone follow
the logic.**
