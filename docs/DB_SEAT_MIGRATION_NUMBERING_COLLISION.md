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
