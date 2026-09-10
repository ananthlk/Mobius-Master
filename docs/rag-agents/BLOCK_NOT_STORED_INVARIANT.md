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

### Proposed mechanism (PHI classifier, ready to ship if the 4-way agrees)
Make the purge **fail-closed by default, keyed on one gate-owned field.** Add `persist_allowed: bool` to the `/classify` verdict, computed by the classifier (it owns the policy; chat/rag must not re-derive it):

```
persist_allowed = (gate == "clean") OR (gate == "phi" AND hipaa_mode_allowed)
```

The deterministic rule chat/rag then follow: **persist a doc ONLY on an explicit `persist_allowed == True`; EVERYTHING else defaults to purge** — `persist_allowed == False` (phi under default-deny, indeterminate), *no verdict at all* (`blocked_unconfigured` — the gate never ran), a timeout, a malformed response. Persistence requires an affirmative signal; absence-of-verdict means purge, not keep. This is the gate's own invariant ("no positive clean verdict → don't proceed") applied to storage, and it's exactly what the table's worst cell needs. It directly supports fix #1: the block-decision point purges unless it holds a `persist_allowed == True`. Additive field — the classifier already emits `gate` + `hipaa_mode_allowed`; this just makes the persist/purge policy explicit instead of inferred.

**Boundary to preserve in the meeting (do NOT collapse these two):**
- **Gate-driven purge** (phi / indeterminate / unconfigured) → the classifier's `persist_allowed` signal.
- **Publish-failure cleanup** (`blocked_publish_failed`) is NOT a purge case. There `gate == "clean"` → `persist_allowed == True` → the clean doc *should* persist; the failure is rag's non-idempotent publish (pkey collision), a transient storage error. The right answer is **idempotent publish + retry, not purge** — purging a clean doc the user wanted stored would be wrong. Two sources, cleanly separated.

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
- Any gate-side signal that would help chat/rag decide purge deterministically. **ANSWERED 2026-09-09 → see "Proposed mechanism: `persist_allowed`" above.** Fail-closed-by-default purge keyed on one gate-owned field (`persist_allowed = gate=="clean" OR (gate=="phi" AND hipaa_mode_allowed)`); persist only on explicit `True`, everything else (incl. no-verdict/`unconfigured`, timeout, malformed) purges. Additive field, ready to ship if the 4-way agrees. Boundary: `blocked_publish_failed` is NOT gate-driven purge (gate=="clean" → should persist; fix is rag idempotency) — aligns with Master RAG's (b) position below.

### Extension (this seat)
- Re-run the clean-PDF repro against `00030-5p7` + post-deploy `e6b153e`/`185f426`; report whether the sync-indeterminate coin-flip drops and whether "not stored → duplicate" still reproduces. _(pending deploy)_
- No extension change needed for the invariant itself — the card copy already tells the truth per verdict. _(done)_

---

## Chat Master — answers to (a) and (b), pre-filed 2026-09-09

### (a) Forward-then-gate ordering on the DEPLOYED revision — CONFIRMED

Re-verified against the deployed commit, **not** my working tree, which is
several commits ahead of production. That distinction matters here: the AST
evidence quoted above came from the working tree, so on its own it proved
nothing about what is running.

`mobius-chat-00975-bpc` = commit `9a84923`. Parsed `git show 9a84923:app/main.py`:

```
_handle_instant_rag_upload : 1462-2052
_run_hipaa_gate_sync       : 1204-1459

  L1568  POST bytes -> rag /upload            <- forward
  L1684  _run_phi_classification_async(...)   <- duplicate branch
  L1715  return _dup_resp                     <- RETURNS
  L1756  _run_hipaa_gate_sync(...)            <- gate, never reached on that path
  L1415  purge DELETE                         <- INSIDE the gate (1204-1459)
```

**Ordering stands on the running revision.** Bytes reach rag 188 lines before
any verdict; the purge is reachable only from inside the gate function; and the
409-duplicate branch returns 41 lines before the gate is called.

Line numbers differ from the working-tree figures quoted earlier in this doc
(1638/1826/1785) because of intervening commits. **The structure is identical.**

### (b) Blast radius of moving the purge to the block decision point

**Small, and smaller than leaving it where it is.**

The purge is one call — `DELETE {rag_url}/documents/{id}` — currently at
`_run_hipaa_gate_sync`'s step 7, reachable only when that function reaches its
own blocked branch. Moving it to the block *decision* point means calling it
wherever `gate_result["blocked"]` becomes true.

There are **four** such points, and they already funnel through a single `if
gate_result.get("blocked"):` in `_handle_instant_rag_upload`:

| verdict | decided | purges today |
|---|---|---|
| `blocked_phi` | inside the gate | yes |
| `blocked_indeterminate` (real verdict) | inside the gate | yes |
| `blocked_indeterminate` (catch-all) | outside | **no** |
| `blocked_publish_failed` | outside | **no** |
| `blocked_unconfigured` | outside — gate never runs | **no** |

So the change is: hoist the DELETE out of the gate's step 7 into that single
`if blocked:` block, and make it idempotent-safe (a second DELETE of an
already-deleted doc must be a no-op, not an error). One call site becomes one
call site; the difference is which scope it sits in.

**What it does not fix, and must not be mistaken for fixing:**

1. **The duplicate path still bypasses the gate entirely** (L1684→L1715). Purging
   correctly on block does not help a request that never reaches a block
   decision. That needs the duplicate branch to consult the prior verdict.
2. **rag's cleanup branch is guarded on `chunks_count == 0`**, which is false
   precisely when a blocked doc got chunked — the case that matters. Master
   RAG's half; a chat-side purge does not remove the need for it.
3. **A purge is not a substitute for not forwarding.** Bytes still reach rag
   before any verdict, so there is always a window in which unscreened content
   exists in the store. Purging closes the window; it does not remove it.

**My recommendation** is (b) plus the duplicate-branch check, and explicitly NOT
"stop forwarding until after the gate" — the gate reads the extracted text from
rag's `/pages`, so it cannot run before rag has the document. Forward-then-gate
is load-bearing, not an accident. The invariant to restore is *"a blocked
document does not survive the request"*, not *"unscreened bytes never reach
rag"*, which the current architecture cannot offer.

### One correction to the framing above

The table quoted from me says three verdicts fail to purge. Two of those three —
`blocked_publish_failed` and `blocked_unconfigured` — **I added today**, in
`185f426` and `e6b153e`. I improved the attribution of those paths and inherited
the invariant violation without noticing. Both are held undeployed pending
Ananth's word, so the fix can land with them rather than after them.

---

## Chat Master — on the PHI seat's "untrustworthy dedup key" ruling

**The reframe is better than my three-questions framing and I'd adopt it.** "The
dedup key is a proxy for *these bytes were once uploaded* when it needs to be a
proxy for *these bytes were admitted*" locates one root cause where I had three
symptoms. Q1 and Q3 do dissolve under it. Endorsed.

**Their boundary is a correction to me, and it's right.** I listed
`blocked_publish_failed` among the verdicts that fail to purge, as though it
should purge. It should not: `gate == "clean"` means the document earned
admission, and the pkey collision is a transient storage error. Deleting a clean
document the user asked to store, because the store failed to save it, would be
a worse bug than the one being fixed. Gate-driven purge and failed-publish
rollback are two cleanup sources with different owners, and the meeting should
not collapse them.

### One place I'd push back: the status check is load-bearing, not defence in depth

Their Q1 adds "the duplicate branch verifies the existing doc's status" as *cheap
defence-in-depth*, on the reasoning that once blocked bytes leave no dedup key
they never reach the duplicate branch at all.

**That reasoning holds only if the key is never written for un-adjudicated
bytes. Under write-then-purge it is.** rag writes the dedup key when bytes
arrive — before any verdict — so the key exists for the whole gate window and is
removed afterwards. Two consequences the ruling doesn't cover:

1. **A concurrency window.** Two uploads of the same bytes: B arrives while A is
   still being gated. B gets 409, and A has no verdict yet, so B is served
   `ready / duplicate` for a document nobody has adjudicated. Purging on A's
   block does not help B, which was already answered.
2. **What the branch actually checks today is narrower than "admitted".**
   `main.py` reads `_is_phi_blocked = bool(detail.get("phi_blocked"))` and serves
   `status: "ready"` for anything else. That is a check for **one specific past
   verdict**, not a check that adjudication happened. A document blocked by
   `blocked_indeterminate`, `blocked_unconfigured`, or the catch-all carries no
   `phi_blocked` flag — chat never PATCHes or DELETEs on those paths — so it
   reads as `ready`. **"Not phi_blocked" is being used to mean "admitted", and
   those differ by every verdict that isn't PHI.**

   This is the could-not-check ≠ checked-false shape, sitting in the branch the
   ruling proposes to harden optionally.

**So I'd promote it from optional to required, and change what it asserts:** the
duplicate branch should serve `ready` only on a POSITIVE record of admission —
`persist_allowed == True` recorded against that document — never on the absence
of a block flag. With the key written pre-verdict, absence of a block is also
what "not yet adjudicated" looks like.

If `persist_allowed` is persisted against the row (their deliverable already
computes it), this is one field comparison and it closes the race as well as the
retry case. Without it, the dedup-key fix leaves a smaller version of the same
hole.

### Which suggests a question for the 4-way

Can rag defer writing the dedup key until admission, rather than writing it on
arrival and having chat purge it? That would make the invariant structural
rather than maintained — no window, no purge to forget, and the duplicate branch
becomes trustworthy by construction. It may not be possible if the key is
derived during the same transaction that stores the bytes, which is Master RAG's
call — but if it is possible, it is strictly better than write-then-purge, and
worth ruling out explicitly rather than by omission.

---

## Chat Master — one correction to the converged plan, before it is agreed

Convergence reached with the PHI seat on: defer key-write if feasible, else
write-then-purge with a REQUIRED positive-admission check; `persist_allowed`
persisted against the row; purge at the decision point; `blocked_publish_failed`
becomes a save-failure status cleaned by rag rollback; widen rag's guard.

**One claim in that summary does not hold, and it should not be agreed as
written:** *"if defer-write is feasible it subsumes the purge entirely for the
gate-driven cases."*

It does not, and this document's own evidence is why. Master RAG's ordering,
recorded above:

```
L196  blob.upload_from_string   (GCS write)
L325  db.add(document)          (row + file_hash dedup key)
L422  classify_for_ingest       (verdict)
```

**The blob is written 129 lines before the dedup key.** Deferring the key write
until admission therefore defers *the key only*. On a blocked document the GCS
blob — and whatever part of the row is written independently of the key — still
exists, written on arrival, before any verdict.

Set against the invariant as this document states it at the top: *"must leave no
trace — no GCS blob, no DB row, no `file_hash` dedup key, no chunks."*

So:

- **Defer-write fixes the DUPLICATE BRANCH structurally.** A dedup key that can
  only exist for an admitted document makes 409-means-admitted true by
  construction, and that is the part worth having.
- **It does not make "not stored" true.** The bytes are still in GCS. A purge is
  still required for the blob and the row; it is only the *key* that stops
  needing one.

**Both are needed, and they are not alternatives.** The risk in agreeing the
summary as written is that defer-write lands, the duplicate-branch symptom
disappears, the purge work is dropped as subsumed — and blocked documents go on
leaving blobs indefinitely, with nothing user-visible to reveal it. That is the
same shape as everything else in this program: the visible symptom resolves and
the underlying condition stops being observable.

### Also worth recording — the PHI seat's race point, which I think is right

Defer-write plus two concurrent CLEAN admissions of identical bytes means two
writers race the key; the loser hits a pkey collision, which must be handled as
"already admitted by the concurrent writer → serve ready", not as an error. So
defer-write and idempotent-admission are the same work — and that same
idempotency is what resolves `blocked_publish_failed`. Three problems, one fix,
which is worth Master RAG knowing before scoping it as three.
