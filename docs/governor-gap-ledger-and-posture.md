# The gap ledger and posture — owned by the governor

Ananth, 2026-09-11: *"this is yours to own because this will set the tone for
the prompt builder. You will predict based on N rounds, gaps closed and open,
increasing vs decreasing, and the same or new gaps, what the next posture is —
and prompts just builds that profile."*

This closes the seam that has been unowned all week, and that I kept arriving at
from every direction: phase detection, the spend decision, `gap_closed`, the
judgment lag, the communication threshold.

---

## 1. Identity is MINE to assign, which removes the hard part

The obvious design — ask react to give each gap a stable id — is the wrong one.
**A model cannot be relied on to remember an identifier across rounds**, and
every round is a fresh call.

**So the governor holds the ledger and injects it.** React never remembers;
**it is handed the list every round and answers by reference.**

```
round N:  governor → prompt:  OPEN GAPS
                                  G3  "no FL Medicaid timely-filing figure"
                                  G7  "unclear whether member is MMA or LTC"
          react   → governor:  closed: [G3]
                               new:    ["payer's appeal window not established"]
```

The governor assigns `G9` to the new one. **React does zero bookkeeping**, and
identity is exact rather than inferred, because I minted it.

**Why this matters beyond tidiness:** without identity, `gaps_open: 2` at round
3 and `gaps_open: 2` at round 4 are indistinguishable between *"the same two,
untouched"* and *"two closed, two new."* Those are **opposite situations** — one
says the lever is not working, the other says discovery is healthy — and today
they produce identical telemetry.

### What a gap carries

| field | why |
|---|---|
| `id` | governor-minted; makes *closed* verifiable rather than asserted |
| `text` | react's own words — never rewritten |
| `opened_round` | **age.** A gap open four rounds is evidence the lever fails, not that more of it is needed |
| `importance` | Ananth's term. Not every gap is worth a round |
| `attempted_by` | which levers have already been spent on it — **prevents buying the same round twice** |
| `closed_round` | null while open |
| `reopened_count` | evidence conflict, and currently invisible |

---

## 2. What the data already says — measured, 60 days, 3,364 round-transitions

**P(all gaps closed next round), by gaps open now:**

```
0 → 57.7%   |   1 → 24.6%   2 → 20.5%   3 → 21.7%   4 → 23.9%
```

**Flat at ~20–24% for every non-zero count.** One open gap predicts closure no
better than four. `[MEASURED]`

**Because the list GROWS as evidence arrives:** round 1 avg **0.46** open →
round 3 **1.32** → round 4 **1.34**. Gaps are *discovered*, not only closed —
so **"% of gaps closed" measures against a moving denominator** and is not a
percentage at all. That kills the natural heuristic, which is worth knowing
before building on it.

**The trend does carry signal, and only on one side:**

```
decreasing 41.5%  |  flat 41.0%  |  INCREASING 25.4%
```

Decreasing and flat are indistinguishable. **Only *increasing* is informative,
and what it says is: stop expecting closure.**

`[OPEN]` **Every one of these is a count of unnamed strings.** Two "gaps" may be
one gap rephrased. The 57.7% row means 42% of rounds after a zero-gap round have
gaps again — almost certainly discovery, **but I cannot prove it without
identity.** These numbers get re-derived once the ledger exists, and I expect
them to move.

---

## 3. Posture — what I emit, and what the prompt seat builds to

**Posture is the governor's output and the prompt's input.** The prompt seat
owns what each posture's prompt *says*; I own which posture is in force.

| posture | fires when | what the round is for |
|---|---|---|
| **FRAME** | round 1, or the question is not what we are answering | establish the target. **Cheapest failure to fix, most expensive to miss** |
| **DISCOVER** | gaps **increasing** | learn the shape. **Do not buy closure here** — 25.4% says it will not happen |
| **CLOSE** | gaps flat/decreasing, ≥1 gap worth spending on | attack a **named** gap, by id |
| **CONSOLIDATE** | no gap worth spending on, evidence not yet assembled | combine what we have |
| **DRAFT** | consolidation done | user-facing output. **The answer-card schema lives here and only here** |
| **NARROW** | budget nearly spent, gaps still open | **ship with the holes named.** Not a failure mode — the honest close |

**NARROW is the one a naive governor never picks**, and the data argues for it:
if gaps are increasing at round 6 with 25.4% odds of closure, more rounds are
speculation. **Naming the open gaps to the user is a better answer than a
confident one with a silent hole** — the same discipline as emitting recall as
an explicit null.

### The signal identity unlocks that nothing has today

| observation | reading | lever |
|---|---|---|
| **same** gap open 3+ rounds | the lever is not working | **change lever** — model, tool, or FRAME. **Not another round of the same** |
| **new** gaps arriving | healthy discovery | DISCOVER; do not buy closure |
| gap **closed then reopened** | evidence conflict | CONSOLIDATE, not more retrieval |
| gap closed, none new | converging | CLOSE or DRAFT |

**Row 1 is the one that pays for the ledger.** "Buy another round with the same
model and the same tool for a gap that has survived two of them" is the most
expensive mistake available, and today it is invisible — the counts look
identical to healthy progress.

---

## 3a. RULED by Ananth, 2026-09-11 — two decisions that reshape this

### `close` is a DIRECTIVE, not a posture

The job does not change when the governor aims a round at a named gap — it is
still explore. What changes is **what it is aimed at.** So:

| | |
|---|---|
| **postures** (⇒ prompt profiles) | `FRAME` · `EXPLORE` · `NARROW` · `VALIDATE` · `COMMUNICATE` |
| **directives on EXPLORE** | `DISCOVER` · `CLOSE(gap_id)` · `REFORMULATE(gap_id)` |

**This simplifies the prompt seat''s work rather than adding to it**, and it
follows their own four-axis test: discover, close and reformulate share an
output contract (a tool call), an evidence posture (seeking), and a failure mode
(a wasted round). **Only the aim differs — and an aim is a directive.**

`[OPEN]` **REFORMULATE may be a directive too, by the same argument.** Its
success test is arguably distinct — *"is the new query materially different"* is
checkable where the others are not — but its output contract is identical. **The
prompt seat''s call, not mine**, since it turns on whether one block can carry
both instructions without the differentiation being deferred into a condition —
which is exactly how `react_draft`/`explore`/`synthesize` became one prompt.

### The ledger is THREAD-scoped, not turn-scoped

**The consequences are larger than the change.**

**1. A follow-up turn can skip discovery.** It starts with the thread''s open
gaps and goes straight to `EXPLORE/CLOSE`. Today turn 2 rediscovers from
scratch.

**2. Gaps outlive the promise they were opened under.** Turn 1 may have been
`fast` (13s) and left gaps; turn 2 may be `thinking` (95s). **A gap must carry
`opened_turn` and the `promise_version` in force when it opened** — because *"we
could not close this in 13 seconds"* and *"we could not close this in 95
seconds"* are different facts about the same gap. Same discipline as the
attestation storing the promise inline rather than by reference.

**3. The re-ask override finally has a mechanism.** §9 actor 3
(observed-frustrated) was marked *"nothing detects this."* A user still on the
same thread with **named open gaps** is no longer an inference about mood — it
is a list. **The strongest evidence the promise was not kept, and the reason,
sitting in the same row.**

**4. 🔴 The promise is turn-scoped; the objective is now thread-scoped.** This is
the real complication. A turn can **keep its promise while the thread makes no
progress**, and a turn can **breach while closing a gap three turns old.**
Per-turn attestation cannot fully account for a thread-scoped objective — the
cost of closing a gap is spread across turns, and only the last one gets credit.
`[OPEN]` **Needs a thread-level view alongside the turn-level one**, or
conformance reporting will answer *"did we keep our promises"* while never
answering *"did we get the user their answer."*

**5. Staleness needs a rule.** A gap from a thread three days idle is not
obviously live. `[OPEN]` TTL, or relevance-check on reopen — not yet decided,
and **it must not default to "carry everything forever"** by omission.

**6. It needs storage, not just context.** A `thread_gaps` table keyed by
`thread_id`, with the same idempotency constraint every chat migration needs
(`run_migrations.py` re-applies every file on every boot). Gap text derives from
user questions, so it inherits the thread''s existing PHI posture — worth
confirming with the PHI seat rather than assuming, since it persists longer than
a turn.

## 4. What this asks of the prompt seat

Not "write prompts." **Build to posture.** The governor sends:

```
posture       ∈ {FRAME, DISCOVER, CLOSE, CONSOLIDATE, DRAFT, NARROW}
open_gaps     the ledger, by id and text
gap_targeted  the id this round is buying, when posture = CLOSE
token_budget  the remainder after manifest, history and evidence
```

And react answers by reference — `closed: [G3]`, `new: [...]` — instead of
re-emitting a list it had to reconstruct.

**This also settles the profile question from the other end.** Six postures
against four agreed profiles: FRAME and DISCOVER may both map to `explore`;
CONSOLIDATE to `synthesize`; DRAFT and NARROW to `draft` with different
instructions. **Whether a posture needs its own profile is the prompt seat''s
call, decided by their four-axis test** — output contract, evidence posture,
failure mode, success test. **Posture is mine; profile is theirs; the mapping is
a joint decision.**

---

## 5. Sequencing — and this must not go in the wrong order

1. **Ledger with identity** — governor-held, injected, answered by reference.
2. **Re-derive §2 on identified gaps.** Every number there is over unnamed
   strings and should be treated as provisional.
3. **Posture from the re-derived numbers**, not from these.
4. **Prompt profiles per posture**, once the set is stable.

**Do not build posture thresholds on §2.** Those numbers are the argument that
the ledger is worth building — **they are not the calibration.** Using them as
calibration would be the same error as reading a division as a discovery.
