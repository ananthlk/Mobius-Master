# `thread_gaps` — persisting the ledger across turns

Ananth, 2026-09-11: *"the single biggest thing we have across turns is the gap
list. I don't think we persist that. We should create a new table to persist it
and load it at state_load. It tells react everything we want to do."*

Governor seat owns this. `[MEASURED]` state confirmed against dev.

---

## 1. Confirmed: nothing persists gaps today

| where gaps exist today | scope | survives the turn? |
|---|---|---|
| `thinking_log` → `rounds[].enrichment.gaps_open` | per turn, JSONB | **readable, not usable** — no identity, no query |
| `react_loop.py:1139` | `if gaps_open: return False` | **content discarded**, boolean only |
| `chat_state.state_json` | 13 keys — `active`, `open_slots`, `master_objective`, `refined_query`… | **no gaps key** |
| a gaps table | — | **does not exist** |

So every turn rediscovers from zero, and the prompt tells the model *"a gap
tracker downstream reads these directly"* when **there is no gap tracker.**

---

## 2. Why a TABLE and not a key in `chat_state.state_json`

`chat_state` is already loaded at `state_load`, so a key there would be free to
read. **I am still recommending a separate table, for two reasons that outweigh
that:**

**1. The CAPABILITY build queue needs cross-thread aggregation.** *"Which gaps
exit CAPABILITY across many threads and users"* is the product signal in
`governor-exit-modes.md` — it names sources we do not have, in users'' own
words. **That query is impossible efficiently inside a per-thread JSONB blob**
and trivial against an indexed table.

**2. `chat_state` carries a known compare-and-set hazard.** `storage/threads.py:750`
documents it: *"A turn writes chat_state more than once — state_load persists
the delta, then the orchestrator persists refined_query at the end. Each write
advances state_version, so a version captured once at read time is stale by the
second write."* **Adding gaps to that blob inherits that contention**, and gaps
are written on a different cadence than the rest of the state.

`[DESIGN]` A third reason, weaker but real: a gap has **structure worth
constraining** — a status enum, foreign-key-shaped turn references, a closed_at.
JSONB accepts anything, including a gap with no id.

---

## 3. Shape — migration `067_thread_gaps.sql`

**Must be idempotent.** `app/db/run_migrations.py:179` globs `db/schema/*.sql`
and re-applies **every file on every boot**; there is no applied-ledger.

| column | why |
|---|---|
| `gap_id` TEXT PK | **governor-minted.** React never mints or remembers one |
| `thread_id` UUID | the scope, per Ananth''s ruling |
| `text` TEXT | **react''s own words, never rewritten.** Rewriting loses the user''s framing |
| `status` TEXT | `open` · `closed` · `abandoned` |
| `importance` TEXT | Ananth''s term — not every gap is worth a round |
| `opened_turn` TEXT · `opened_round` INT · `opened_at` TIMESTAMPTZ | age, and which turn is accountable |
| **`opened_promise_version`** TEXT | **"we could not close this in 13s" and "…in 95s" are different facts.** A gap outlives the promise it was opened under, so the promise travels with it — same rule that put the promised values inline on `turn_attestations` |
| `attempted_by` JSONB | levers already spent — **prevents buying the same round twice, and is what separates BUDGET from CAPABILITY at exit** |
| `closed_turn` · `closed_round` · `closed_at` | **credit goes to the closing turn** |
| `reopened_count` INT | evidence conflict; currently invisible |
| `exit_mode_at_close` TEXT | `complete` · `budget` · `capability` — **feeds the build queue** |
| `last_seen_turn` TEXT | staleness |

**Indexes:** `(thread_id, status)` for the load; `(status, exit_mode_at_close)`
for the build queue.

---

## 4. Read at `state_load`, write once at turn end

**Read:** one indexed lookup on `(thread_id, status='open')`, alongside the
existing state read. `state_load` is currently **412.7ms p50** — I took it there
from 1,572.9ms, so I am watchful about adding to it. A single-index read on a
small per-thread set should be low single-digit ms; **it must be measured after,
not assumed**, and it belongs beside the existing read rather than after it.

**Write: once, at turn end, in the same `finally` that closes the attestation.**
Not per round.

- keeps the round loop free of DB writes
- reuses the settling step already built and proven
- and it is **correct for ERROR turns**: `governor-exit-modes.md` §4 says an
  errored turn''s gap list is not authoritative, so writing at the `finally`
  means those updates land **marked provisional** rather than silently
  promoting a half-judged list into thread state. **That risk only exists
  because the ledger now outlives the turn.**

---

## 5. What it gives react — the loop the prompt already assumes

```
state_load  ──►  open gaps for this thread, by id
                      │
                      ▼
governor injects into the prompt:   G3  "no FL Medicaid timely-filing figure"
                                    G7  "unclear whether member is MMA or LTC"
                      │
                      ▼
react answers BY REFERENCE:  closed: [G3]   new: ["appeal window not established"]
                      │
                      ▼
governor mints G9, writes the ledger at turn end
```

**React does zero bookkeeping and never has to remember an id across rounds** —
it is handed the list every time. **Identity is exact because the governor minted
it**, not inferred by matching text.

**And this is the mechanism the prompt has been promising since August.**
`react/prompts.py:443` tells the model: *"a gap tracker downstream reads these
directly."* Today that is false. This makes it true.

---

## 6. Open, and deliberately not decided here

| item | why it is open |
|---|---|
| **staleness rule** | a gap in a thread idle three days may not be live. TTL, or relevance-check on reopen. **Must not default to "carry everything forever" by omission** |
| **PHI posture** | gap text derives from user questions and now persists beyond the turn. It inherits the thread''s scope, but **confirm with the PHI seat rather than assume** — the retention window changed |
| **thread-level conformance** | the promise is turn-scoped, the objective is now thread-scoped. A turn can keep its promise while the thread makes no progress. **Needs a thread view or reporting answers the wrong question** |
| **posture thresholds** | every number in `governor-gap-ledger-and-posture.md` §2 counts **unnamed strings**. Re-derive on identified gaps before calibrating anything |
