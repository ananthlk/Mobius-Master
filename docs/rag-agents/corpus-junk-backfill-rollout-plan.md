# Corpus Junk Backfill — Safe Rollout Plan (DRAFT v0)

**Owner:** Curation (which rows) + DB (execution mechanics) — same split as
`corpus-content-gate-spec.md` §5. **Status:** design 2026-07-23.
**Relationship to the gate spec:** `corpus-content-gate-spec.md` designs
`is_contentless()` and where it plugs into the *live* chunk→embed→publish
path (stops new junk). This doc scopes the *backfill* — removing the
~222k+ junk rows already published — as its own change, because it's a
one-shot bulk mutation against a 1.9M-row production table that live query
traffic reads from, which is a different risk class than a code change and
needs its own dry-run/rollback plan rather than inheriting the gate's.

Verified against code before writing this (not taking the spec draft's
claims on faith):
- `rag_published_embeddings` (`app/models.py:242-257`) has no `ForeignKey`
  on `source_id` — it's a dbt-contract table, not FK-enforced back to
  `hierarchical_chunks`/`chunk_embeddings`. Deleting published rows alone
  does **not** delete the source rows.
- `publish_document()` (`app/services/publish.py:76`) does a per-document
  **delete + re-insert** of that doc's published rows, reading from
  `chunk_embeddings`/`hierarchical_chunks`/`extracted_facts`. **This is the
  resurrection risk**: if a cleaned document is ever republished (manual
  republish, re-ingest, doc edit) before the source-table junk is also
  removed, the junk chunk regenerates and republishes itself unchanged.
- Closest in-repo precedent for this kind of cleanup: `scripts/clean_chroma_orphans.py`
  — idempotent, `--dry-run` flag, batched deletes with per-batch logging,
  run as a standalone script against `DATABASE_URL`, not through the live
  API. This plan follows that pattern.

---

## 1. Precondition — sequencing with the gate

**The code gate (`is_contentless` in `chunking.py` + `publish.py` backstop)
must land and be verified working before this backfill runs**, or the
backfill is chasing a moving target — any document re-chunked or
republished mid-cleanup would re-publish the same junk. If the gate can't
land first for scheduling reasons, this backfill must re-run (or the
target set must be re-queried immediately before each execution batch,
not once at planning time).

## 2. Target set — R1 + R2 only, explicitly NOT R3

Per `corpus-content-gate-spec.md` §3/§4, only ship what's already at
FP=0 with no calibration dependency:

```sql
-- R1: zero-alphanumeric content
length(regexp_replace(text, '[^A-Za-z0-9]', '', 'g')) = 0
-- R2: curated UI-chrome stoplist (exact match, case/whitespace-normalized)
OR text = ANY(:stoplist)   -- 'MS Word Viewer', 'Ok, I understand',
                            -- 'Windows Media Player', 'Twitter.com/AHCA_FL', ...
```

R3 (orphan-header: `GOVERNOR`/`SECRETARY`, ~18,270 rows) is **excluded from
this backfill** until it clears the FP=0 calibration gate in the spec's
§4. Shipping R3 rows in this pass would mean deleting rows nobody has
verified are actually contentless. If R3 later clears calibration, it gets
its own follow-up backfill pass, not folded in here silently.

**No silent cap:** this pass targets the ~222k rows matching the exact
strings already identified in the length≤30 histogram (`filler-b-vector-tracker.md`).
It does **not** cover the long tail of *other* short-but-distinct junk
strings that didn't make the top-15 list — re-run the histogram query
post-cleanup (§7) to check what's left before calling the corpus clean.

## 3. Durable retire — three tables, not one

Delete matched rows from all three, keyed by `(document_id, source_id)`
carried over from `rag_published_embeddings` to its source rows:

1. `rag_published_embeddings` — the published/served copy.
2. `chunk_embeddings` — the embedded copy (`source_type='hierarchical'`,
   `source_id` = `hierarchical_chunks.id`).
3. `hierarchical_chunks` — the chunk itself.

All three in the same transaction per batch (see §6), same predicate
applied at each table (`chunk_embeddings`/`hierarchical_chunks` matched by
`id = source_id` collected from the `rag_published_embeddings` scan, not
re-evaluated against `text` on `hierarchical_chunks` — confirm the text
matches before deleting to guard against `source_id` collision/reuse).
Skipping tables 2-3 is the resurrection bug described in §"Verified
against code" above — do not ship a published-only delete.

## 4. Reversibility — archive before delete

This is a DELETE against production, not an UPDATE — there is no soft-undo
without a backup. Before any batch deletes:

```sql
CREATE TABLE IF NOT EXISTS rag_published_embeddings_junk_archive
  (LIKE rag_published_embeddings INCLUDING ALL);
```

Each batch: `INSERT INTO ..._junk_archive SELECT * FROM rag_published_embeddings
WHERE id = ANY(:batch_ids)` **before** the corresponding delete. Do the
same (or a flat export) for the `chunk_embeddings`/`hierarchical_chunks`
rows being removed — the published-row archive alone can't reconstruct a
chunk's embedding model/version metadata.

**Rollback procedure:** re-`INSERT ... SELECT` from the archive table back
into the live tables by `id`. Keep the archive for a fixed retention window
(e.g. 30 days) post-cleanup, then drop it once the before/after eval run
(§8) has confirmed no regression.

## 5. Pre-flight checks (run immediately before execution, not at planning time)

1. **Fresh recount** — re-run the §2 predicate query against current
   `rag_published_embeddings`. The 222,303 figure is from 2026-07-23;
   confirm it hasn't moved unexpectedly (new ingests could add more junk
   if the gate hasn't landed yet — see §1).
2. **Sample spot-check** — pull a random 100-row sample matching the
   predicate, human-review for any row that has real content the R1/R2
   rules shouldn't have caught. Zero tolerance: any false positive in the
   sample blocks execution until the predicate is fixed.
3. **must_facts zero-overlap** — per the gate spec's §4 FP guard, confirm
   zero rows matching the backfill predicate appear among the eval bank's
   (`eval/queries_cmhc.yaml`) golden-answer/must_facts-bearing chunks.

## 6. Staged execution

1. **Dry run** (`--dry-run`, mirrors `clean_chroma_orphans.py`): count and
   log matches per table, per rule (R1 vs R2), no writes. Compare against
   §5.1's fresh recount.
2. **Canary batch** — smallest bounded batch (e.g. 1,000 rows, one
   `document_id` at a time to keep the archive/delete atomic per doc).
   Run archive→delete on all three tables for the canary only. Verify:
   vector search still returns results for a few sanity queries, row
   counts dropped by exactly the canary size, no errors in RAG service
   logs.
3. **Full batched run** — bounded batches (start at 5,000-10,000 rows per
   transaction, tune down if lock contention/timeout appears), looping
   with the same archive→delete→log pattern, idempotent (safe to re-run —
   already-archived/deleted rows are no-ops). Log running totals per
   batch, matching `clean_chroma_orphans.py`'s per-batch logging style.

## 7. Execution mechanics / constraints

- **Run as a standalone script** (`scripts/backfill_junk_cleanup.py` or
  similar) against `DATABASE_URL` directly — not through the live RAG API,
  which is pinned to `max=1` with in-process job state
  (`feedback_rag_api_max1_inprocess_state`) and isn't the right surface
  for a long-running bulk job.
- **Off-peak window**, batches paced with a short sleep between them to
  avoid saturating the connection pool or tripping `idle_in_transaction_session_timeout=120s`
  (`project_rag_connection_leak`) — each batch's transaction should commit
  well under that window.
- **Idempotent**: re-running after a partial failure should pick up where
  it left off (predicate-driven, not offset-driven — already-deleted rows
  simply won't match anymore).

## 8. Downstream considerations

- **Answer cache** (`mobius_cache`, pgvector, `project_answer_cache_service`) —
  cached answers derived from junk-dominated retrievals may still be
  served stale post-cleanup until TTL expiry. Flag to the cache owner
  whether a targeted invalidation is warranted or TTL is acceptable —
  don't assume either without checking.
- **BQ/analytics sync** — if any downstream BQ mirror of
  `rag_published_embeddings` exists (`project_module_sync_contracts`
  flags BQ↔PG contract gaps as a known problem area in this fleet),
  confirm whether it needs re-sync after this delete or will silently
  drift.

## 9. Post-run verification

1. **Row count delta** — table count dropped by exactly the batches'
   summed total across all three tables; archive table count matches.
2. **Fast smoke test** — re-run Filler-b's exact two live queries from
   `filler-b-vector-tracker.md` ("timely filing deadline for Sunshine
   Health FL Medicaid claims", "credentialing requirements for a new
   provider group") directly against `PublicSourceAdapter.vector_search()`;
   confirm top-N is no longer dominated by dash/header junk. Cheap,
   immediate, catches a broken predicate before waiting on the full bank.
3. **Full eval-bank before/after** — per the gate spec's §6 protocol
   (`eval/queries_cmhc.yaml`, full-pool + vector-arm-only `oracle_recall`
   slices). This is the authoritative lift number; §9.2 is a sanity gate
   in front of it, not a replacement.

## 10. Gates / sign-off

| Gate | What it checks |
|---|---|
| Curation | owns which rows (predicate correctness, §2-3) |
| DB | owns execution mechanics (§4-7): archive design, batching, transaction safety |
| Eval | §5.3 must_facts guard pre-run; §9.3 before/after lift post-run |
| Maintaining | inherits the ongoing sweep once this one-shot backfill closes — re-running the histogram query periodically to catch new junk patterns is nightly-sweep scope, not this doc's |

Do not execute against production until Curation + DB have both signed off
on this plan specifically (separate from any sign-off already given to the
gate design in `corpus-content-gate-spec.md`).
