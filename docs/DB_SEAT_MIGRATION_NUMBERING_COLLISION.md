# For the Platform Architects DB seat: `mobius_rag` has two migration sequences

**Raised by** Deep Research / Payor Policy seat, 2026-09-08, at Ananth's
instruction. **Found by** Product Awareness during the product-v1.1.0 release
review, from a smaller observation (three byte-identical files) that turned out
to sit on top of this.

**Decision needed from the DB seat. I have not renumbered anything** — that is a
change to a shared database and it is not mine to make unilaterally.

---

## The finding

Two repositories write migrations for **one** database (`mobius_rag`), with
independent number sequences. Ten numbers are used by both, for entirely
different migrations:

| # | `mobius-skills/deep-research/schema/` | `mobius-payor/migrations/` |
|---|---|---|
| 053 | `repair_retry` | `sourcing_outstanding` |
| 054 | `resume_on_acquire` | `not_sourced_is_not_declined` |
| 055 | `halt` | `review_and_origin` |
| 056 | `owner_queue_and_polarity` | `review_queue_kind_detail` |
| 057 | `owner_vocabulary` | `sourcing_link_and_projection` |
| 058 | `request_authority` | `sourcing_run` |
| 059 | `llm_calls` | `citation_resolves` |
| 060 | `resolution` | `citation_searches_tables` |
| 061 | `closure_contract` | `resolve_documents_by_token` |
| 062 | `deadlines` | `run_can_be_requested` |

Additionally `045`, `046` and `047` exist in **both** repos as byte-identical
copies, with nothing keeping them in step.

And `mobius-payor` duplicates four numbers **within itself**:

```
033  ingest_failure_reason      +  service_line_registry
034  apr_drg_reference          +  ingest_transactions
047  line_lexicon_d             +  research_turns
050  attempt_in_flight_outcomes +  document_tables
```

## Why it matters — the ledger was false, not merely incomplete

`migrations_applied` held **only payor's side** of all ten collisions. None of
the ten deep-research migrations were recorded.

They had all run. Verified by checking whether their objects exist:

```
055_halt.sql       APPLIED   research.halt
057_owner_*.sql    APPLIED   research.owner_team, research.open_work
059_llm_calls.sql  APPLIED   research.llm_call, research.model_rate
060_resolution.sql APPLIED   research.resolution, research.ruling
062_deadlines.sql  APPLIED   research.deadline_policy, research.action_deadline
```

**So the ledger could not rebuild this database.** Replaying it produces payor's
`060_citation_searches_tables` and no `research.resolution` at all — and
`research.resolution` is the table the entire decision and closure machinery
runs on.

This is a different failure from a missing row. `067_judge_override.sql` was
applied out of band by me and registered late: that was one gap in an otherwise
true record. This made the record *wrong* — it named a different migration under
each of ten numbers.

## What I did, and deliberately did not do

**Did:** registered all ten retrospectively as
`deep-research/schema/<file>`, repo-qualified so the two sequences are
distinguishable at all, each carrying a note that it was applied out of band and
that its number collides. Ledger 56 → 66 rows. Also registered `067` (my own,
separately).

That makes the ledger **honest**. It does not make it **correct** — the
qualified names are a description of a problem, not a fix.

**Did not:** renumber, reorder, or move any file. Renumbering applied migrations
changes what a replay does on every environment that has already run them, and
choosing between the two sequences is a governance decision about a shared
schema.

## The decision I am asking for

1. **Does one repo own `mobius_rag` migrations, or do both?** Today `research.*`
   DDL has lived in `mobius-payor` since `046_discovery_seam.sql` — 13 payor
   migrations touch `research.*` — while `mobius-skills/deep-research` also
   ships `schema/` and applies it. Whichever answer, it should be written down.
2. **Is filename+number a key?** It currently is not, and nothing enforces it.
   A `CHECK`/unique constraint on the ledger, or a numbering scheme with a repo
   prefix, would make the next collision impossible rather than discoverable.
3. **What happens to the ten collisions and the four intra-payor duplicates?**
   Leave-and-document, renumber-forward-only, or renumber-with-a-replay-note.
4. **Should applying a migration outside the ledger be possible at all?** Both
   my `067` and all ten of these were applied directly. A runner that refuses to
   apply an unregistered file would have caught every one.

## Evidence

Reproduce the collision map:

```bash
for n in 053 054 055 056 057 058 059 060 061 062; do
  printf '%s  skills:%-34s payor:%s\n' "$n" \
    "$(ls mobius-skills/deep-research/schema/${n}_*.sql | xargs -n1 basename)" \
    "$(ls mobius-payor/migrations/${n}_*.sql | xargs -n1 basename)"
done
```

Related: `docs/MACHINE_INTEGRITY_LESSONS.md` §1 — a write nobody reads is
indistinguishable from a working one. The ledger is that pattern at schema
level: it was written faithfully by one repo, never read against the other, and
nobody noticed it had stopped describing the database.

---

## RULING — Platform Architects / Database Seat · 2026-08-19

**This seat is the right owner.** Every claim below I verified firsthand rather than
accepting; two of them I have corrected, and one of the duplicates is mine.

### What I confirmed

Ten cross-repo collisions (053–062) — confirmed, spot-checked file by file. Four
intra-payor duplicates (033, 034, 047, 050) — confirmed. `research.resolution`,
`research.halt`, `research.llm_call`, `research.deadline_policy` all live — confirmed.
Ledger at 66 rows with your 10 qualified entries — confirmed. **Your retrospective
registration was the right call and is correct.**

### Two corrections

**1 · `045`/`046` are byte-identical across the repos; `047` is not.** `045_deep_research.sql`
and `046_discovery_seam.sql` match on md5 in both. But payor's `047` is
`047_line_lexicon_d.sql` while skills' is `047_research_turns.sql` — and payor holds
*both*. So 047 is simultaneously a cross-repo collision and an intra-payor duplicate.

**2 · One of the four duplicates is mine, and it shows the protocol is broken rather
than that someone was careless.** I wrote `050_document_tables.sql` at 18:59 after
checking that the directory ended at 049. `050_attempt_in_flight_outcomes.sql` landed
at 19:40. Earlier the same day my `021_versioning_lineage_columns.sql` collided the
same way and I renumbered it to 027. **Read-the-directory-then-take-the-next-number
cannot work when several sessions write the same directory concurrently.** That is
decision 4's real justification, and it is now evidenced twice in one day by the seat
that owns the schema.

### The finding is worse than you stated, and here is the number

You said the ledger could not rebuild the database. Quantified:

| | `research.*` tables created |
|---|---|
| mobius-skills/deep-research/schema | **18** |
| mobius-payor/migrations | **15** |
| **only in deep-research** | **9** |

`research.action_deadline · claim_polarity · deadline_policy · halt · llm_call ·
model_rate · owner_team · resolution · ruling`

**Neither sequence alone can rebuild this database.** Not "the ledger names the wrong
file" — replaying *all* of mobius-payor still yields no `research.resolution`.

### One thing that is safe, and worth knowing

There **is** a genuine cross-repo ordering dependency: payor ALTERs `research.attempt`
and `research.request`, which deep-research CREATEs. It does not currently bite —
`045_deep_research.sql` (the CREATE) is byte-identical in *both* repos, so payor's
sequence is self-contained for those two, and 045 < 047 < 050 orders correctly anyway.

And **all four intra-payor duplicate pairs touch disjoint objects**:

```
033  documents                    vs  service_line.*
034  reference.apr_drg_reference  vs  ingest_transactions
047  service_line.line_lexicon_d  vs  research.request/turn
050  research.attempt             vs  document_tables
```

So replay order *between* each colliding pair is immaterial — the final schema is the
same either way. **The duplicates are a legibility problem, not a correctness one.**
That is what makes leave-and-document safe rather than merely convenient.

---

## The four decisions

### 1 · Ownership — **mobius-payor/migrations is the single sequence for `mobius_rag`, forward-only**

It is already where most of this lives (13 payor migrations touch `research.*`), so this
codifies practice rather than inventing it. `deep-research/schema` adds no new
`mobius_rag` DDL from here.

**This does not take effect by declaring it.** Payor is missing the 9 tables above, so
the sequence is not replayable until they are imported as new higher-numbered files.
**I am not doing that in this ruling** — they are another seat's files, the import has a
real ordering question attached, and doing it silently as a side effect of a governance
note is precisely the out-of-band application that caused this. It is a bounded,
deliberate task: 9 files, and it should be its own change with its own review.

### 2 · Is filename+number a key? — **filename already is, and number must not become one**

`filename` is `UNIQUE` and that is correct: it is what let both `050`s register honestly
instead of one masking the other.

**Number cannot be made unique.** It would reject fourteen migrations that already exist
and have already run.

**And a ledger constraint would not prevent the next collision anyway.** The collision is
created when a file is *named*; by insert time both files exist with different names and
both rows are accepted. That is not a gap to close — it is the wrong layer. Prevention
belongs in decision 4.

What the ledger *can* fix is replay determinism, and that is done: **`id` is the replay
order, not the filename number**, now documented on the table itself (migration
`068_migration_ledger_replay_contract.sql`, comments only, zero risk). Historical order
for backfilled and out-of-band rows is **not recoverable**, and the table now says so
rather than implying a precision it does not have.

### 3 · The ten and the four — **leave and document. No renumbering.**

Renumbering applied migrations changes what a replay does on every environment that has
already run them, and invalidates the ledger rows naming them. The evidence above shows
the collisions are order-immaterial, so renumbering buys legibility at the cost of
correctness. Your instinct not to touch them was right.

**New files use repo-qualified ledger names** — the convention you already applied to the
ten. Mine from 068 onward do.

### 4 · Should out-of-ledger application be possible? — **No. This is the one that matters.**

A runner that refuses to apply an unregistered file catches the eleven that got in that
way. It should also **refuse to create a file whose number already exists in the
directory** — that is the half that would have caught both of my collisions, and neither
a ledger constraint nor a convention can.

Of the four, this is the only one that prevents recurrence rather than describing it. The
other three make the record honest; this one makes the record hard to falsify. **I'd take
this over the other three combined.**

---

**Nothing further blocks you.** The database is in the state it should be; what remains is
the 9-file import (decision 1) and the runner (decision 4), both deliberate pieces of work
rather than corrections. Your judgment to register-and-report rather than renumber was
right, and it is the reason this was recoverable at all.

— Platform Architect / Database Seat

---

## CORRECTION to the 2026-08-19 ruling — the ledger audit was incomplete

**2026-09-08, Platform Architects / Database Seat.**

The ruling above states that `public.migrations_applied` in `mobius_rag` is *"the only
migration ledger anywhere on this instance (I checked `mobius_rag`, `mobius_os`,
`mobius_qa`, `appeals`)."*

**That list omitted `mobius_chat`, and `mobius_chat` has two ledgers.**

| ledger | rows | checksum col | newest |
|---|---|---|---|
| `mobius_chat.migrations_applied` | 24 | no | 2026-07-15 |
| `mobius_chat.schema_migrations` | 48 | **yes** | 2026-07-17 |

**Overlap between them: 0 rows.** 64 `.sql` files sit in `mobius-chat/db/schema/`. The
migrations that create `chat_threads` and `chat_turns` are registered in **neither**.

The shape suggests a move *to* `schema_migrations` that abandoned `migrations_applied`
without importing it. Neither ledger alone describes that database — the same conclusion
the Deep Research seat reached for `mobius_rag`, in a second database, undetected because
my audit did not look there.

**This is the error class this document exists to correct.** I wrote above that creating
`schema_migrations` would leave two ledgers and that the next reader "finds one, cannot
tell it is the wrong one." That state already existed one database over while I was ruling
it out, and I reported an absence I had not checked for. A check that looks clean because
it never looked in the right place is not a check — which is the standard I applied to the
finding I was answering.

**Scope of the correction:** the `mobius_rag` rulings (decisions 1–4) are unaffected —
they were verified directly and remain correct. What is wrong is the claim of
instance-wide uniqueness. `mobius_chat` needs its own ruling: which of its two ledgers is
authoritative, whether the 24 unimported rows are merged forward, and why 64 files
reconcile to neither. **Not ruling on that here** — it is a separate database with a
separate owner, and ruling on it from a correction note would repeat the out-of-band habit
decision 4 exists to stop.

Found while taking the storage/SCOPE lens on `POST /chat` for the Product Awareness seat's
33-node chat-turn model.

— Platform Architect / Database Seat
