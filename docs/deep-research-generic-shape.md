# The generic shape — what is actually reusable

Working note, 2026-08-21. Written from four domains running through one machine:
claims adjudication, behavioral health service lines, member incentives, and
provider credentialing. Everything here is provisional and several parts are
labelled as guesses.

The question behind it: is there a framework here, or four tools that resemble
each other? The test is whether one extractor shape, one judge, one arbiter and
one executor handle all four without per-domain special-casing.

---

## The three loops

Named as configuration in `deep_research/modes.py`, not as round numbers. Mode
is chosen from what the last round *learned*, not from how many turns a question
has had — those are unrelated facts and conflating them was a real bug: a
question whose claims all check out but sit in a single document was being
re-asked *more narrowly*, which could only ever find the same document again.

| loop | retriever bargain | accepts | buys |
|---|---|---|---|
| **BROAD** | any authority, any source, wide question | nothing | direction — documents, vocabulary, the paths the search took |
| **CITATION** | narrow, one claim, citable forced at a named document | yes | provenance — a lead becomes a fact or a named defect |
| **CONTRADICTION** | where else does this live, and does it agree | nothing | the second opinion single-source validation structurally cannot see |

The interesting measurement is what fraction each loop closes, per domain. That
is why the mode is recorded on every round rather than inferred from its index.

---

## The five pieces

### 1. ReAct — skills + config + framework

**Config is the mode.** `citable_required` is the only knob the loop actually
turns today. Everything else it inherits.

**Skills is the open question.** Right now the loop reaches ReAct through one
door — a chat turn — and ReAct picks its own tools. The loop cannot say "read
this document" or "search for a competing source"; it can only word the question
so that ReAct probably will. That is the largest gap in the machine, and it is
why CONTRADICTION mode is currently implemented as a local corpus read rather
than a retrieval turn: there is no way to *ask* for a contradicting source.

### 2. Extractor — one shape across all four domains

```
payer            the single payer this rule belongs to
rule             what the source says, one sentence
scope            the population / service line / product / claim type it governs
condition        when it applies
value            the limit, amount, count or duration — only if stated
provider_action  what the provider or member must do
manual_section   the section or page, if named
```

`scope` was added *because of a failure*, and it is the most important field in
the set. The corpus holds three clean-claim adjudication regimes — 10 business
days for nursing facility, 20/40 calendar for non-nursing, 15/20 for medical
foster care — and the answer picked one and attributed it to the manual at
large. Nothing was wrong with any document. The question was under-specified,
and a rule recorded without its scope reads as the rule for everyone.

Whether one shape survives four domains is the experiment; the run is what
answers it, not this note.

### 3. Judge — token presence is not textual support

The judge asks one question per claim: *does the document this claim names
actually say it?*

It used to answer by checking whether the claim's codes and numbers appeared
anywhere in the document. That passed a sentence which exists only in
`MFC-Billing-Reimbursement-Guidelines` as a quote from the Sunshine Provider
Manual — because `15` and `20` appear in every payer manual ever written — and
the manual it was attributed to states a different rule.

The fix was not a tighter threshold. Token presence and textual support are
different questions and no threshold over the first answers the second. It is
an LLM read now: `present` · `contradicted` · `absent` · `undecidable`.

### 4. Arbiter — a verdict either settles or names a loop

The whole arbiter for this half of the machine is a table
(`modes.NEXT_MODE`). Worst verdict wins.

| verdict | next |
|---|---|
| `corroborated` | settled, and settled well |
| `contradicted` | **a human rules** |
| `scope_unstated` | **the question is wrong, not the corpus** |
| `single_source` | CONTRADICTION — look harder before believing it |
| `mis_attributed` | CITATION — value real, citation wrong, repoint |
| `claim_unsupported` | CITATION — subject covered, value absent |
| `not_comparable` | CITATION — nothing to compare, read the document |
| `not_found` | BROAD — the subject is not where we looked |

Two of the eight stop the machine. That ratio feels right and is not yet earned
by evidence.

### 5. Executor — inward and outward

Unchanged from the earlier design and still the weakest-tested piece.
Inward skills (`locate` · `acquire` · `reindex` · `gloss`) are retryable;
outward skills (`file` · `call` · `escalate`) consume something irreversible.
Only the inward ones have been exercised.

---

## What made this work, and it was not the loop

**Everything that judges is an LLM. Everything that retrieves is mechanical.**

That line was found the hard way. The contradiction check began as regex and
grew a rulebook — a stoplist of generic words, word-boundary matching, a
co-occurrence threshold — and each fix bought exactly one case:

- `claims` matched a credentialing paragraph — *"liability claims have the right
  to request reconsideration within 30 days"* — and the 30 days was reported as
  a rival deadline for clean-claim adjudication.
- `electronic` matched *"the form was filed electronically"* and *"notice
  provided by mail or electronic means"*.

Whether two sentences answer the same question is a reading judgment, and a
stoplist is a bad proxy for one. The retrieval requiring a passage to state a
*duration* was the same error one level up — it quietly made the whole machine a
deadline-checker, so a benefit limit or a credentialing requirement retrieved
nothing and the loop reported the corpus silent on subjects it covers
thoroughly.

**A manufactured contradiction is worse than a missed one.** It stops
certification on a rule nobody disputes and costs a human the time to discover
the machine was confused. Every threshold here errs toward under-claiming.

---

---

## What six sweeps of the same four questions actually showed

**Run-to-run variance is large enough to invalidate single-run comparison.**
Identical questions, identical code on two of the runs, confirmed-claim counts
of 21 / 21 / 5 / 17. `gemini-2.5-flash` went DEGRADED mid-sweep on one of them
("recent mean 25750ms > 3.0x ema 5700ms"). Any conclusion drawn from one run
comparing counts is noise — including several I drew during the session and had
to withdraw.

What *can* be read from a single run is anything structurally true or false
regardless of draw:

| check | before | after |
|---|---|---|
| off-schema field names | `Standard Prior Authorization Timeframe`, `Program` | NONE |
| scope carried onto claims | 0 of 5 | 17 of 17 |
| crashes | 2 of 6 runs | 0 |
| `scope_unstated` share of verdicts | 18 of 21 | 0 of 17 |
| verdict distribution | one verdict swallowing 86% | single_source 7 · corroborated 3 · mis_attributed 3 · not_found 2 · contradicted 1 · claim_unsupported 1 |

The last row is the one that matters. A verdict vocabulary where one term covers
86% of cases is not a vocabulary, it is a default with decoration.

---

## The limit the sweeps found: one question, one answer

Corroboration assumes a claim has *an* answer that another document either
matches or does not. That holds for scalars — a deadline, an amount, a
frequency. It breaks on **enumerations**, and credentialing is nothing but
enumerations:

```
claim      "Submit a curriculum vitae"
found      "Work history for the past five years"
verdict    claim_unsupported      ← WRONG. Both are required. It is a
                                    checklist, not a disagreement.
```

The test that fixes it is not lexical: *if both statements were true at once,
would that be a problem?* Two checklist items can both hold; two deadlines for
the same claim type cannot. Only the second is a contradiction. That question is
now in the reading prompt.

The same run surfaced a document contradicting *itself* — rendered, before the
fix, as "Sunshine Provider Manual.pdf state X, while Sunshine Provider Manual.pdf
state Y", which reads as a bug rather than as the finding it is. Self-conflict is
worth surfacing and has to be said in those words, because a reader who decides
the machine is confused stops reading the rest of the output.

---

## Known gaps

- **CONTRADICTION mode is not a retrieval turn.** It reads the corpus locally.
  It should be able to ask the retriever for a competing source, and cannot,
  because the loop has no way to hand ReAct a tool instruction.
- **Definitions are compared by word overlap** like everything else. Whether
  that is adequate for a definitional claim is untested.
- **Scope is extracted, not bound.** Nothing checks that a claim's `scope`
  matches the caller's intended scope — that check is where `scope_unstated`
  should eventually be caught *before* the corroboration pass, not after.
- **Outward executor skills are unexercised.** `call the payor` and
  `look for claims-based evidence` are named endpoints with nothing behind them.
- **Caller-supplied identity fields** — FIXED. `payer`, `manual_section`,
  `state`, `product` are dropped before validation and out of the caller schema.
  A `payer` field of "Sunshine Health" had been going through corroboration and
  coming back `scope_unstated`, meaning the machine had gone looking for other
  populations the payer's own name might govern.
- **Enumerated claims** — the "if both were true, would that be a problem" test
  is in the prompt but untested across a repeat run, and it is the kind of
  instruction that could suppress real conflicts. Needs repeats, not one sweep.
- **Repeat runs are not automated.** Every count in this note came from reading
  runs by hand and lining them up afterwards. Given the variance measured above,
  that is backwards: the loop should run N times and report a distribution.
