# "Blocked ⟹ not stored" — a fail-closed invariant that only half-holds

**Status:** OPEN · prep for a 4-way + Ananth · **pickup tomorrow (2026-09-10)**
**Convened by:** Ananth · **Seats:** Extension (coordinator here) · Chat Master (mobius-chat) · Master RAG (mobius-rag) · PHI classifier (mobius-skills/phi-classifier)
**Scope:** the fetch-to-RAG upload lane (`/chat/upload` → rag `/upload` → gate → publish/purge)

> This page is a shared work surface. Each seat has a section below — fill in your half tomorrow. Nothing here is a decision yet; it's the assembled evidence so the call can be made fast. Verified facts are attributed to who verified them and as of which commit (cross-repo claims decay — re-confirm against your deployed rev before acting).

---

## The invariant we expect
A document the system tells the user was **blocked / "not stored"** must leave **no trace** — no GCS blob, no DB row, no `file_hash` dedup key, no chunks. Fail-closed means closed: a later re-upload of the same bytes must not read as an already-stored duplicate, and a genuinely-PHI doc must never persist unscreened.

## What actually happens (verified)
Chat forwards the bytes to rag **before** the sync PHI verdict, and the purge that deletes a blocked doc lives **inside** the gate function — so it only fires for blocks the gate itself decides.

| Block verdict | Decided | Purged from storage? |
|---|---|---|
| `blocked_phi` (genuine PHI) | inside gate | ✅ yes |
| `blocked_indeterminate` (real classifier verdict) | inside gate | ✅ yes |
| `blocked_indeterminate` (chat catch-all exception) | outside gate | ❌ **no** |
| `blocked_publish_failed` (`185f426`) | outside gate | ❌ **no** |
| `blocked_unconfigured` (`e6b153e`, held) | outside gate — gate never runs | ❌ **no** |

**The bottom three tell the user "not stored" while the bytes sit in rag with a live dedup key.**

### The sharpest corner (compliance)
`blocked_unconfigured` means the gate **never runs at all**. A genuinely-PHI doc uploaded while the classifier URL is unset would be **stored, unscreened, AND reported "not stored"** — the worst cell in the table. Not live today (the var is set), but this is the case that makes this a compliance decision, not a cleanup nicety.

---

## Evidence (attributed, as-of commits)

**Chat Master (mobius-chat), verified by AST:**
- `_handle_instant_rag_upload` L1638 `POST {rag_url}/upload` (bytes leave) → L1826 `_run_hipaa_gate_sync` (verdict), 188 lines later.
- The purge DELETE is **inside** `_run_hipaa_gate_sync` (`[hipaa-gate] DELETE ok doc=… (embeddings purged)` ~L1485). Blocks decided outside that function never reach it.
- `blocked_publish_failed` (`185f426`) **preserves the classifier's real gate** (often `clean`); `blocked_unconfigured` (`e6b153e`, held for deploy) fails closed when `PHI_CLASSIFIER_URL` is unset.

**Master RAG (mobius-rag), verified by line offset in `/upload`:**
- L196 `blob.upload_from_string` (GCS write) → L325 `db.add(document)` (row + `file_hash` dedup key) → L422 `classify_for_ingest` (verdict). **Dedup key is written 97 lines before rag classifies.**
- rag `/upload` has **no PHI gate** — the `indeterminate` verdict is upstream (chat), not rag.
- Existing cleanup: `if _chunks_count == 0 and existing_doc.status == "phi_blocked": → 409 phi_blocked + delete row so retry re-ingests`. **Guarded on `chunks_count == 0` — skipped exactly when a blocked doc got chunked**, which is the case that persists.

**Extension (this seat), reproduced on live dev:**
- Small **clean** PHI-free PDF: sync POST → `status:"blocked", gate:"indeterminate"` ("not stored"), a `document_id` assigned; re-POST same bytes → `status:"ready", ux_path:"duplicate", chunks_count:2`. You can't dedupe against something never stored — so it was stored.
- Most of these clean-doc "indeterminate" repros are likely **chat's catch-all firing on rag's non-idempotent publish (pkey collision)**, not a real classifier indeterminate — the two share the `blocked_indeterminate` string until `185f426` re-labels them to `blocked_publish_failed`.

**PHI classifier (mobius-skills), contract confirmed:**
- Genuine PHI is **always** `gate == "phi"`, never any other value. `gate == "indeterminate"` is exclusively "couldn't confirm clean" (LLM unavailable + regex/NER found nothing) — never a detection.
- Retry-with-backoff shipped (`00030-5p7`, live): deadline-bounded ≤40s (< chat's 45s), closes short breaker windows so brief blips stop producing false indeterminates. Sustained outage still degrades → async recovery.

---

## Candidate fixes (not decided)
1. **Chat-side:** move the purge from *inside the gate function* to the **block decision point**, so every fail-closed path (`unconfigured`, `publish_failed`, catch-all) purges — not just the ones the gate reaches. *(Chat Master: "the purge belongs at the block decision point, not inside the one function that happens to reach it first.")*
2. **Rag-side:** make a blocked doc **un-chunkable**, or widen the cleanup past the `chunks_count == 0` guard so a blocked-but-chunked doc is still purged. *(Master RAG: destructive path — "delete a document that has chunks and may be published" — needs the chat-ordering answer first to pick the right one.)*
3. **Ordering:** gate **before** the rag write (upload-then-gate-then-publish), so blocked bytes never land. Largest change; addresses the root rather than cleaning up after.

The right fix depends on where the invariant should be enforced; that's the 4-way's call.

## Adjacent, possibly one thread
The **non-idempotent publish** (rag pkey collision → chat catch-all → `blocked_indeterminate`) is filed separately with Ananth and may be the same root as several "indeterminate on a clean doc" reports. `185f426` re-labels that population to `blocked_publish_failed`; resolving idempotency likely shrinks this problem before any purge change.

## Already handled (no decision needed)
- **Extension block-card copy** (`97aca80`, mobius-os): PHI card **iff** `gate == "phi"`; every other block renders as non-PHI (`try again` / `service unavailable`). So the user is not falsely told "flagged for PHI" for a storage or config failure. This is UX only — it does **not** fix the storage invariant.

---

## Seat sections — fill in tomorrow

### Ananth — the decision
- Which enforcement point owns "block ⟹ purge": chat decision-point, rag cleanup, or gate-before-write? _(pending)_
- Priority vs. the `source_origin` deploy (`e6b153e`) and the non-idempotent-publish fix. _(pending)_

### Chat Master (mobius-chat)
- Confirm current forward-then-gate ordering still stands on your deployed rev. _(pending)_
- Feasibility/blast-radius of moving the purge to the decision point. _(pending)_

### Master RAG (mobius-rag)

**(b) Publish pkey collision — ANSWERED 2026-09-09. It is a RACE, not a logic bug,
and it is smaller than it looked.**

`rag_published_embeddings.id = chunk_embeddings.id` (publish.py:281 `id=ce.id`) —
the published row reuses the embedding's key rather than minting one. That is
deliberate and fine on its own. The publish sequence is:

    line 316   rows.append(row)                        build in memory
    line 347   DELETE ... WHERE document_id = X        scoped, correct
    line 349   db.add(row) x N
    line 350   await db.flush()

So it IS delete-then-insert, correctly scoped, in one transaction. **Sequential
republish of the same document is already safe.** I expected to find a missing
delete and did not.

The collision is CONCURRENT publishes of the SAME document. Under READ
COMMITTED, T1 deletes and inserts uncommitted; T2's delete cannot see T1's
uncommitted rows, so T2 inserts the same ids and violates the pkey on flush.
That matches the reported shape exactly: 9x/24h, and triggered by repeatedly
uploading identical bytes — dedup resolves them to ONE document, so retries
stack concurrent publishes on a single row set.

Two candidate fixes, and I want the meeting's view rather than picking alone:

  1. `ON CONFLICT (id) DO UPDATE` on the insert. Smallest change; makes publish
     idempotent by construction. Note `publish_sync.py:352` already does exactly
     this for the CHAT-side store (`published_rag_metadata`), so the pattern is
     established in this codebase and the rag-side table is simply the one that
     never got it.
  2. A per-document advisory lock around publish. Stronger — it also serialises
     the read side — but it introduces a lock nobody currently holds, and a
     stuck publish would then block subsequent ones rather than racing them.

I lean (1) for symmetry with the chat-side store, but (2) is worth ten minutes
if we think two publishes of one document is itself a bug worth surfacing rather
than absorbing.

**Why this may shrink the invariant problem:** a publish that dies on the pkey
leaves the document in a state chat's catch-all labels `blocked_indeterminate`.
That is very likely the source of at least some observed "blocked" verdicts that
were never PHI decisions at all. Fixing (b) first may remove a chunk of the
population before any purge change is designed.

**(a) Un-chunkable vs widened cleanup — POSITION, with the constraint that
decides it.**

The cleanup guard is `if _chunks_count == 0 and existing_doc.status ==
"phi_blocked"`. It is guarded on the condition that is false precisely when
cleanup is needed, which is the defect already recorded above.

I do NOT recommend simply widening it past `chunks_count == 0`. That converts
the branch into "delete a document that has chunks and may be published", which
is destructive on a path reached by an ordinary re-upload. Getting that wrong
removes real corpus.

The better shape, given Chat Master's confirmed ordering (bytes forwarded L1638,
verdict L1826):

  **rag should not START chunking for bytes whose verdict is still outstanding.**

Today `/upload` enqueues the chunking job at the end of the handler, so by the
time chat's gate decides, chunking may already be running or done. Making the
block un-chunkable therefore requires the forwarding side to tell us the verdict
is pending — a two-phase ingest (`hold` on arrival, `release` or `purge` on
verdict) rather than a cleanup that races the chunker.

That is a contract change across chat and rag, not a one-line guard, which is
why I am bringing it as a position rather than a patch. If the meeting prefers
the smaller move, the honest interim is: keep the guard, and have the purge
delete chunks too rather than refusing when they exist — but that is still a
destructive path and it still races.

**Constraint the meeting should know:** whatever we choose, `/upload` writes the
GCS blob (handler line 196) and the document row carrying the `file_hash` dedup
key (line 325) BEFORE it calls the classifier (line 422). Any invariant of the
form "a blocked document leaves no trace" is unachievable at `/upload` without
either deferring those writes or accepting a purge. There is no ordering of the
current handler that satisfies it.

### PHI classifier (mobius-skills)
- Confirm no block path emits genuine PHI as anything but `gate == "phi"`. _(confirmed 2026-09-09; re-affirm if the tri-state changes)_
- Any gate-side signal that would help chat/rag decide purge deterministically. _(pending)_

### Extension (this seat)
- Re-run the clean-PDF repro against `00030-5p7` + post-deploy `e6b153e`/`185f426`; report whether the sync-indeterminate coin-flip drops and whether "not stored → duplicate" still reproduces. _(pending deploy)_
- No extension change needed for the invariant itself — the card copy already tells the truth per verdict. _(done)_
