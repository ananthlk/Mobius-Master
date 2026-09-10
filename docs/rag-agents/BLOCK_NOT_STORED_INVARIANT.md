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
- Can a blocked doc be made un-chunkable, or the cleanup widened safely past `chunks_count == 0`? _(pending)_
- Idempotency fix status for the publish pkey collision. _(pending)_

### PHI classifier (mobius-skills)
- Confirm no block path emits genuine PHI as anything but `gate == "phi"`. _(confirmed 2026-09-09; re-affirm if the tri-state changes)_
- Any gate-side signal that would help chat/rag decide purge deterministically. _(pending)_

### Extension (this seat)
- Re-run the clean-PDF repro against `00030-5p7` + post-deploy `e6b153e`/`185f426`; report whether the sync-indeterminate coin-flip drops and whether "not stored → duplicate" still reproduces. _(pending deploy)_
- No extension change needed for the invariant itself — the card copy already tells the truth per verdict. _(done)_
