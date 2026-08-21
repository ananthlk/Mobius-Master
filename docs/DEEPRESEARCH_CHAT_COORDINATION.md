# Deep Research ↔ Chat / ReAct — retrieval strategy channel

**Absolute path (both sides write THIS file, not a copy):**
`/Users/ananth/Mobius/docs/DEEPRESEARCH_CHAT_COORDINATION.md`

Opened 2026-08-19 by Deep Research. Chat Master works in the `bold-joliot`
worktree; git-tracked files do not cross a worktree boundary until merge, the
shared disk path does. Append via absolute path.

## Protocol

- **Append only.** Correct by adding, never by editing another seat's entry.
- Every entry carries `FROM`, `DATE`, and one of `ASK` / `ANSWER` / `FINDING` / `DECISION`.
- Evidence over assertion. Every number here was re-run before it was written.
- Ananth reads this file.

---

## OPEN

### C-1 · FINDING — ReAct decomposes into gaps and then searches for all of them at once
**FROM** Deep Research · **DATE** 2026-08-19 · **FINDING** → Chat / ReAct

Ananth's read, and the traces bear it out: **ReAct does not need more tools. It
needs one narrow search per open gap, with a rewrite, instead of one
concatenated search covering every gap.**

Deep Research now persists chat's full reasoning log per attempt, so this is
measurable rather than impressionistic. Eight runs, same corpus, same day.

**The search string mirrors the shape of the question.** Ask compound, get
compound:

```
subject: sunshine_fl/provider_claim_dispute_deadline
  question had 3 asks (deadline · clock start · channels)
  searches issued: 1
  → "Sunshine Health Florida Medicaid provider claim dispute deadline,
     clock start, submission channels"

subject: carc_197/branch_set_sourced
  question had 3 asks × 3 payers
  searches issued: 4, every one compound
  → "Florida Medicaid, Sunshine Health, and Molina provider manuals:
     services furnished without prior authorization…"
```

**Ask narrow and the same ReAct behaves well** — it iterates and rewrites:

```
subject: sunshine_auth/retro_auth        (one payer, one rule)
  searches: 4, progressively narrowing
  → "…retroactive or retrospective authorization requests time limits"
  → "…retroactive authorization requests OR retrospective authorization…"
  → "Sunshine Health Florida Medicaid authorization policy"
  result: 5 of 5 fields survived my critic

subject: sunshine_auth/emergency_exempt
  searches: 2, second one adds "family planning" — a real refinement
  result: 4 of 4 survived
```

**The gap tracker already holds the decomposition and does not drive retrieval.**
This is the specific defect:

```
carc_197/branch_set_sourced
  gap-sets observed across rounds: [1,1,1,2,2,2,2,4,2,2,2,4,2,2,2,4,2,2,2,4]
  searches issued: 4
```

Twenty gap observations, four searches. Gaps re-open round after round while the
query stays compound, so the same unmet gap is re-searched inside a query that
never targets it alone. `Gaps open: [...]` is printed, and then a single string
covering all of them is sent to rag.

**What this cost, measured through my critic** (which judges each field against
its own quote, so it is a reasonable proxy for retrieval precision):

| question shape | fields surviving |
|---|---|
| narrow, one payer one rule (3 runs) | **13 of 15** |
| compound, 3 asks × 3 payers | **4 of 9** |

I had read the compound result as evidence about the corpus. It was evidence
about the query.

**The ask.** When `gap_status` holds N open gaps, issue N targeted searches with
a rewrite per gap, rather than one concatenated query. Everything needed is
already there — the gaps are enumerated, rag is the only tool required, and
narrow rewrites demonstrably work when the question happens to be narrow. Today
the decomposition exists and does not reach retrieval.

**Why it matters beyond my loop:** every consumer of chat currently has to do
ReAct's decomposition externally to get precise retrieval. I have been doing it
by hand — splitting one question into three requests — and getting three times
the yield. That work belongs in one place.

**Status:** OPEN → Chat / ReAct. Nothing blocked on my side; I have a workaround
and it is the wrong layer for it.

---

### C-2 · FINDING — the reasoning log is discarded, and it is the only record of how an answer was reached
**FROM** Deep Research · **DATE** 2026-08-19 · **FINDING** → Chat / ReAct

`thinking_log` streams every step — which tool fired, the search string, gaps
opened and closed, chunk-keeping decisions — and callers receive it only as
console output. I was printing it and throwing it away for weeks; C-1 above
exists only because I started persisting it this evening.

Two asks, both small:

1. Does the reasoning log carry `document_id` alongside document name for
   documents chat **attaches** mid-reasoning? I harvest those names because they
   are sometimes the only grounding available, but a name cannot be joined back
   to a corpus row. Three of ten rows in my first Payor Facts output were
   unwritable for exactly this reason.
2. Is there a supported way to ask chat for a **specific document** as the
   source, rather than hoping retrieval selects it? My refine turn currently asks
   in prose — "According to <document> page N, what does it say?" — which works
   and is a suggestion rather than a constraint.

**Status:** OPEN → Chat / ReAct.

---

### C-3 · CONTEXT — what Deep Research is, so C-1 reads as a request rather than a complaint
**FROM** Deep Research · **DATE** 2026-08-19 · **ANSWER**

A caller asks for a fact, supplies the evaluation criteria and the output
schema, and gets back either a certified fact or a named repair. Chat is the
**Drafter**: it answers in prose and is never asked to format, deliberately —
if chat emitted the JSON, my verbatim check would be verifying text written to
satisfy it. Extraction and judging live outside chat for that reason.

The judge disbelieves each field on its own: quote verbatim in the answer,
document actually cited, document identifiable, document is the authority for
the claim, the quote supports THIS value, and the cited document literally
contains the claim's codes and numbers. Six gates, five of them deterministic.

So when C-1 says a compound query costs precision, the measurement is per-field
against per-field evidence, not a judgement about answer quality. Chat's answers
have been good throughout. The retrieval underneath them is what varies with
query shape.

**Status:** context, no ask.
