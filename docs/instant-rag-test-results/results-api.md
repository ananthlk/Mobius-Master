# Instant RAG — API Results (automated)

Runner: `run_api_tests.sh` (re-runnable). Raw output: `raw/api_results.txt`.

## Run 1 — 2026-07-13 18:30 UTC · RAG rev `mobius-rag-00315-57w`

🔴 **FULL OUTAGE — every case failed.** All 5 docs uploaded successfully (~1 s, valid
`document_id`) but **none became searchable** within the poll window; no verification
phrase or facts retrieved.

| ID | File | Format | Size | Upload | Time-to-searchable | Phrase | Facts |
|----|------|--------|------|--------|--------------------|--------|-------|
| A | t_alpha_quickfacts.txt | txt | 287 B | 1 s | **TIMEOUT (60 s)** | ❌ | ❌ |
| B | t_bravo_payer.txt | txt | 500 B | 1 s | **TIMEOUT (60 s)** | ❌ | ❌ |
| C | t_charlie_policy.html | html | 572 B | 1 s | **TIMEOUT (60 s)** | ❌ | ❌ |
| D | t_delta_auth.pdf | pdf | 1.6 KB | 1 s | **TIMEOUT (60 s)** | ❌ | ❌ |
| E | t_foxtrot_large.txt | txt | 1.6 MB | 1 s | **TIMEOUT (200 s)** | ❌ | ❌ |

### Diagnosis — silent DB lock (P0 outage)
- **Systemic, not cold-start:** all 5 failed (cold A *and* warm B–E). A cold-start would
  fail only A.
- **Uploads accepted, publish stalled:** `/upload` returns ~1 s (background_sync), but
  there is **zero `[publish]`/`[instant]`/`rag_published_embeddings` activity** in RAG
  logs — the inline publish never completes, so docs never commit to pgvector.
- **Silent — no error logs:** no lock/deadlock/`InFailedSQLTransaction`/timeout entries.
  Consistent with queries **blocking on a lock**, not erroring.
- **Regression:** the same path was **9 s warm on `00313`** (see run history) two hours
  earlier. Broke on `00315`.

**Most likely:** a blocking lock on `rag_published_embeddings` (pgvector) — a runaway
cleanup / backfill / reindex / `VACUUM FULL`, or an `idle in transaction` session holding
the lock — stalls every inline publish. (Ananth flagged "RAG is doing some cleanup"
earlier; this may be it.)

**Action:** escalated to RAG (has DB access) to inspect `pg_stat_activity` / `pg_locks`
for the blocker and terminate/throttle it. Re-run `run_api_tests.sh` after; expect
searchable in ~9–17 s per doc when the lock clears.

## Run 2 — 2026-07-13 18:44 UTC · RAG rev `mobius-rag-00315-57w` (post-lock-kill)

RAG terminated the blocking transaction (a 41-min, 743k-row single-transaction UPDATE of
`rag_published_embeddings` — the chunk_tags backfill — holding a row-exclusive lock). Re-ran:

| ID | File | Format | Size | Time-to-searchable | Phrase | Facts | Notes |
|----|------|--------|------|--------------------|--------|-------|-------|
| A | t_alpha_quickfacts.txt | txt | 287 B | **TIMEOUT** | ❌ | ❌ | deduped to Run-1 zombie doc `2c918c2e` |
| B | t_bravo_payer.txt | txt | 500 B | **TIMEOUT** | ❌ | ❌ | deduped to Run-1 zombie doc `2e14f363` |
| C | t_charlie_policy.html | html | 572 B | ✅ **1 s** | ✅ | ✅ | fresh doc, correct |
| D | t_delta_auth.pdf | pdf | 1.6 KB | ✅ **0 s** | ✅ | ✅ | fresh doc, correct |
| E | t_foxtrot_large.txt | txt | 1.6 MB | ✅ **2 s** | ✅ | ✅ | fresh doc; found buried phrase in 2 s |

**Verdict:** ✅ **Outage cleared — instant-RAG upload→index→retrieve is healthy and fast**
(0–2 s, all formats, 1.6 MB large-doc included).

**Edge case (A/B) — RESOLVED same day:** docs uploaded *during* the outage got a committed
`documents` row but **no embeddings** (publish transaction killed with the lock), so
re-uploading deduped to the zombie shell.
- ✅ **Cleanup:** RAG retried the 3 orphans (`c485c12c`, `2c918c2e`, `2e14f363`) via
  `POST /documents/{id}/retry`; **verified both suite zombies are now searchable** —
  `2c918c2e` → "copper falcon 12", `2e14f363` → "indigo walrus 55".
- ✅ **Dedup hardened** (RAG commit `5c52145`): when `file_hash` matches but
  `rag_published_embeddings` count = 0, delete the zombie row and fall through to normal
  ingest instead of raising 409. Prevents this permanently.

**Net after resolution: all 5 cases pass.** (A/B via the orphan retry; C/D/E fresh in 0–2 s.)

### Prior good baseline (for contrast)
- `00313`, 2026-07-13 (curl, chat-facing `/api/query` path): **cold 17 s, warm 9 s** —
  the target-passing result before this regression.
