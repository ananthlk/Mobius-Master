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
