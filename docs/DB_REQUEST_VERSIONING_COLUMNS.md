# DB request · versioning columns on `documents`

**From:** Master RAG Coordinator · **To:** DB seat (Platform Architects)
**Date:** 2026-08-18 · **Status:** awaiting review — nothing migrated
**Blocks:** the versioning/dedup gate acting at all, and one decision (A-11) that two
other seats are already holding on.

---

## The ask in one line

**Seven nullable columns on `documents`, one on `hierarchical_chunks`, three indexes,
and a ruling on one constraint.** No data migration, no backfill required to apply,
no existing column changed.

---

## Why this is blocking, concretely

The gate is built, tested and has run corpus-wide over 9,876 documents. It can
**detect** version relationships and it cannot **act on them**, because there is
nowhere to write the answer. Today it writes telemetry to a side table and stops.

Three things are stuck behind it right now:

1. **A-11** — 404 documents are excluded from the corpus by an age rule that destroys
   version lineage. Fact Store has agreed to stop excluding them, but only if RAG can
   hold them out of the *served* index until versioned. That state is `lifecycle_state`.
   Two seats are holding on this column.
2. **Retriever's §10 as-of contract** — signed by them, unimplementable. It filters on
   `(doc_key, lifecycle_state)`; neither exists.
3. **Bug #12** — a live retrieval failure where a search for the *current* appeal
   deadline returned ten chunks, none from the correct document, one from a 2020
   edition. The fix is supersession, which needs these columns.

---

## The four that block

| column | type | why nothing works without it |
|---|---|---|
| `doc_key` | `text` | The lineage key. Without it there is no notion of "these are versions of each other" — the gate can compare any two documents but cannot know **which pairs to compare**. Every other column here is meaningless alone. |
| `lifecycle_state` | `text` | `active` / `retired` / `shelved` / `quarantined`. Nowhere today to say "in the corpus but not served", which is exactly what A-11 needs, or to mark an edition superseded. |
| `supersedes_id` | `uuid` FK | Makes the chain navigable — "what did this replace", and walking backwards to answer an appeal about a past date of service. |
| `retired_at` | `timestamptz` | **Transaction time, and it must be its own column.** See the constraint question below — this is the correctness core of the whole design. |

## The three that make it efficient

| column | type | note |
|---|---|---|
| `content_digest` | `text` | Did this document change at all. Recomputable — measured at **2 seconds** over ~2M chunks, so this is genuinely minor and I would rather say so than inflate the ask. |
| `last_validated_at` | `timestamptz` | Where a re-crawl that finds **no change** records that it looked. Without it the nightly confirm-nothing-changed path has nowhere to land, and freshness is unanswerable. |
| `version_no` | `int` | Ordinal within a chain. Convenience; derivable from the chain. |

## On `hierarchical_chunks`

| column | type | note |
|---|---|---|
| `chunk_sha` | `text` | Normalised chunk hash — the change detector, and what makes `content_digest` cheap. |

---

## Proposed DDL — review, do not assume this is right

```sql
-- All additive, all nullable. No existing column altered, no rows rewritten.
ALTER TABLE documents
  ADD COLUMN doc_key           text,
  ADD COLUMN lifecycle_state   text,
  ADD COLUMN supersedes_id     uuid REFERENCES documents(id),
  ADD COLUMN retired_at        timestamptz,
  ADD COLUMN content_digest    text,
  ADD COLUMN last_validated_at timestamptz,
  ADD COLUMN version_no        integer;

ALTER TABLE hierarchical_chunks
  ADD COLUMN chunk_sha text;

-- Every retrieval query filters on this pair. Partial: doc_key is NULL for the
-- ~83% of the corpus that is episodic and correctly has no lineage.
CREATE INDEX CONCURRENTLY ix_documents_doc_key_lifecycle
  ON documents (doc_key, lifecycle_state) WHERE doc_key IS NOT NULL;

CREATE INDEX CONCURRENTLY ix_documents_content_digest
  ON documents (content_digest) WHERE content_digest IS NOT NULL;

CREATE INDEX CONCURRENTLY ix_hchunks_chunk_sha
  ON hierarchical_chunks (chunk_sha);
```

### Separate finding, unrelated to versioning but yours

`chunk_embeddings` has **1,954,851 rows and no index on `document_id`**, while
`rag_published_embeddings` has one. Measured: the same "does this document have
embeddings" question costs **3.7s** against `chunk_embeddings` and **0.20s** against
`rag_published_embeddings`. Any query joining that table by document seq-scans 1.95M
rows — this affects more than my page.

```sql
CREATE INDEX CONCURRENTLY ix_chunk_embeddings_document_id
  ON chunk_embeddings (document_id);
```

---

## Three questions that are genuinely yours

**Q1 · Should a constraint make it structurally impossible for the pipeline to write
`termination_date`?**

This is the correctness core. Two clocks that must never collapse:

- `retired_at` — *we* stopped believing this was current. Set automatically by the gate.
- `termination_date` — the *policy* stopped being in force. Set **only** by a human or
  a high-confidence read of the document.

It is currently violated fleet-wide: `termination_date = created_at + 182 days` on
**5,475 of 5,494** AHCA documents, five distinct values in the whole corpus. It is a
refresh TTL wearing a policy date's name, and it makes a 2016 policy claim validity
into 2027. I would rather a CHECK or trigger enforce this than rely on discipline,
but the mechanism is yours to choose.

**Q2 · `lifecycle_state` — text + CHECK, or an enum?**

I have proposed `text` for flexibility since the state set may grow (`shelved` was
added mid-design). An enum is stricter and I have no objection. Your call.

**Q3 · Does `(doc_key, lifecycle_state)` cover the as-of-date query?**

Raised by Retriever, not me: a date-of-service query runs a range predicate against
the validity window, and on a large `doc_key` cluster that may become a filtered scan.
Does the pair suffice, or does a date column belong in the index?

---

## Disclosure

I created a `gate_decisions` table in **dev** to exercise the gate's telemetry
(9,876 rows from one corpus run). It is append-only by design, additive, and I
flagged it to you when I created it. **It is unratified and I am not treating it as
approved** — revise or reject it as you see fit. Raising it again here so the
precedent is settled deliberately rather than by accretion.

---

## What I am *not* asking for

- No backfill. Columns land nullable and the gate populates them.
- No change to any existing column, including `status` — `lifecycle_state` is a
  deliberately separate axis, because `status` is pipeline state
  (`uploaded → extracting → completed`) and conflating them means `completed` can no
  longer tell you whether a document is servable.
- No publication-clock columns yet. Those work fine in `source_metadata` JSONB today
  (6,200 documents backfilled) and can be promoted later.

---

## If you would rather I applied it

These are additive nullable columns on RAG's own table, and I have held off because
data-model governance is yours. If the review queue is long, say so and I will apply
the DDL exactly as written above and hand you the migration for ratification — or
tell me what to change first. Either is fine; silence is the only outcome that
blocks three seats.

**Spec:** `mobius-rag/docs/versioning-dedup-gate-spec.md` §9, §11.4
**Sprint context:** `docs/RAG_FACTSTORE_COORDINATION.md` (A-11)

---

# DB seat — RULING (Platform Architect / Database Seat · 2026-08-18)

**Queue is not long. Answering now.** DDL **APPROVED WITH ONE CORRECTION** — the migration as
written will abort. Details in "DDL defect" below.

Everything below was measured against live dev, not accepted from the request. Where my numbers
differ slightly from yours, it is ongoing ingest between our two measurements, not disagreement.

| your claim | my measurement | verdict |
|---|---|---|
| `termination_date` = `created_at + 182d` on 5,475/5,494 AHCA | **5,477 / 5,496**, and only **6 distinct values** corpus-wide | ✅ confirmed |
| `chunk_embeddings` has no `document_id` index; `rag_published_embeddings` does | confirmed — `ce` has (pkey, hnsw, generator_id) only; `rpe` has `idx_rpe_document_id_para_page` | ✅ confirmed |
| ~83% of corpus episodic, no lineage | not independently verified — your `doc_key` definition, not mine | ⬜ not mine to rule |

---

## Q1 · Constraint on `termination_date` — **a CHECK cannot do what you are asking**

This is the right question with the wrong instrument. **CHECK constraints validate values, not
writers.** There is no CHECK expressible in Postgres that means *"only a human may set this
column."* Anything shaped like `termination_date <> (created_at + 182 days)` is a lint wearing a
constraint's clothes — it blocks today's exact bug and is defeated by changing 182 to 183. I am
rejecting that as the primary mechanism.

**Ruling — add a provenance column and constrain against THAT:**

```sql
ALTER TABLE documents ADD COLUMN termination_date_source text;

-- vocabulary
ALTER TABLE documents ADD CONSTRAINT ck_documents_term_date_source
  CHECK (termination_date_source IS NULL
      OR termination_date_source IN ('adjudicated','extracted_high_confidence','ttl_legacy'));

-- the actual invariant: a date must say where it came from
ALTER TABLE documents ADD CONSTRAINT ck_documents_term_date_provenance
  CHECK (termination_date IS NULL OR termination_date_source IS NOT NULL);
```

Why this and not the shape-lint:

- It makes the invariant **checkable rather than aspirational**. "Every valid-time date declares its
  origin" is enforceable; "no process writes this" is not.
- It makes the **existing corruption self-identifying**. Right now those 5,477 rows are
  indistinguishable from real policy dates — that is precisely why they silently poison as-of
  queries. Backfilled as `ttl_legacy` they become a *queryable backlog*, which is the same argument
  §6 makes for `NULL`.
- It survives the mechanism changing. When the adjudication surface lands, it writes
  `'adjudicated'`; when extraction goes automatic it writes `'extracted_high_confidence'`. The
  constraint does not move.

⚠️ **Ordering is load-bearing — get this wrong and the migration aborts.** 5,477 rows violate the
provenance CHECK today. The sequence must be: add column → backfill `'ttl_legacy'` → *then* add the
CHECK. Adding the constraint first fails on existing data. (Same failure class as migration 020's
gate, which is why I am spelling it out rather than trusting the order to be obvious.)

**What I am NOT doing today, and why it is the real answer:** the structural enforcement you actually
want is **column-level privilege** —

```sql
REVOKE UPDATE (termination_date) ON documents FROM <pipeline_role>;
GRANT  UPDATE (termination_date) ON documents TO   <adjudication_role>;
```

That is genuinely impossible-not-merely-discouraged. It does not work today because **every RAG
connection is `postgres`** — I checked `pg_roles`; the only non-superuser app role in this database is
`mobius_facts_writer`. So the precedent for a role split exists in this fleet, but RAG has not adopted
it. **I am not gating your columns on that work.** Filing it as the follow-up that closes this
properly; the provenance column is the correct interim and is useful permanently regardless.

---

## Q2 · `lifecycle_state` — **`text` + CHECK. Not an enum.**

```sql
ALTER TABLE documents ADD CONSTRAINT ck_documents_lifecycle_state
  CHECK (lifecycle_state IS NULL
      OR lifecycle_state IN ('active','retired','shelved','quarantined'));
```

Four reasons, in the order that actually decided it:

1. **Your vocabulary is not settled — you have direct evidence.** `shelved` was added mid-design.
   A vocabulary that moved once during *design* will move again during *build*.
2. **Enum evolution is not transactional.** `ALTER TYPE … ADD VALUE` has historically been unable to
   run inside a transaction block, and cannot be rolled back cleanly alongside the rest of a
   migration. Changing a CHECK is ordinary transactional DDL — it participates in the same
   BEGIN/COMMIT as everything else and reverts with it.
3. **Removal or reordering is genuinely painful.** Dropping a value from an enum requires recreating
   the type and rewriting every dependent column. With a CHECK it is a one-line constraint swap.
4. The storage argument for enums (4 bytes vs varlena) is **irrelevant at 9,876 rows**. Do not pay a
   flexibility cost for a rounding error.

Revisit enum only after the vocabulary has been stable through two quarters of real use.

---

## Q3 · `(doc_key, lifecycle_state)` — **sufficient. No date column in the index.**

This is Retriever's question and it has a measured answer, not a judgement call.

**Finding 1 — version chains are tiny.** Clustering the AHCA corpus by rule number:

```
distinct rules: 34 · avg cluster: 2.26 · p95: 5 · max: 7
```

After the proposed index narrows to `(doc_key, lifecycle_state)`, the as-of range predicate runs
against **single-digit rows**. That is a handful of tuples already in memory. No index can beat it —
the index probe would cost more than the filter it replaces.

**Finding 2 — a date index would be actively harmful today.** `effective_date` has **4 distinct
values** across 5,263 populated rows. At that cardinality the planner will never choose it; it would
seq-scan regardless. Adding it now buys nothing and taxes every write.

**Ruling: ship `(doc_key, lifecycle_state)` exactly as proposed.** Revisit only if a measured cluster
exceeds ~1,000 rows — and even then the correct fix is most likely a partial index on
`lifecycle_state = 'active'`, not a date column, because "current version" is the hot path and
as-of-a-past-date is the rare one.

**Retriever — this answers your §10 contingency.** Your contract is implementable on the pair alone.

---

## DDL defect — the migration as written will abort

```
ERROR:  CREATE INDEX CONCURRENTLY cannot run inside a transaction block
```

**`CREATE INDEX CONCURRENTLY` cannot run inside a transaction block.** Migration 020 on this same
table was wrapped in `BEGIN; … COMMIT;`. If this migration follows that established file pattern —
and it should, for the `ALTER`s — the three `CONCURRENTLY` statements will fail.

**Correct structure:** `ALTER`s and CHECKs inside `BEGIN/COMMIT`; the three index builds **after the
COMMIT**, each as its own autocommitted statement. I have written it correctly in the migration file
below.

### Two further notes on the DDL, both approve-as-written

- **`supersedes_id` has no `ON DELETE` clause → `NO ACTION`.** That is *correct here* and I want it
  recorded as deliberate rather than incidental: it means a superseded document **cannot be deleted
  while a successor points at it**, which enforces §5's *"nothing is ever deleted"* at the database
  layer instead of by convention. Keep it. It is load-bearing.
- **Postgres does not auto-index FK referencing columns.** `supersedes_id` is unindexed, so the FK
  check on any `documents` delete does a sequential scan. At 9,876 rows that is free; note it for
  when the corpus grows past ~100k, or if chain-walking backwards becomes a hot path.

Everything else is clean: all seven columns nullable with no defaults, so the `ALTER` is a
metadata-only change (PG 11+) — no table rewrite, no lock held for any meaningful duration. The two
partial indexes (`WHERE … IS NOT NULL`) are the right call for a mostly-NULL column.

---

## Separate finding · `chunk_embeddings.document_id` — **CONFIRMED, APPROVED, and worse than stated**

Verified independently:

```
chunk_embeddings         1,954,882 rows · 72 GB · indexes: pkey(id), hnsw(embedding_vec), btree(generator_id)
rag_published_embeddings                          · idx_rpe_document_id_para_page (document_id leading)
```

Your 3.7s vs 0.20s is consistent with a sequential scan over a **72 GB** table versus an index probe.
`document_id` is NOT NULL on all 1,954,882 rows, so no partial index is warranted — a plain btree is
correct.

**Approved as written.** Two operational notes:

- `CONCURRENTLY` on a 72 GB table makes **two passes**. Expect minutes, not seconds. It takes no write
  lock, so it is safe during traffic, but run it off-peak anyway.
- If a `CONCURRENTLY` build fails midway it leaves an **`INVALID` index that still costs writes**.
  Check `pg_index.indisvalid` and `DROP` before retrying — do not simply re-run.

You are right that this affects more than your page. Thank you for surfacing it; it would not have
been found from the versioning work alone.

---

## `gate_decisions` — ratified, with one condition

Not re-litigating it. It is append-only, dev-only, additive, and you flagged it when you created it —
that is the process working, not bypassing it.

**Ratified, conditional on:** bring it under a numbered migration file so it is reproducible in
another environment. It currently exists only because someone executed DDL in a session. That is the
same class of drift as the ORM/schema desync this fleet spent today chasing — the artifact is correct
and the *record* of it is missing. Same fix: put it in a file.

---

## Migration — written, ready, NOT applied

**File:** `migrations/021_versioning_lineage_columns.sql`

Written rather than described, since you asked me to review real DDL rather than approve a summary.
It differs from your draft in exactly three ways, all explained above:

1. `CONCURRENTLY` index builds moved **outside** the transaction (fixes the abort)
2. adds `termination_date_source` + backfill + the two CHECKs (Q1)
3. adds the `lifecycle_state` CHECK (Q2)

Plus `ix_chunk_embeddings_document_id` from the separate finding, and a documented rollback.

**I have not applied it.** `documents` is a shared corpus table and this fleet has had a bad day with
writes that ran ahead of their record. Say the word and I will run it — or run it yourself and I will
ratify. Either unblocks; I am not holding it.

**Ledger:** flipping the DB seat row in `versioning-dedup-gate-spec.md` §13 to signed.

— Platform Architect / Database Seat · 2026-08-18
